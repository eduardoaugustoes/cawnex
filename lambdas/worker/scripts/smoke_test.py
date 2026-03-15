#!/usr/bin/env python3
"""Smoke test: run the full crow pipeline manually against real infrastructure.

Seeds crows into DynamoDB Local, invokes handler, reads results.
Each step uses the previous step's output to seed the next crow.

Prerequisites:
    1. DynamoDB Local running:  docker run -p 8000:8000 amazon/dynamodb-local
    2. Test repo exists:        python scripts/setup_test_repo.py
    3. Env vars set:
         export ANTHROPIC_AUTH_TOKEN="your-oauth-token"
         export GITHUB_TOKEN="$(gh auth token)"

Usage:
    # Run planner only (safe, no git writes):
    python scripts/smoke_test.py planner

    # Run planner + implementer (creates branch, pushes code):
    python scripts/smoke_test.py implement

    # Run full pipeline — planner → implementer → reviewer (creates PR):
    python scripts/smoke_test.py full

    # Dry run — seed crow, show what would execute, don't call Claude:
    python scripts/smoke_test.py planner --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from decimal import Decimal
from typing import Any

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import boto3

from worker.blackboard import Blackboard
from worker.config import ExecutionConfig
from worker.enums import CrowStatus, CrowType
from worker.executor import execute
from worker.logging import StructuredLogger
from worker.models import Cost, CrowSnapshot

# Config
REPO = "eduardoaugustoes/cawnex-test-target"
TENANT = "smoke"
PROJECT = "test"
WAVE_ID = f"w{int(time.time())}"
MVI_ID = "health"
BUDGET = 2_000_000  # $2 budget cap for safety (microdollars)
DIRECTIVE = "Add a GET /health endpoint that returns {status: 'healthy', timestamp: <current UTC ISO>}. Add a test for it."

DYNAMO_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT", "http://localhost:8000")
TABLE_NAME = "cawnex-smoke"


def _decimal_default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError


def pp(label: str, data: Any) -> None:
    """Pretty print with label."""
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    if isinstance(data, dict):
        print(json.dumps(data, indent=2, default=_decimal_default))
    else:
        print(data)


def check_prereqs(dry_run: bool = False) -> None:
    """Verify everything is in place before running."""
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
            print(f"  ✗ {e}")
        print()
        sys.exit(1)

    print("✓ All prerequisites met")


def get_table() -> Any:
    """Create or get the smoke test table."""
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
    print(f"✓ Created table {TABLE_NAME}")
    return table


def seed_crow(
    blackboard: Blackboard,
    crow_id: str,
    crow_type: CrowType,
    instructions: str,
    branch: str,
    budget: int = BUDGET,
) -> CrowSnapshot:
    """Write a pending crow to the blackboard."""
    crow = CrowSnapshot(
        tenant=TENANT,
        project=PROJECT,
        wave_id=WAVE_ID,
        mvi_id=MVI_ID,
        crow_id=crow_id,
        crow_type=crow_type,
        status=CrowStatus.PENDING,
        instructions=instructions,
        repo=REPO,
        branch=branch,
        budget_remaining=budget,
    )
    blackboard.write_item(crow.to_item())
    return crow


def run_crow(
    blackboard: Blackboard,
    crow: CrowSnapshot,
    config: ExecutionConfig,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Execute a single crow and write the result."""
    snapshot = {
        "crow_type": crow.crow_type.value,
        "crow_id": crow.crow_id,
        "repo": crow.repo,
        "branch": crow.branch,
        "instructions": crow.instructions,
        "budget_remaining": crow.budget_remaining,
    }

    if dry_run:
        pp(f"DRY RUN — would execute {crow.crow_type.value}", snapshot)
        return {"status": "skipped", "outcome": {"reason": "dry run"}, "cost": Cost.zero().to_dict(), "completed_at": ""}

    # Claim
    blackboard.conditional_status_update(crow.pk, crow.sk, "pending", "running")

    logger = StructuredLogger(
        component="smoke", tenant=TENANT, project=PROJECT, execution_id=crow.crow_id,
    )

    pp(f"EXECUTING {crow.crow_type.value.upper()}", {
        "crow_id": crow.crow_id,
        "repo": crow.repo,
        "branch": crow.branch,
    })

    start = time.time()
    completion = execute(snapshot, logger=logger, config=config)
    elapsed = time.time() - start

    pp(f"{crow.crow_type.value.upper()} RESULT ({elapsed:.1f}s)", completion)

    # Write completed snapshot
    cost = Cost.from_dict(completion["cost"])
    completed_crow = CrowSnapshot(
        tenant=TENANT, project=PROJECT, wave_id=WAVE_ID, mvi_id=MVI_ID,
        crow_id=crow.crow_id, crow_type=crow.crow_type,
        status=CrowStatus.COMPLETED if completion["status"] == "completed" else CrowStatus.FAILED,
        instructions=crow.instructions, repo=crow.repo, branch=crow.branch,
        budget_remaining=crow.budget_remaining - cost.credits,
        outcome=completion.get("outcome"), cost=cost,
        git_commit=completion.get("git_commit", ""),
        pr=completion.get("pr"),
        completed_at=completion.get("completed_at", ""),
    )
    blackboard.write_item(completed_crow.to_item())

    return completion


