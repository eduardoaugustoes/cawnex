"""Compare metrics across experiment runs and print formatted report."""

from __future__ import annotations

import math
from dataclasses import dataclass


MICROS_PER_DOLLAR = 1_000_000

# t-distribution critical values for 95% CI (two-tailed, alpha=0.05)
# Key: degrees of freedom (n-1), Value: t-critical
_T_TABLE: dict[int, float] = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    15: 2.131,
    20: 2.086,
    30: 2.042,
    60: 2.000,
    120: 1.980,
}


def _t_critical(df: int) -> float:
    """Look up t-critical value for given degrees of freedom."""
    if df <= 0:
        return float("inf")
    if df in _T_TABLE:
        return _T_TABLE[df]
    # Interpolate between nearest entries
    keys = sorted(_T_TABLE.keys())
    for i in range(len(keys) - 1):
        if keys[i] <= df <= keys[i + 1]:
            lo, hi = keys[i], keys[i + 1]
            frac = (df - lo) / (hi - lo)
            return _T_TABLE[lo] + frac * (_T_TABLE[hi] - _T_TABLE[lo])
    return _T_TABLE[keys[-1]]  # df > 120 → use largest


@dataclass
class RunMetrics:
    run_id: str
    strategy_name: str
    total_crows: int
    crow_sequence: list[str]
    iterations_to_ship: int
    first_review_approved: bool
    total_tokens_in: int
    total_tokens_out: int
    total_credits: int
    total_duration_ms: int
    wall_time_seconds: float
    final_status: str
    log_file: str
    # Richer quality metrics
    reviewer_issue_count: int = 0
    reviewer_suggestion_count: int = 0
    files_changed: int = 0


@dataclass
class StatSummary:
    mean: float
    stddev: float
    n: int
    ci_lower: float
    ci_upper: float


def compute_stats(values: list[float]) -> StatSummary:
    """Compute mean, stddev, and 95% CI via t-distribution."""
    n = len(values)
    if n == 0:
        return StatSummary(mean=0, stddev=0, n=0, ci_lower=0, ci_upper=0)
    mean = sum(values) / n
    if n == 1:
        return StatSummary(mean=mean, stddev=0, n=1, ci_lower=mean, ci_upper=mean)
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    stddev = math.sqrt(variance)
    se = stddev / math.sqrt(n)
    t = _t_critical(n - 1)
    margin = t * se
    return StatSummary(
        mean=mean,
        stddev=stddev,
        n=n,
        ci_lower=mean - margin,
        ci_upper=mean + margin,
    )


def _delta(a: float, b: float) -> str:
    """Format percentage delta between two values."""
    if a == 0:
        return "N/A"
    pct = ((b - a) / a) * 100
    sign = "+" if pct > 0 else ""
    return f"{sign}{pct:.0f}%"


def _bool_delta(a: bool, b: bool) -> str:
    if a == b:
        return "same"
    return "+++" if b and not a else "---"


def _sig_indicator(baseline: StatSummary, treatment: StatSummary) -> str:
    """Check if confidence intervals overlap — non-overlap suggests significance."""
    if baseline.n < 2 or treatment.n < 2:
        return ""
    if treatment.ci_upper < baseline.ci_lower or treatment.ci_lower > baseline.ci_upper:
        return " *"
    return ""


def _fmt_stat(stat: StatSummary, fmt: str = ".1f") -> str:
    """Format a stat summary as 'mean ± stddev (n=N)'."""
    return f"{stat.mean:{fmt}} ±{stat.stddev:{fmt}} (n={stat.n})"


def _fmt_ci(stat: StatSummary, fmt: str = ".1f") -> str:
    """Format 95% CI as '[lo, hi]'."""
    return f"[{stat.ci_lower:{fmt}}, {stat.ci_upper:{fmt}}]"


