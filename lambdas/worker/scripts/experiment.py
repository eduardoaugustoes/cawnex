#!/usr/bin/env python3
"""Prompt experiment harness: statistical comparison of prompt strategies.

Cross-directive memory design: builds a memory pool from a warmup directive,
then tests whether that memory helps on a harder target directive.
This eliminates future-information bias (memory never comes from the same problem).

Usage:
    # Warmup on health, test auth with N=5 (recommended)
    python scripts/experiment.py --runs 5 --target auth

    # Warmup on health, test crud
    python scripts/experiment.py --runs 5 --target crud

    # Dry run
    python scripts/experiment.py --runs 1 --target auth --dry-run

    # Legacy mode: same-directive pairing (biased, for comparison only)
    python scripts/experiment.py --runs 3 --target crud --same-directive
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Generator

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

from experiment_memory import extract_memory
from experiment_report import RunMetrics, print_comparison, print_statistical_report
from experiment_strategies import BaselineStrategy, MemoryStrategy

# Config
REPO = "eduardoaugustoes/cawnex-test-target"
TENANT = "experiment"
PROJECT = "prompt"
BUDGET_MICROS = 2 * MICROS_PER_DOLLAR  # $2 per run

DYNAMO_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT", "http://localhost:8000")
TABLE_NAME = "cawnex-experiment"

MAX_ITERATIONS = 8

# -- Directive catalog --

DIRECTIVES: dict[str, dict[str, str]] = {
    "health": {
        "directive": "Add a GET /health endpoint that returns {status: 'healthy', timestamp: <current UTC ISO>}. Add a test for it.",
        "mvi_id": "health",
        "mvi_name": "Health endpoint",
        "mvi_description": "Add GET /health endpoint with status and timestamp",
    },
    "crud": {
        "directive": "Add CRUD endpoints for an 'items' resource: GET /items, GET /items/:id, POST /items, PUT /items/:id, DELETE /items/:id. Items have fields: id (uuid), name (string), description (string), created_at (ISO timestamp). Store in-memory. Add tests for all endpoints.",
        "mvi_id": "crud-items",
        "mvi_name": "CRUD items API",
        "mvi_description": "Full CRUD for items resource with in-memory store and tests",
    },
    "refactor": {
        "directive": "Refactor all route definitions into a separate routes/ directory. Create routes/index.js that mounts all route files. Each resource gets its own file (e.g., routes/health.js, routes/items.js). Update the main app to use the new route structure. Ensure all existing tests still pass.",
        "mvi_id": "route-refactor",
        "mvi_name": "Route refactoring",
        "mvi_description": "Extract routes into modular files under routes/ directory",
    },
    "auth": {
        "directive": "Add JWT authentication middleware. Create POST /auth/login that accepts {username, password} and returns a JWT token. Add middleware that validates JWT on all routes except /health and /auth/login. Use a hardcoded secret for now. Add tests for the auth flow including protected route access.",
        "mvi_id": "auth-middleware",
        "mvi_name": "Auth middleware",
        "mvi_description": "JWT auth with login endpoint, middleware, and tests",
    },
}

# Warmup directive used to build memory pool (always health — simple, fast, cheap)
WARMUP_DIRECTIVE = "health"


def _decimal_default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError


def pp(label: str, data: Any) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}")
    if isinstance(data, dict):
        print(json.dumps(data, indent=2, default=_decimal_default))
    else:
        print(data)


# -- Logging wrapper for Claude calls --

@dataclass
class CallLog:
    run_id: str
    crow_type: str
    system_prompt: str
    user_prompt: str
    output: str
    tokens_in: int
    tokens_out: int
    duration_ms: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "crow_type": self.crow_type,
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "output": self.output,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "duration_ms": self.duration_ms,
        }


class CallLogger:
    """Wraps call_claude to capture all prompts and outputs."""

    def __init__(self, run_id: str, log_file: Path) -> None:
        self.run_id = run_id
        self.log_file = log_file
        self.calls: list[CallLog] = []

    def make_wrapper(self, original_call_claude: Any) -> Any:
        """Return a function with the same signature as call_claude."""
        logger = self

        def logging_call_claude(
            system_prompt: str,
            user_prompt: str,
            model: str = "",
            max_tokens: int = 8192,
        ) -> Any:
            import worker.config as wc
            if not model:
                model = wc.ANTHROPIC_MODEL

            result = original_call_claude(
                system_prompt, user_prompt, model=model, max_tokens=max_tokens
            )

            crow_type = "unknown"
            for ct in ("planner", "implementer", "reviewer", "fixer"):
                if ct in system_prompt.lower()[:200]:
                    crow_type = ct
                    break

            entry = CallLog(
                run_id=logger.run_id,
                crow_type=crow_type,
                system_prompt=system_prompt,
                user_prompt=user_prompt[:2000],
                output=result.raw_output[:2000],
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
                duration_ms=result.duration_ms,
            )
            logger.calls.append(entry)

            logger.log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(logger.log_file, "a") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")

            return result

        return logging_call_claude


# -- Monkey-patch context manager --

@contextmanager
def patched_executor(
    identities: dict[str, str],
    call_logger: CallLogger,
) -> Generator[None, None, None]:
    """Monkey-patch worker.executor's CROW_IDENTITIES and call_claude."""
    import worker.executor as executor_mod
    import worker.prompts as prompts_mod
    from worker.claude import call_claude as original_call_claude

    original_identities = prompts_mod.CROW_IDENTITIES
    original_call = executor_mod.call_claude

    try:
        prompts_mod.CROW_IDENTITIES = identities
        executor_mod.CROW_IDENTITIES = identities
        executor_mod.call_claude = call_logger.make_wrapper(original_call_claude)
        yield
    finally:
        prompts_mod.CROW_IDENTITIES = original_identities
        executor_mod.CROW_IDENTITIES = original_identities
        executor_mod.call_claude = original_call