def run_planner(blackboard: Blackboard, config: ExecutionConfig, dry_run: bool) -> dict[str, Any]:
    branch = f"cawnex/{WAVE_ID}-{MVI_ID}"
    crow = seed_crow(blackboard, "cr_plan_01", CrowType.PLANNER, DIRECTIVE, branch)
    return run_crow(blackboard, crow, config, dry_run)


def run_implementer(
    blackboard: Blackboard,
    config: ExecutionConfig,
    planner_outcome: dict[str, Any],
    budget_remaining: int,
    dry_run: bool,
) -> dict[str, Any]:
    branch = f"cawnex/{WAVE_ID}-{MVI_ID}"

    # Build instructions from planner output
    tasks = planner_outcome.get("tasks", [])
    if not tasks:
        print("⚠ Planner produced no tasks. Cannot run implementer.")
        sys.exit(1)

    instructions = json.dumps({
        "task": tasks[0] if tasks else {},
        "context_files": planner_outcome.get("context_files", []),
        "files_to_modify": tasks[0].get("files_to_modify", []) if tasks else [],
    })

    crow = seed_crow(
        blackboard, "cr_impl_01", CrowType.IMPLEMENTER,
        instructions, branch, budget=budget_remaining,
    )
    return run_crow(blackboard, crow, config, dry_run)


def run_reviewer(
    blackboard: Blackboard,
    config: ExecutionConfig,
    budget_remaining: int,
    dry_run: bool,
) -> dict[str, Any]:
    branch = f"cawnex/{WAVE_ID}-{MVI_ID}"
    instructions = "Review the changes on this branch for quality, security, and correctness."
    crow = seed_crow(
        blackboard, "cr_review_01", CrowType.REVIEWER,
        instructions, branch, budget=budget_remaining,
    )
    return run_crow(blackboard, crow, config, dry_run)


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test the worker pipeline")
    parser.add_argument("mode", choices=["planner", "implement", "full"],
                        help="How far to run the pipeline")
    parser.add_argument("--dry-run", action="store_true",
                        help="Seed crows but don't call Claude")
    args = parser.parse_args()

    check_prereqs(dry_run=args.dry_run)
    table = get_table()
    blackboard = Blackboard(table)

    efs_mount = os.environ.get("EFS_MOUNT", "/tmp/cawnex-smoke-repos")
    os.makedirs(efs_mount, exist_ok=True)

    github_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN", "")
    config = ExecutionConfig(efs_mount=efs_mount, github_token=github_token)

    budget = BUDGET

    pp("SMOKE TEST", {
        "mode": args.mode,
        "repo": REPO,
        "wave_id": WAVE_ID,
        "directive": DIRECTIVE,
        "budget": budget,
        "efs_mount": efs_mount,
        "dry_run": args.dry_run,
    })

    # Step 1: Planner
    planner_result = run_planner(blackboard, config, args.dry_run)
    planner_cost = int(planner_result["cost"].get("credits", 0))
    budget -= planner_cost

    if args.mode == "planner" or args.dry_run:
        pp("DONE", {"total_cost": BUDGET - budget})
        return

    if planner_result["status"] != "completed":
        print("✗ Planner failed. Stopping.")
        sys.exit(1)

    # Step 2: Implementer
    impl_result = run_implementer(
        blackboard, config, planner_result["outcome"], budget, args.dry_run,
    )
    impl_cost = int(impl_result["cost"].get("credits", 0))
    budget -= impl_cost

    if args.mode == "implement":
        pp("DONE", {
            "total_cost": BUDGET - budget,
            "git_commit": impl_result.get("git_commit", ""),
            "pr": impl_result.get("pr"),
        })
        return

    if impl_result["status"] != "completed":
        print("✗ Implementer failed. Stopping.")
        sys.exit(1)

    # Step 3: Reviewer
    review_result = run_reviewer(blackboard, config, budget, args.dry_run)
    review_cost = int(review_result["cost"].get("credits", 0))
    budget -= review_cost

    pp("PIPELINE COMPLETE", {
        "total_cost_micros": BUDGET - budget,
        "budget_remaining_micros": budget,
        "planner": planner_result["outcome"].get("summary", ""),
        "implementer": impl_result["outcome"].get("summary", ""),
        "reviewer_approved": review_result.get("outcome", {}).get("approved"),
        "reviewer_summary": review_result.get("outcome", {}).get("summary", ""),
        "git_commit": impl_result.get("git_commit", ""),
        "pr": impl_result.get("pr"),
    })


if __name__ == "__main__":
    main()
