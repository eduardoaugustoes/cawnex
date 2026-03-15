#!/usr/bin/env python3
"""End-to-end smoke test: Murder + Worker self-driving pipeline.

Simulates DynamoDB Streams by calling Murder reactor directly after
each Worker execution. Proves the full loop:

  Murder seeds planner → Worker executes planner → Murder reads outcome,
  assigns implementer → Worker executes implementer → Murder assigns
  reviewer → Worker executes reviewer → Murder marks MVI ready_to_ship.

Prerequisites:
    1. DynamoDB Local running:  docker run -p 8000:8000 amazon/dynamodb-local
    2. Test repo exists:        python scripts/setup_test_repo.py
    3. Env vars set:
         export ANTHROPIC_AUTH_TOKEN="your-oauth-token"
         export GITHUB_TOKEN="$(gh auth token)"

Usage:
    python scripts/smoke_test_e2e.py

    # Dry run — seed everything, don't call Claude:
    python scripts/smoke_test_e2e.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

# Load .env from project root
_env_file = Path(__file__).resolve().parents[3] / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            if val and key.strip() not in os.environ:
                os.environ[key.strip()] = val.strip()

# Add both src paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "murder", "src"))

import boto3

from murder.blackboard import Blackboard
from murder.config import MICROS_PER_DOLLAR, WAVE_BUDGET_LIMIT
from murder.enums import MVIStatus, WaveStatus
from murder.keys import build_pk, build_sk
from murder.logging import StructuredLogger as MurderLogger
from murder.models import MVISnapshot, WaveBudget, WaveSnapshot
from murder.reactor import react_to_crow_completion, react_to_mvi_queued

from worker.config import ExecutionConfig
from worker.enums import CrowStatus, CrowType
from worker.executor import execute
from worker.logging import StructuredLogger as WorkerLogger
from worker.models import Cost, CrowSnapshot

# Config
REPO = "eduardoaugustoes/cawnex-test-target"
TENANT = "smoke"
PROJECT = "e2e"
WAVE_ID = f"w{int(time.time())}"
MVI_ID = "health"
BUDGET_MICROS = 2 * MICROS_PER_DOLLAR  # $2 budget cap for safety
DIRECTIVE = "Add a GET /health endpoint that returns {status: 'healthy', timestamp: <current UTC ISO>}. Add a test for it."

DYNAMO_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT", "http://localhost:8000")
TABLE_NAME = "cawnex-e2e"


def _decimal_default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError


def pp(label: str, data: Any) -> None:
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    if isinstance(data, dict):
        print(json.dumps(data, indent=2, default=_decimal_default))
    else:
        print(data)


def check_prereqs(dry_run: bool = False) -> None:
    errors: list[str] = []

    if not dry_run:
        if not os.environ.get("ANTHROPIC_AUTH_TOKEN") and not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
            errors.append("No Anthropic auth. Run: claude setup-token")
        github_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not github_token:
            errors.append("GITHUB_TOKEN not set. Run: export GITHUB_TOKEN=$(gh auth token)")

    try:
        dynamodb = boto3.resource(
            "dynamodb", endpoint_url=DYNAMO_ENDPOINT,
            region_name="us-east-1", aws_access_key_id="test", aws_secret_access_key="test",
        )
        dynamodb.meta.client.list_tables()
    except Exception as e:
        errors.append(f"DynamoDB Local not reachable at {DYNAMO_ENDPOINT}: {e}")

    if errors:
        print("PREREQUISITES NOT MET:\n")
        for e in errors:
            print(f"  x {e}")
        sys.exit(1)

    print("All prerequisites met")


def get_table() -> Any:
    dynamodb = boto3.resource(
        "dynamodb", endpoint_url=DYNAMO_ENDPOINT,
        region_name="us-east-1", aws_access_key_id="test", aws_secret_access_key="test",
    )

    try:
        existing = dynamodb.Table(TABLE_NAME)
        existing.load()
        return existing
    except Exception:
        pass

    table = dynamodb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
            {"AttributeName": "GSI1PK", "AttributeType": "S"},
            {"AttributeName": "GSI1SK", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[{
            "IndexName": "GSI1",
            "KeySchema": [
                {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
        }],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    print(f"Created table {TABLE_NAME}")
    return table


def seed_wave_and_mvi(blackboard: Blackboard) -> None:
    """Seed the wave (approved) and MVI (queued) that Murder will react to."""
    branch = f"cawnex/{WAVE_ID}-{MVI_ID}"

    wave = WaveSnapshot(
        tenant=TENANT, project=PROJECT, wave_id=WAVE_ID,
        status=WaveStatus.EXECUTING,
        human_directive=DIRECTIVE,
        budget=WaveBudget(spent=0, limit=BUDGET_MICROS),
    )
    blackboard.write_item(wave.to_item())

    mvi = MVISnapshot(
        tenant=TENANT, project=PROJECT, wave_id=WAVE_ID, mvi_id=MVI_ID,
        name="Health endpoint",
        status=MVIStatus.QUEUED,
        repo=REPO, branch=branch,
        description="Add GET /health endpoint with status and timestamp",
    )
    blackboard.write_item(mvi.to_item())
    pp("SEEDED", {"wave_id": WAVE_ID, "mvi_id": MVI_ID, "branch": branch})


def execute_pending_crow(
    blackboard: Blackboard,
    config: ExecutionConfig,
    dry_run: bool,
) -> dict[str, Any] | None:
    """Find the pending crow Murder created, execute it via Worker."""
    pk = build_pk(TENANT, PROJECT)
    crow_prefix = f"S#{WAVE_ID}#m{MVI_ID}#cr_"
    crows = blackboard.query(pk, crow_prefix)

    pending = [c for c in crows if c.get("status") == "pending"]
    if not pending:
        print("No pending crows found")
        return None

    item = pending[0]
    crow_id = item["SK"].split("#")[-1]
    crow_type = item["crow_type"]

    pp(f"WORKER: executing {crow_type}", {"crow_id": crow_id})

    if dry_run:
        print("  [dry run — skipping Claude execution]")
        return None

    # Claim: pending -> running
    blackboard.conditional_status_update(pk, item["SK"], "pending", "running")

    snapshot = {
        "crow_type": crow_type,
        "crow_id": crow_id,
        "repo": item.get("repo", ""),
        "branch": item.get("branch", ""),
        "instructions": item.get("instructions", ""),
        "budget_remaining": int(item.get("budget_remaining", 0)),
    }

    logger = WorkerLogger(
        component="smoke-e2e", tenant=TENANT, project=PROJECT, execution_id=crow_id,
    )

    start = time.time()
    completion = execute(snapshot, logger=logger, config=config)
    elapsed = time.time() - start

    pp(f"WORKER: {crow_type} result ({elapsed:.1f}s)", {
        "status": completion["status"],
        "outcome_keys": list((completion.get("outcome") or {}).keys()),
        "cost_credits": completion["cost"]["credits"],
        "git_commit": completion.get("git_commit", "")[:12],
    })

    # Write completed crow back
    cost = Cost.from_dict(completion["cost"])
    status = CrowStatus.COMPLETED if completion["status"] == "completed" else CrowStatus.FAILED

    completed_crow = CrowSnapshot(
        tenant=TENANT, project=PROJECT, wave_id=WAVE_ID, mvi_id=MVI_ID,
        crow_id=crow_id, crow_type=CrowType(crow_type), status=status,
        instructions=item.get("instructions", ""),
        repo=item.get("repo", ""), branch=item.get("branch", ""),
        budget_remaining=int(item.get("budget_remaining", 0)) - cost.credits,
        outcome=completion.get("outcome"), cost=cost,
        git_commit=completion.get("git_commit", ""),
        pr=completion.get("pr"),
        completed_at=completion.get("completed_at", ""),
    )
    blackboard.write_item(completed_crow.to_item())

    return {**completion, "crow_id": crow_id, "crow_type": crow_type, "SK": item["SK"]}


def murder_react(blackboard: Blackboard, completed_item: dict[str, Any]) -> None:
    """Call Murder reactor with the completed crow item."""
    pk = build_pk(TENANT, PROJECT)
    sk = completed_item["SK"]
    item = blackboard.read(pk, sk)
    if not item:
        print(f"Cannot read completed crow at {sk}")
        return

    logger = MurderLogger(component="smoke-e2e-murder", tenant=TENANT, project=PROJECT)
    pp("MURDER: reacting to crow completion", {
        "crow_type": item.get("crow_type"),
        "status": item.get("status"),
    })
    react_to_crow_completion(blackboard, item, logger)


def main() -> None:
    parser = argparse.ArgumentParser(description="E2E smoke test: Murder + Worker pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Seed only, don't call Claude")
    args = parser.parse_args()

    check_prereqs(dry_run=args.dry_run)
    table = get_table()
    blackboard = Blackboard(table)

    efs_mount = os.environ.get("EFS_MOUNT", "/tmp/cawnex-e2e-repos")
    os.makedirs(efs_mount, exist_ok=True)
    github_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN", "")
    config = ExecutionConfig(efs_mount=efs_mount, github_token=github_token)

    pp("E2E SMOKE TEST", {
        "repo": REPO,
        "wave_id": WAVE_ID,
        "directive": DIRECTIVE,
        "budget": f"${BUDGET_MICROS / MICROS_PER_DOLLAR:.2f}",
        "dry_run": args.dry_run,
    })

    # Step 0: Seed wave + MVI
    seed_wave_and_mvi(blackboard)

    # Step 1: Murder reacts to MVI queued -> assigns planner
    pk = build_pk(TENANT, PROJECT)
    mvi_sk = build_sk(wave_id=WAVE_ID, mvi_id=MVI_ID)
    mvi_item = blackboard.read(pk, mvi_sk)
    assert mvi_item is not None, "MVI not found after seeding"

    murder_logger = MurderLogger(component="smoke-e2e-murder", tenant=TENANT, project=PROJECT)
    pp("MURDER: reacting to MVI queued", {"mvi_id": MVI_ID})
    react_to_mvi_queued(blackboard, mvi_item, murder_logger)

    if args.dry_run:
        # Show what Murder created
        crows = blackboard.query(pk, f"S#{WAVE_ID}#m{MVI_ID}#cr_")
        pp("MURDER: created pending crow", crows[0] if crows else "none")
        pp("DRY RUN COMPLETE", "Murder assigned planner. Would execute via Worker next.")
        return

    # Step 2-N: Loop until MVI is terminal
    max_iterations = 8
    for i in range(max_iterations):
        print(f"\n--- Iteration {i + 1} ---")

        # Worker executes pending crow
        result = execute_pending_crow(blackboard, config, dry_run=False)
        if result is None:
            break

        if result["status"] != "completed":
            print(f"Crow failed: {result.get('outcome', {}).get('error', 'unknown')}")

        # Murder reacts
        murder_react(blackboard, result)

        # Check MVI status
        mvi = blackboard.read(pk, mvi_sk)
        assert mvi is not None
        mvi_status = mvi["status"]
        pp(f"MVI STATUS: {mvi_status}", {
            "can_ship": mvi.get("can_ship"),
            "cost": mvi.get("cost"),
        })

        if mvi_status in ("ready_to_ship", "failed"):
            break
    else:
        print(f"Hit max iterations ({max_iterations})")

    # Final summary
    mvi = blackboard.read(pk, mvi_sk)
    assert mvi is not None

    crows = blackboard.query(pk, f"S#{WAVE_ID}#m{MVI_ID}#cr_")
    events = blackboard.query(pk, f"EVT#{WAVE_ID}")

    pp("PIPELINE COMPLETE", {
        "mvi_status": mvi["status"],
        "can_ship": mvi.get("can_ship"),
        "total_crows": len(crows),
        "crow_types": [c["crow_type"] for c in crows],
        "total_events": len(events),
        "event_types": [e["type"] for e in events],
        "mvi_cost": mvi.get("cost"),
    })


if __name__ == "__main__":
    main()