def print_statistical_report(
    directive_results: dict[str, dict[str, list[RunMetrics]]],
) -> None:
    """Print per-directive and aggregate comparison with significance indicators.

    directive_results: {directive_id: {"baseline": [RunMetrics...], "memory": [RunMetrics...]}}
    """
    print(f"\n{'=' * 110}")
    print("  STATISTICAL EXPERIMENT REPORT")
    print(f"{'=' * 110}")

    all_baseline_iters: list[float] = []
    all_memory_iters: list[float] = []
    all_baseline_cost: list[float] = []
    all_memory_cost: list[float] = []

    for directive_id, strategies in sorted(directive_results.items()):
        baseline_runs = strategies.get("baseline", [])
        memory_runs = strategies.get("memory", [])

        b_iters = [float(r.iterations_to_ship) for r in baseline_runs]
        m_iters = [float(r.iterations_to_ship) for r in memory_runs]
        b_cost = [r.total_credits / MICROS_PER_DOLLAR for r in baseline_runs]
        m_cost = [r.total_credits / MICROS_PER_DOLLAR for r in memory_runs]
        b_approve = sum(1 for r in baseline_runs if r.first_review_approved)
        m_approve = sum(1 for r in memory_runs if r.first_review_approved)
        b_issues = [float(r.reviewer_issue_count) for r in baseline_runs]
        m_issues = [float(r.reviewer_issue_count) for r in memory_runs]
        b_files = [float(r.files_changed) for r in baseline_runs]
        m_files = [float(r.files_changed) for r in memory_runs]

        all_baseline_iters.extend(b_iters)
        all_memory_iters.extend(m_iters)
        all_baseline_cost.extend(b_cost)
        all_memory_cost.extend(m_cost)

        s_b_iter = compute_stats(b_iters)
        s_m_iter = compute_stats(m_iters)
        s_b_cost = compute_stats(b_cost)
        s_m_cost = compute_stats(m_cost)
        s_b_issues = compute_stats(b_issues)
        s_m_issues = compute_stats(m_issues)
        s_b_files = compute_stats(b_files)
        s_m_files = compute_stats(m_files)

        print(f"\n  Directive: {directive_id}")
        print(f"  {'-' * 106}")
        col_w = 30
        print(f"  {'':28s}{'Baseline':{col_w}s}{'Memory':{col_w}s}{'Delta'}")
        print(f"  {'-' * 106}")

        sig_iter = _sig_indicator(s_b_iter, s_m_iter)
        sig_cost = _sig_indicator(s_b_cost, s_m_cost)
        sig_issues = _sig_indicator(s_b_issues, s_m_issues)

        print(f"  {'Iterations (mean±sd):':<28s}{_fmt_stat(s_b_iter):{col_w}s}{_fmt_stat(s_m_iter):{col_w}s}{_delta(s_b_iter.mean, s_m_iter.mean)}{sig_iter}")
        print(f"  {'  95% CI:':<28s}{_fmt_ci(s_b_iter):{col_w}s}{_fmt_ci(s_m_iter):{col_w}s}")
        print(f"  {'Cost $ (mean±sd):':<28s}{_fmt_stat(s_b_cost, '.3f'):{col_w}s}{_fmt_stat(s_m_cost, '.3f'):{col_w}s}{_delta(s_b_cost.mean, s_m_cost.mean)}{sig_cost}")
        print(f"  {'  95% CI:':<28s}{_fmt_ci(s_b_cost, '.3f'):{col_w}s}{_fmt_ci(s_m_cost, '.3f'):{col_w}s}")
        b_approve_str = f"{b_approve}/{len(baseline_runs)}"
        m_approve_str = f"{m_approve}/{len(memory_runs)}"
        print(f"  {'1st review approved:':<28s}{b_approve_str:{col_w}s}{m_approve_str}")
        print(f"  {'Reviewer issues (mean±sd):':<28s}{_fmt_stat(s_b_issues):{col_w}s}{_fmt_stat(s_m_issues):{col_w}s}{_delta(s_b_issues.mean, s_m_issues.mean)}{sig_issues}")
        print(f"  {'Files changed (mean±sd):':<28s}{_fmt_stat(s_b_files):{col_w}s}{_fmt_stat(s_m_files):{col_w}s}{_delta(s_b_files.mean, s_m_files.mean)}")

    # Aggregate
    s_all_b_iter = compute_stats(all_baseline_iters)
    s_all_m_iter = compute_stats(all_memory_iters)
    s_all_b_cost = compute_stats(all_baseline_cost)
    s_all_m_cost = compute_stats(all_memory_cost)

    col_w = 30
    print(f"\n  {'=' * 106}")
    print(f"  AGGREGATE (all directives)")
    print(f"  {'=' * 106}")
    print(f"  {'':28s}{'Baseline':{col_w}s}{'Memory':{col_w}s}{'Delta'}")
    print(f"  {'-' * 106}")

    sig_iter = _sig_indicator(s_all_b_iter, s_all_m_iter)
    sig_cost = _sig_indicator(s_all_b_cost, s_all_m_cost)

    print(f"  {'Iterations (mean±sd):':<28s}{_fmt_stat(s_all_b_iter):{col_w}s}{_fmt_stat(s_all_m_iter):{col_w}s}{_delta(s_all_b_iter.mean, s_all_m_iter.mean)}{sig_iter}")
    print(f"  {'  95% CI:':<28s}{_fmt_ci(s_all_b_iter):{col_w}s}{_fmt_ci(s_all_m_iter):{col_w}s}")
    print(f"  {'Cost $ (mean±sd):':<28s}{_fmt_stat(s_all_b_cost, '.3f'):{col_w}s}{_fmt_stat(s_all_m_cost, '.3f'):{col_w}s}{_delta(s_all_b_cost.mean, s_all_m_cost.mean)}{sig_cost}")
    print(f"  {'  95% CI:':<28s}{_fmt_ci(s_all_b_cost, '.3f'):{col_w}s}{_fmt_ci(s_all_m_cost, '.3f'):{col_w}s}")
    print(f"\n  * = CIs do not overlap (suggestive of significance at p<0.05)")
    print(f"  N(baseline) = {len(all_baseline_iters)}, N(memory) = {len(all_memory_iters)}")
    print(f"{'=' * 110}\n")


