#!/usr/bin/env python3
"""Reflection experiment: does accumulated agent memory improve outcomes over sequential runs?

Design:
- Group A (control):   N sequential runs with reflection DISABLED — each starts fresh
- Group B (treatment): N sequential runs with reflection ENABLED — memory accumulates across runs

Key difference from experiment.py: runs are SEQUENTIAL and, in the treatment group,
memory from run N is visible to run N+1 via the MemoryStrategy. This tests whether
the reflection loop (extract → store → inject) produces a measurable improvement
as the agent specializes over time.

Usage:
    python scripts/experiment_reflection.py --runs 5 --directive crud
    python scripts/experiment_reflection.py --runs 5 --directive auth
    python scripts/experiment_reflection.py --runs 3 --directive crud --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone
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
from murder.config import MICROS_PER_DOLLAR
from murder.enums import WaveStatus
from murder.keys import build_pk, build_sk
from murder.logging import StructuredLogger as MurderLogger
from murder.memory_store import MemoryStore
from murder.models import MVISnapshot, WaveBudget, WaveSnapshot
from murder.reactor import react_to_crow_completion, react_to_mvi_queued
from murder.reflection import reflect_on_crow

from worker.config import ExecutionConfig

from experiment import (
    DIRECTIVES,
    DYNAMO_ENDPOINT,
    MAX_ITERATIONS,
    REPO,
    TABLE_NAME,
    TENANT,
    PROJECT,
    BUDGET_MICROS,
    CallLogger,
    execute_pending_crow,
    get_table,
    murder_react,
    patched_executor,
    pp,
    seed_wave_and_mvi,
    _extract_quality_metrics,
    _reset_test_repo,
    check_prereqs,
)
from experiment_memory import extract_memory
from experiment_report import RunMetrics, compute_stats, print_statistical_report
from experiment_strategies import BaselineStrategy, MemoryStrategy


# -- Reflection group run --

def run_control(
    blackboard: Blackboard,
    config: ExecutionConfig,
    run_num: int,
    directive_cfg: dict[str, str],
    log_dir: Path,
    dry_run: bool,
) -> RunMetrics:
    """Single control run: no reflection, no accumulated memory."""
    ts = int(time.time())
    wave_id = f"w{ts}_{directive_cfg['mvi_id']}_ctrl_{run_num}"
    mvi_id = directive_cfg["mvi_id"]
    branch = f"cawnex/{wave_id}-{mvi_id}"
    run_id = f"ctrl_r{run_num}"
    log_file = log_dir / f"ctrl_r{run_num}.jsonl"

    pp(f"CONTROL RUN {run_num}", {"wave_id": wave_id, "memory": "disabled"})

    _reset_test_repo(config.github_token, branch)
    seed_wave_and_mvi(blackboard, wave_id, branch, directive_cfg)

    pk = build_pk(TENANT, PROJECT)
    mvi_sk = build_sk(wave_id=wave_id, mvi_id=mvi_id)
    mvi_item = blackboard.read(pk, mvi_sk)
    assert mvi_item is not None

    murder_logger = MurderLogger(component="experiment-murder", tenant=TENANT, project=PROJECT)
    react_to_mvi_queued(blackboard, mvi_item, murder_logger)

    if dry_run:
        crows = blackboard.query(pk, f"S#{wave_id}#m{mvi_id}#cr_")
        pp("DRY RUN (control)", f"Planner assigned: {crows[0]['SK'] if crows else 'none'}")
        return RunMetrics(
            run_id=run_id, strategy_name="control",
            total_crows=0, crow_sequence=[], iterations_to_ship=0,
            first_review_approved=False, total_tokens_in=0, total_tokens_out=0,
            total_credits=0, total_duration_ms=0, wall_time_seconds=0,
            final_status="dry_run", log_file=str(log_file),
        )

    strategy = BaselineStrategy()
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

            murder_react(blackboard, result, wave_id)

            mvi = blackboard.read(pk, mvi_sk)
            assert mvi is not None
            if mvi["status"] in ("ready_to_ship", "failed"):
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
        run_id=run_id, strategy_name="control",
        total_crows=len(crow_sequence), crow_sequence=crow_sequence,
        iterations_to_ship=len(crow_sequence),
        first_review_approved=first_review_approved or False,
        total_tokens_in=total_tokens_in, total_tokens_out=total_tokens_out,
        total_credits=total_credits, total_duration_ms=total_duration_ms,
        wall_time_seconds=wall_time, final_status=final_status,
        log_file=str(log_file),
        reviewer_issue_count=quality["reviewer_issue_count"],
        reviewer_suggestion_count=quality["reviewer_suggestion_count"],
        files_changed=quality["files_changed"],
    )


def run_treatment(
    blackboard: Blackboard,
    config: ExecutionConfig,
    memory_store: MemoryStore,
    run_num: int,
    directive_cfg: dict[str, str],
    log_dir: Path,
    dry_run: bool,
) -> RunMetrics:
    """Single treatment run: reflection ENABLED, reads accumulated memory from prior runs."""
    ts = int(time.time())
    wave_id = f"w{ts}_{directive_cfg['mvi_id']}_treat_{run_num}"
    mvi_id = directive_cfg["mvi_id"]
    branch = f"cawnex/{wave_id}-{mvi_id}"
    run_id = f"treat_r{run_num}"
    log_file = log_dir / f"treat_r{run_num}.jsonl"

    # Read all accumulated agent memories before this run
    all_memories = memory_store.read_all_agent_memories(TENANT, PROJECT)
    memory_md = _format_agent_memories(all_memories, run_num)

    pp(f"TREATMENT RUN {run_num}", {
        "wave_id": wave_id,
        "memory": "enabled",
        "agents_with_memory": list(all_memories.keys()),
        "total_memory_chars": sum(len(v) for v in all_memories.values()),
    })

    _reset_test_repo(config.github_token, branch)
    seed_wave_and_mvi(blackboard, wave_id, branch, directive_cfg)

    pk = build_pk(TENANT, PROJECT)
    mvi_sk = build_sk(wave_id=wave_id, mvi_id=mvi_id)
    mvi_item = blackboard.read(pk, mvi_sk)
    assert mvi_item is not None

    murder_logger = MurderLogger(component="experiment-murder", tenant=TENANT, project=PROJECT)
    react_to_mvi_queued(blackboard, mvi_item, murder_logger)

    if dry_run:
        crows = blackboard.query(pk, f"S#{wave_id}#m{mvi_id}#cr_")
        pp("DRY RUN (treatment)", f"Planner assigned: {crows[0]['SK'] if crows else 'none'}")
        return RunMetrics(
            run_id=run_id, strategy_name="treatment",
            total_crows=0, crow_sequence=[], iterations_to_ship=0,
            first_review_approved=False, total_tokens_in=0, total_tokens_out=0,
            total_credits=0, total_duration_ms=0, wall_time_seconds=0,
            final_status="dry_run", log_file=str(log_file),
        )

    # Inject accumulated memory into the strategy
    strategy = MemoryStrategy(memory_md) if memory_md else BaselineStrategy()
    identities = strategy.build_identities()
    call_logger = CallLogger(run_id, log_file)

    crow_sequence: list[str] = []
    first_review_approved: bool | None = None
    completed_results: list[dict[str, Any]] = []
    wall_start = time.time()

    with patched_executor(identities, call_logger):
        for i in range(MAX_ITERATIONS):
            print(f"\n--- {run_id} Iteration {i + 1} ---")
            result = execute_pending_crow(blackboard, config, wave_id, mvi_id)
            if result is None:
                break

            crow_sequence.append(result["crow_type"])
            completed_results.append(result)

            if result["crow_type"] == "reviewer" and first_review_approved is None:
                outcome = result.get("outcome", {})
                first_review_approved = outcome.get("approved", False)

            murder_react(blackboard, result, wave_id)

            mvi = blackboard.read(pk, mvi_sk)
            assert mvi is not None
            if mvi["status"] in ("ready_to_ship", "failed"):
                break
        else:
            print(f"Hit max iterations ({MAX_ITERATIONS})")

    # Accumulate memory from this run for future runs
    _accumulate_memory(memory_store, completed_results)

    wall_time = time.time() - wall_start
    total_tokens_in = sum(c.tokens_in for c in call_logger.calls)
    total_tokens_out = sum(c.tokens_out for c in call_logger.calls)
    total_credits = sum(c.tokens_in * 3 + c.tokens_out * 15 for c in call_logger.calls)
    total_duration_ms = sum(c.duration_ms for c in call_logger.calls)

    mvi = blackboard.read(pk, mvi_sk)
    final_status = mvi["status"] if mvi else "unknown"
    quality = _extract_quality_metrics(blackboard, wave_id, mvi_id)

    return RunMetrics(
        run_id=run_id, strategy_name="treatment",
        total_crows=len(crow_sequence), crow_sequence=crow_sequence,
        iterations_to_ship=len(crow_sequence),
        first_review_approved=first_review_approved or False,
        total_tokens_in=total_tokens_in, total_tokens_out=total_tokens_out,
        total_credits=total_credits, total_duration_ms=total_duration_ms,
        wall_time_seconds=wall_time, final_status=final_status,
        log_file=str(log_file),
        reviewer_issue_count=quality["reviewer_issue_count"],
        reviewer_suggestion_count=quality["reviewer_suggestion_count"],
        files_changed=quality["files_changed"],
    )


def _accumulate_memory(
    memory_store: MemoryStore,
    completed_results: list[dict[str, Any]],
) -> None:
    """Extract learnings from completed crows and persist to memory store."""
    for result in completed_results:
        crow_type = result.get("crow_type", "")
        outcome = result.get("outcome") or {}
        status = result.get("status", "failed")
        if crow_type:
            learnings = reflect_on_crow(
                memory_store, TENANT, PROJECT, crow_type, outcome, status
            )
            if learnings:
                print(f"  [reflection] {crow_type}: {len(learnings)} learning(s) stored")


def _format_agent_memories(memories: dict[str, str], run_num: int) -> str:
    """Format accumulated agent memories as markdown for injection into system prompt."""
    if not memories:
        return ""
    sections = [f"## Agent Memory (accumulated from {run_num - 1} prior run(s))"]
    for agent_type, content in sorted(memories.items()):
        if content.strip():
            sections.append(f"\n### {agent_type.title()} learnings\n{content}")
    return "\n".join(sections)


# -- Per-run comparison output --

def print_run_comparison(
    run_num: int,
    control: RunMetrics,
    treatment: RunMetrics,
) -> None:
    def _delta(a: float, b: float) -> str:
        if a == 0:
            return "N/A"
        pct = ((b - a) / a) * 100
        sign = "+" if pct > 0 else ""
        return f"{sign}{pct:.0f}%"

    col_w = 20
    print(f"\n{'=' * 80}")
    print(f"  RUN {run_num} COMPARISON")
    print(f"{'=' * 80}")
    print(f"  {'':26s}{'Control':{col_w}s}{'Treatment':{col_w}s}{'Delta'}")
    print(f"  {'-' * 76}")

    rows = [
        ("Iterations to ship:", str(control.iterations_to_ship), str(treatment.iterations_to_ship),
         _delta(control.iterations_to_ship, treatment.iterations_to_ship)),
        ("1st review approved:",
         "Yes" if control.first_review_approved else "No",
         "Yes" if treatment.first_review_approved else "No", ""),
        ("Reviewer issues:",
         str(control.reviewer_issue_count), str(treatment.reviewer_issue_count),
         _delta(control.reviewer_issue_count, treatment.reviewer_issue_count)),
        ("Cost (microdollars):", str(control.total_credits), str(treatment.total_credits),
         _delta(control.total_credits, treatment.total_credits)),
        ("Wall time:", f"{control.wall_time_seconds:.0f}s", f"{treatment.wall_time_seconds:.0f}s",
         _delta(control.wall_time_seconds, treatment.wall_time_seconds)),
        ("Final status:", control.final_status, treatment.final_status, ""),
    ]
    for label, val_a, val_b, delta in rows:
        print(f"  {label:26s}{val_a:{col_w}s}{val_b:{col_w}s}{delta}")
    print()


def print_reflection_report(
    directive: str,
    control_runs: list[RunMetrics],
    treatment_runs: list[RunMetrics],
) -> None:
    """Print trend analysis showing whether treatment improves over sequential runs."""
    print(f"\n{'=' * 90}")
    print(f"  REFLECTION EXPERIMENT REPORT: {directive}")
    print(f"{'=' * 90}")

    print(f"\n  Control group (no reflection) — {len(control_runs)} runs:")
    print(f"  {'Run':<6}{'Iterations':<14}{'1st Approved':<16}{'Issues':<10}{'Cost $':<12}{'Status'}")
    print(f"  {'-' * 80}")
    for i, r in enumerate(control_runs, 1):
        cost = r.total_credits / MICROS_PER_DOLLAR
        print(f"  {i:<6}{r.iterations_to_ship:<14}{'Yes' if r.first_review_approved else 'No':<16}"
              f"{r.reviewer_issue_count:<10}${cost:<11.3f}{r.final_status}")

    print(f"\n  Treatment group (reflection enabled) — {len(treatment_runs)} runs:")
    print(f"  {'Run':<6}{'Iterations':<14}{'1st Approved':<16}{'Issues':<10}{'Cost $':<12}{'Status'}")
    print(f"  {'-' * 80}")
    for i, r in enumerate(treatment_runs, 1):
        cost = r.total_credits / MICROS_PER_DOLLAR
        print(f"  {i:<6}{r.iterations_to_ship:<14}{'Yes' if r.first_review_approved else 'Yes' if r.first_review_approved else 'No':<16}"
              f"{r.reviewer_issue_count:<10}${cost:<11.3f}{r.final_status}")

    # Trend: does treatment improve over runs?
    if len(treatment_runs) >= 2:
        first_half = treatment_runs[: len(treatment_runs) // 2]
        second_half = treatment_runs[len(treatment_runs) // 2 :]
        first_iter = sum(r.iterations_to_ship for r in first_half) / len(first_half)
        second_iter = sum(r.iterations_to_ship for r in second_half) / len(second_half)
        trend = "improving" if second_iter < first_iter else ("stable" if second_iter == first_iter else "degrading")
        print(f"\n  Treatment trend: {trend} ({first_iter:.1f} -> {second_iter:.1f} iterations)")

    # Aggregate comparison
    directive_results = {
        directive: {
            "baseline": control_runs,
            "memory": treatment_runs,
        }
    }
    print_statistical_report(directive_results)


# -- Main --

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reflection experiment: sequential runs with/without accumulated memory"
    )
    parser.add_argument("--runs", type=int, default=5,
                        help="Number of runs per group (default: 5)")
    parser.add_argument("--directive", required=True,
                        help="Directive to test (health, crud, refactor, auth)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Seed only, don't call Claude")
    args = parser.parse_args()

    if args.directive not in DIRECTIVES:
        print(f"Unknown directive: {args.directive}")
        print(f"Available: {', '.join(DIRECTIVES.keys())}")
        sys.exit(1)

    check_prereqs(dry_run=args.dry_run)
    table = get_table()
    blackboard = Blackboard(table)
    memory_store = MemoryStore(blackboard)

    efs_mount = os.environ.get("EFS_MOUNT", "/tmp/cawnex-reflection-repos")
    os.makedirs(efs_mount, exist_ok=True)
    github_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN", "")
    config = ExecutionConfig(efs_mount=efs_mount, github_token=github_token)

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_dir = Path(__file__).resolve().parent.parent / "experiments" / f"reflection_{date_str}"
    log_dir.mkdir(parents=True, exist_ok=True)

    directive_cfg = DIRECTIVES[args.directive]

    pp("REFLECTION EXPERIMENT CONFIG", {
        "directive": args.directive,
        "runs_per_group": args.runs,
        "total_runs": args.runs * 2,
        "repo": REPO,
        "budget_per_run": f"${BUDGET_MICROS / MICROS_PER_DOLLAR:.2f}",
        "dry_run": args.dry_run,
        "hypothesis": "Treatment runs improve over time as memory accumulates",
    })

    control_runs: list[RunMetrics] = []
    treatment_runs: list[RunMetrics] = []

    # Phase 1: Control group — N sequential runs with no reflection
    pp("PHASE 1: CONTROL GROUP", {"reflection": "disabled", "runs": args.runs})
    for run_num in range(1, args.runs + 1):
        metrics = run_control(blackboard, config, run_num, directive_cfg, log_dir, args.dry_run)
        control_runs.append(metrics)
        if not args.dry_run:
            cost_str = f"${metrics.total_credits / MICROS_PER_DOLLAR:.3f}"
            seq = "->".join(t[0].upper() for t in metrics.crow_sequence)
            print(f"  Control run {run_num}: {metrics.final_status}, "
                  f"{metrics.iterations_to_ship} iters, {cost_str}, seq: {seq}")
        time.sleep(1)

    # Phase 2: Treatment group — N sequential runs with reflection accumulating
    pp("PHASE 2: TREATMENT GROUP", {"reflection": "enabled", "runs": args.runs})
    for run_num in range(1, args.runs + 1):
        metrics = run_treatment(
            blackboard, config, memory_store, run_num, directive_cfg, log_dir, args.dry_run
        )
        treatment_runs.append(metrics)
        if not args.dry_run:
            cost_str = f"${metrics.total_credits / MICROS_PER_DOLLAR:.3f}"
            seq = "->".join(t[0].upper() for t in metrics.crow_sequence)
            print(f"  Treatment run {run_num}: {metrics.final_status}, "
                  f"{metrics.iterations_to_ship} iters, {cost_str}, seq: {seq}")

            # Show what memory has accumulated
            all_memories = memory_store.read_all_agent_memories(TENANT, PROJECT)
            total_chars = sum(len(v) for v in all_memories.values())
            print(f"  Memory state: {len(all_memories)} agents, {total_chars} chars total")
        time.sleep(1)

    # Results
    if not args.dry_run:
        for i, (ctrl, treat) in enumerate(zip(control_runs, treatment_runs), 1):
            print_run_comparison(i, ctrl, treat)

        print_reflection_report(args.directive, control_runs, treatment_runs)

    print(f"\nLogs saved to: {log_dir}")


if __name__ == "__main__":
    main()