# -- DynamoDB + prereqs --

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


# -- Seed + execute --

def seed_wave_and_mvi(
    blackboard: Blackboard,
    wave_id: str,
    branch: str,
    directive_cfg: dict[str, str],
) -> None:
    wave = WaveSnapshot(
        tenant=TENANT, project=PROJECT, wave_id=wave_id,
        status=WaveStatus.EXECUTING,
        human_directive=directive_cfg["directive"],
        budget=WaveBudget(spent=0, limit=BUDGET_MICROS),
    )
    blackboard.write_item(wave.to_item())

    mvi = MVISnapshot(
        tenant=TENANT, project=PROJECT, wave_id=wave_id,
        mvi_id=directive_cfg["mvi_id"],
        name=directive_cfg["mvi_name"],
        status=MVIStatus.QUEUED,
        repo=REPO, branch=branch,
        description=directive_cfg["mvi_description"],
    )
    blackboard.write_item(mvi.to_item())
    pp("SEEDED", {"wave_id": wave_id, "mvi_id": directive_cfg["mvi_id"], "branch": branch})


def execute_pending_crow(
    blackboard: Blackboard,
    config: ExecutionConfig,
    wave_id: str,
    mvi_id: str,
) -> dict[str, Any] | None:
    pk = build_pk(TENANT, PROJECT)
    crow_prefix = f"S#{wave_id}#m{mvi_id}#cr_"
    crows = blackboard.query(pk, crow_prefix)
    pending = [c for c in crows if c.get("status") == "pending"]
    if not pending:
        print("No pending crows found")
        return None

    item = pending[0]
    crow_id = item["SK"].split("#")[-1]
    crow_type = item["crow_type"]

    pp(f"WORKER: executing {crow_type}", {"crow_id": crow_id})

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
        component="experiment", tenant=TENANT, project=PROJECT, execution_id=crow_id,
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

    cost = Cost.from_dict(completion["cost"])
    status = CrowStatus.COMPLETED if completion["status"] == "completed" else CrowStatus.FAILED

    completed_crow = CrowSnapshot(
        tenant=TENANT, project=PROJECT, wave_id=wave_id, mvi_id=mvi_id,
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


def murder_react(blackboard: Blackboard, completed_item: dict[str, Any], wave_id: str) -> None:
    pk = build_pk(TENANT, PROJECT)
    sk = completed_item["SK"]
    item = blackboard.read(pk, sk)
    if not item:
        print(f"Cannot read completed crow at {sk}")
        return
    logger = MurderLogger(component="experiment-murder", tenant=TENANT, project=PROJECT)
    pp("MURDER: reacting to crow completion", {
        "crow_type": item.get("crow_type"),
        "status": item.get("status"),
    })
    react_to_crow_completion(blackboard, item, logger)


# -- Git repo reset --

def _reset_test_repo(github_token: str, branch: str) -> None:
    """Delete experiment branch from remote to start clean."""
    try:
        subprocess.run(
            ["git", "push", f"https://x-access-token:{github_token}@github.com/{REPO}.git",
             "--delete", branch],
            capture_output=True, text=True, check=False,
        )
        print(f"  Deleted remote branch: {branch}")
    except Exception:
        print(f"  Branch {branch} did not exist on remote (OK)")


# -- Extract quality metrics from completed run --

def _extract_quality_metrics(
    blackboard: Blackboard,
    wave_id: str,
    mvi_id: str,
) -> dict[str, int]:
    """Extract richer metrics from completed crows for a run."""
    pk = build_pk(TENANT, PROJECT)
    crow_prefix = f"S#{wave_id}#m{mvi_id}#cr_"
    crows = blackboard.query(pk, crow_prefix)

    reviewer_issues = 0
    reviewer_suggestions = 0
    files_changed = 0

    for crow in crows:
        if crow.get("status") != "completed":
            continue
        outcome = crow.get("outcome", {})
        if not isinstance(outcome, dict):
            continue

        crow_type = crow.get("crow_type", "")
        if crow_type == "reviewer":
            reviewer_issues += len(outcome.get("issues", []))
            reviewer_suggestions += len(outcome.get("suggestions", []))
        elif crow_type in ("implementer", "fixer"):
            files_changed += len(outcome.get("files_changed", []))

    return {
        "reviewer_issue_count": reviewer_issues,
        "reviewer_suggestion_count": reviewer_suggestions,
        "files_changed": files_changed,
    }


# -- Run a single experiment variant --

def run_variant(
    blackboard: Blackboard,
    config: ExecutionConfig,
    strategy: Any,
    run_id: str,
    wave_id: str,
    directive_cfg: dict[str, str],
    log_file: Path,
    dry_run: bool,
) -> RunMetrics:
    """Execute one full pipeline run with a given prompt strategy."""
    mvi_id = directive_cfg["mvi_id"]
    branch = f"cawnex/{wave_id}-{mvi_id}"

    pp(f"RUN: {run_id} ({strategy.name})", {
        "wave_id": wave_id,
        "branch": branch,
        "strategy": strategy.name,
        "directive": directive_cfg["directive"][:80],
    })

    _reset_test_repo(config.github_token, branch)
    seed_wave_and_mvi(blackboard, wave_id, branch, directive_cfg)

    pk = build_pk(TENANT, PROJECT)
    mvi_sk = build_sk(wave_id=wave_id, mvi_id=mvi_id)
    mvi_item = blackboard.read(pk, mvi_sk)
    assert mvi_item is not None, "MVI not found after seeding"

    murder_logger = MurderLogger(component="experiment-murder", tenant=TENANT, project=PROJECT)
    react_to_mvi_queued(blackboard, mvi_item, murder_logger)

    if dry_run:
        crows = blackboard.query(pk, f"S#{wave_id}#m{mvi_id}#cr_")
        pp("DRY RUN", f"Murder assigned planner: {crows[0]['SK'] if crows else 'none'}")
        return RunMetrics(
            run_id=run_id, strategy_name=strategy.name,
            total_crows=0, crow_sequence=[], iterations_to_ship=0,
            first_review_approved=False, total_tokens_in=0, total_tokens_out=0,
            total_credits=0, total_duration_ms=0, wall_time_seconds=0,
            final_status="dry_run", log_file=str(log_file),
        )

    identities = strategy.build_identities()
    call_logger = CallLogger(run_id, log_file)

    crow_sequence: list[str] = []
    first_review_approved: bool | None = None
    wall_start = time.time()

    with patched_executor(identities, call_logger):
        for i in range(MAX_ITERATIONS):
            print(f"\n--- {run_id} Iteration {i + 1} ---")

            result = execute_pending_crow(blackboard, config, wave_id, mvi_id)
            if result is None:
                break

            crow_sequence.append(result["crow_type"])

            if result["crow_type"] == "reviewer" and first_review_approved is None:
                outcome = result.get("outcome", {})
                first_review_approved = outcome.get("approved", False)

            if result["status"] != "completed":
                print(f"Crow failed: {result.get('outcome', {}).get('error', 'unknown')}")

            murder_react(blackboard, result, wave_id)

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
            print(f"Hit max iterations ({MAX_ITERATIONS})")

    wall_time = time.time() - wall_start

    total_tokens_in = sum(c.tokens_in for c in call_logger.calls)
    total_tokens_out = sum(c.tokens_out for c in call_logger.calls)
    total_credits = sum(c.tokens_in * 3 + c.tokens_out * 15 for c in call_logger.calls)
    total_duration_ms = sum(c.duration_ms for c in call_logger.calls)

    mvi = blackboard.read(pk, mvi_sk)
    final_status = mvi["status"] if mvi else "unknown"

    quality = _extract_quality_metrics(blackboard, wave_id, mvi_id)

    return RunMetrics(
        run_id=run_id,
        strategy_name=strategy.name,
        total_crows=len(crow_sequence),
        crow_sequence=crow_sequence,
        iterations_to_ship=len(crow_sequence),
        first_review_approved=first_review_approved or False,
        total_tokens_in=total_tokens_in,
        total_tokens_out=total_tokens_out,
        total_credits=total_credits,
        total_duration_ms=total_duration_ms,
        wall_time_seconds=wall_time,
        final_status=final_status,
        log_file=str(log_file),
        reviewer_issue_count=quality["reviewer_issue_count"],
        reviewer_suggestion_count=quality["reviewer_suggestion_count"],
        files_changed=quality["files_changed"],
    )


# -- Warmup: build memory pool from a simpler directive --

def build_memory_pool(
    blackboard: Blackboard,
    config: ExecutionConfig,
    log_dir: Path,
    dry_run: bool,
) -> str:
    """Run warmup directive once and extract memory. Returns memory markdown."""
    warmup_cfg = DIRECTIVES[WARMUP_DIRECTIVE]
    ts = int(time.time())
    wave_id = f"w{ts}_warmup_{WARMUP_DIRECTIVE}"

    pp("WARMUP PHASE", {
        "directive": WARMUP_DIRECTIVE,
        "purpose": "Build cross-directive memory pool (no future-information bias)",
    })

    metrics = run_variant(
        blackboard, config,
        strategy=BaselineStrategy(),
        run_id=f"warmup_{WARMUP_DIRECTIVE}",
        wave_id=wave_id,
        directive_cfg=warmup_cfg,
        log_file=log_dir / f"warmup_{WARMUP_DIRECTIVE}.jsonl",
        dry_run=dry_run,
    )

    if dry_run:
        return "## Project Memory\n- (dry run — no data)"

    memory_md = extract_memory(
        blackboard, TENANT, PROJECT, wave_id, warmup_cfg["mvi_id"]
    )
    pp("WARMUP MEMORY POOL", memory_md)

    pp("WARMUP RESULT", {
        "status": metrics.final_status,
        "iterations": metrics.iterations_to_ship,
        "cost": f"${metrics.total_credits / MICROS_PER_DOLLAR:.3f}",
        "sequence": "->".join(t[0].upper() for t in metrics.crow_sequence),
    })

    return memory_md


# -- Main --

def main() -> None:
    parser = argparse.ArgumentParser(description="Prompt experiment harness")
    parser.add_argument("--runs", type=int, default=5,
                        help="Number of runs per strategy (default: 5)")
    parser.add_argument("--target", required=True,
                        help="Target directive to test (health, crud, refactor, auth)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Seed only, don't call Claude")
    parser.add_argument("--same-directive", action="store_true",
                        help="Legacy mode: use same-directive memory (biased)")
    args = parser.parse_args()

    if args.target not in DIRECTIVES:
        print(f"Unknown directive: {args.target}")
        print(f"Available: {', '.join(DIRECTIVES.keys())}")
        sys.exit(1)

    check_prereqs(dry_run=args.dry_run)
    table = get_table()
    blackboard = Blackboard(table)

    efs_mount = os.environ.get("EFS_MOUNT", "/tmp/cawnex-experiment-repos")
    os.makedirs(efs_mount, exist_ok=True)
    github_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN", "")
    config = ExecutionConfig(efs_mount=efs_mount, github_token=github_token)

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_dir = Path(__file__).resolve().parent.parent / "experiments" / date_str

    target_cfg = DIRECTIVES[args.target]
    memory_source = "same-directive (biased)" if args.same_directive else f"cross-directive ({WARMUP_DIRECTIVE})"
    total_runs = args.runs * 2 + (0 if args.same_directive else 1)  # +1 for warmup

    pp("EXPERIMENT CONFIG", {
        "target_directive": args.target,
        "memory_source": memory_source,
        "runs_per_strategy": args.runs,
        "total_runs": total_runs,
        "repo": REPO,
        "budget_per_run": f"${BUDGET_MICROS / MICROS_PER_DOLLAR:.2f}",
        "dry_run": args.dry_run,
    })

    # Phase 1: Build memory pool (unless same-directive mode)
    if not args.same_directive:
        memory_pool = build_memory_pool(blackboard, config, log_dir, args.dry_run)
    else:
        memory_pool = ""  # Will be overwritten per-run

    # Phase 2: Paired runs on target directive
    directive_results: dict[str, dict[str, list[RunMetrics]]] = {
        args.target: {"baseline": [], "memory": []},
    }

    for run_num in range(1, args.runs + 1):
        ts = int(time.time())

        # Baseline run
        wave_baseline = f"w{ts}_{args.target}_{run_num}_baseline"
        metrics_baseline = run_variant(
            blackboard, config,
            strategy=BaselineStrategy(),
            run_id=f"{args.target}_r{run_num}_baseline",
            wave_id=wave_baseline,
            directive_cfg=target_cfg,
            log_file=log_dir / f"{args.target}_r{run_num}_baseline.jsonl",
            dry_run=args.dry_run,
        )
        directive_results[args.target]["baseline"].append(metrics_baseline)

        # Determine memory source
        if args.same_directive:
            if not args.dry_run:
                memory_pool = extract_memory(
                    blackboard, TENANT, PROJECT, wave_baseline, target_cfg["mvi_id"]
                )
                pp("EXTRACTED SAME-DIRECTIVE MEMORY (biased)", memory_pool)
            else:
                memory_pool = "## Project Memory\n- (dry run — no data)"

        # Memory run
        time.sleep(1)
        wave_memory = f"w{int(time.time())}_{args.target}_{run_num}_memory"
        metrics_memory = run_variant(
            blackboard, config,
            strategy=MemoryStrategy(memory_pool),
            run_id=f"{args.target}_r{run_num}_memory",
            wave_id=wave_memory,
            directive_cfg=target_cfg,
            log_file=log_dir / f"{args.target}_r{run_num}_memory.jsonl",
            dry_run=args.dry_run,
        )
        directive_results[args.target]["memory"].append(metrics_memory)

        if not args.dry_run:
            print_comparison(
                f"{args.target} run {run_num}",
                metrics_baseline,
                metrics_memory,
            )

    # Statistical summary
    if not args.dry_run:
        print_statistical_report(directive_results)

    print(f"\nLogs saved to: {log_dir}")


if __name__ == "__main__":
    main()