def print_comparison(experiment_name: str, run_a: RunMetrics, run_b: RunMetrics) -> None:
    """Print side-by-side comparison of two runs."""
    cost_a = run_a.total_credits / MICROS_PER_DOLLAR
    cost_b = run_b.total_credits / MICROS_PER_DOLLAR
    tokens_a = run_a.total_tokens_in + run_a.total_tokens_out
    tokens_b = run_b.total_tokens_in + run_b.total_tokens_out
    seq_a = "->".join(t[0].upper() for t in run_a.crow_sequence)
    seq_b = "->".join(t[0].upper() for t in run_b.crow_sequence)

    col_w = 24
    header = f"{'':28s}{'Run A (' + run_a.strategy_name + ')':{col_w}s}{'Run B (' + run_b.strategy_name + ')':{col_w}s}{'Delta':{col_w}s}"

    print(f"\n{'=' * 100}")
    print(f"  EXPERIMENT: {experiment_name}")
    print(f"{'=' * 100}")
    print(header)
    print("-" * 100)

    rows = [
        (
            "Iterations to ship:",
            str(run_a.iterations_to_ship),
            str(run_b.iterations_to_ship),
            _delta(run_a.iterations_to_ship, run_b.iterations_to_ship),
        ),
        (
            "First review approved:",
            "Yes" if run_a.first_review_approved else "No",
            "Yes" if run_b.first_review_approved else "No",
            _bool_delta(run_a.first_review_approved, run_b.first_review_approved),
        ),
        (
            "Total tokens (in+out):",
            f"{tokens_a:,}",
            f"{tokens_b:,}",
            _delta(tokens_a, tokens_b),
        ),
        (
            "Total cost:",
            f"${cost_a:.3f}",
            f"${cost_b:.3f}",
            _delta(cost_a, cost_b),
        ),
        (
            "Wall time:",
            f"{run_a.wall_time_seconds:.0f}s",
            f"{run_b.wall_time_seconds:.0f}s",
            _delta(run_a.wall_time_seconds, run_b.wall_time_seconds),
        ),
        (
            "Crow sequence:",
            seq_a,
            seq_b,
            "shorter" if len(run_b.crow_sequence) < len(run_a.crow_sequence) else (
                "longer" if len(run_b.crow_sequence) > len(run_a.crow_sequence) else "same"
            ),
        ),
        (
            "Final status:",
            run_a.final_status,
            run_b.final_status,
            "",
        ),
    ]

    for label, val_a, val_b, delta in rows:
        print(f"  {label:26s}{val_a:{col_w}s}{val_b:{col_w}s}{delta}")

    print()
    print(f"  Run A logs: {run_a.log_file}")
    print(f"  Run B logs: {run_b.log_file}")
    print(f"{'=' * 100}\n")
