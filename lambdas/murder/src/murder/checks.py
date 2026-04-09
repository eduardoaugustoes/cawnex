"""Deterministic MVI checks — run after reviewer approves, before ready_to_ship."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


class CheckSeverity(Enum):
    HARD = "hard"
    SOFT = "soft"


@dataclass
class CheckResult:
    name: str
    passed: bool
    severity: CheckSeverity
    detail: str

    @property
    def is_hard_block(self) -> bool:
        return not self.passed and self.severity == CheckSeverity.HARD

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "severity": self.severity.value,
            "detail": self.detail,
        }


def _check_tests_pass(outcome: dict[str, Any]) -> CheckResult:
    test_results = outcome.get("test_results")
    if not test_results:
        return CheckResult(
            "tests_pass", False, CheckSeverity.HARD, "No test results found"
        )
    exit_code = test_results.get("exit_code", 1)
    summary = test_results.get("summary", "")
    return CheckResult(
        "tests_pass",
        exit_code == 0,
        CheckSeverity.HARD,
        summary if exit_code == 0 else f"Tests failed: {summary}",
    )


def _check_lint_passes(outcome: dict[str, Any]) -> CheckResult:
    lint_results = outcome.get("lint_results")
    if not lint_results:
        return CheckResult(
            "lint_passes", True, CheckSeverity.SOFT, "No lint results (skipped)"
        )
    exit_code = lint_results.get("exit_code", 1)
    summary = lint_results.get("summary", "")
    return CheckResult(
        "lint_passes",
        exit_code == 0,
        CheckSeverity.SOFT,
        summary if exit_code == 0 else f"Lint issues: {summary}",
    )


def _check_coverage_no_drop(outcome: dict[str, Any]) -> CheckResult:
    coverage = outcome.get("coverage_delta")
    if not coverage:
        return CheckResult(
            "coverage_no_drop",
            True,
            CheckSeverity.SOFT,
            "No coverage data (skipped)",
        )
    before = coverage.get("before", 0.0)
    after = coverage.get("after", 0.0)
    dropped = after < before
    detail = f"{before:.1f}% -> {after:.1f}%"
    return CheckResult(
        "coverage_no_drop",
        not dropped,
        CheckSeverity.SOFT,
        f"Coverage dropped: {detail}" if dropped else f"Coverage stable: {detail}",
    )


# Patterns that indicate secrets in diffs
_SECRET_PATTERNS = [
    re.compile(r"(?:AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}", re.ASCII),  # AWS access key
    re.compile(r"(?:^|[^A-Za-z0-9/+=])[A-Za-z0-9/+=]{40}(?:[^A-Za-z0-9/+=]|$)"),  # AWS secret
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),  # OpenAI/Anthropic style keys
    re.compile(r"ghp_[a-zA-Z0-9]{36,}"),  # GitHub personal access token
    re.compile(r"gho_[a-zA-Z0-9]{36,}"),  # GitHub OAuth token
    re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----"),  # Private keys
    re.compile(r"(?:password|secret|token|api_key)\s*[:=]\s*['\"][^'\"]{8,}['\"]", re.I),
]


def _check_no_secrets(outcome: dict[str, Any]) -> CheckResult:
    """Scan diff/changed files for hardcoded secrets."""
    diff = outcome.get("diff", "")
    changed_files_content = outcome.get("changed_files_content", "")
    scan_text = f"{diff}\n{changed_files_content}"

    if not scan_text.strip():
        return CheckResult(
            "no_secrets", True, CheckSeverity.HARD, "No diff to scan (skipped)"
        )

    findings: list[str] = []
    for pattern in _SECRET_PATTERNS:
        matches = pattern.findall(scan_text)
        if matches:
            # Don't leak the actual secret in the detail
            findings.append(f"Pattern match: {pattern.pattern[:40]}... ({len(matches)} hit(s))")

    if findings:
        return CheckResult(
            "no_secrets",
            False,
            CheckSeverity.HARD,
            f"Potential secrets found: {'; '.join(findings)}",
        )

    return CheckResult("no_secrets", True, CheckSeverity.HARD, "No secrets detected")


def _check_acceptance_criteria(
    outcome: dict[str, Any], mvi_item: dict[str, Any]
) -> CheckResult:
    """Check that acceptance criteria are addressed in the implementation."""
    criteria = mvi_item.get("acceptance_criteria", "")
    if not criteria or not criteria.strip():
        return CheckResult(
            "acceptance_criteria",
            True,
            CheckSeverity.SOFT,
            "No acceptance criteria defined (skipped)",
        )

    # Parse criteria lines (supports "- [ ] item" and "- item" formats)
    criteria_lines = []
    for line in criteria.strip().split("\n"):
        line = line.strip()
        cleaned = re.sub(r"^[-*]\s*(\[.\]\s*)?", "", line).strip()
        if cleaned:
            criteria_lines.append(cleaned)

    if not criteria_lines:
        return CheckResult(
            "acceptance_criteria",
            True,
            CheckSeverity.SOFT,
            "No parseable criteria found (skipped)",
        )

    # Check if tests or commit messages reference criteria keywords
    test_summary = outcome.get("test_results", {}).get("summary", "")
    commit_messages = outcome.get("commit_messages", "")
    diff = outcome.get("diff", "")
    reference_text = f"{test_summary}\n{commit_messages}\n{diff}".lower()

    addressed = []
    unaddressed = []
    for criterion in criteria_lines:
        # Extract keywords (3+ chars) from the criterion
        keywords = [w.lower() for w in re.findall(r"\b\w{3,}\b", criterion)]
        # Consider addressed if at least 40% of keywords appear in the reference
        if keywords:
            matches = sum(1 for kw in keywords if kw in reference_text)
            ratio = matches / len(keywords)
            if ratio >= 0.4:
                addressed.append(criterion[:50])
            else:
                unaddressed.append(criterion[:50])
        else:
            addressed.append(criterion[:50])

    total = len(criteria_lines)
    addressed_count = len(addressed)

    if unaddressed:
        return CheckResult(
            "acceptance_criteria",
            False,
            CheckSeverity.SOFT,
            f"{addressed_count}/{total} criteria addressed. Unaddressed: {'; '.join(unaddressed[:3])}",
        )

    return CheckResult(
        "acceptance_criteria",
        True,
        CheckSeverity.SOFT,
        f"All {total} criteria addressed",
    )


def _check_integration(outcome: dict[str, Any]) -> CheckResult:
    """Check that the MVI integrates cleanly with other in-flight work."""
    integration = outcome.get("integration_check")
    if not integration:
        return CheckResult(
            "integration",
            True,
            CheckSeverity.HARD,
            "No integration check data (skipped)",
        )

    merge_ok = integration.get("merge_ok", False)
    build_ok = integration.get("build_ok", False)
    detail = integration.get("detail", "")

    if not merge_ok:
        return CheckResult(
            "integration",
            False,
            CheckSeverity.HARD,
            f"Merge conflict: {detail}",
        )

    if not build_ok:
        return CheckResult(
            "integration",
            False,
            CheckSeverity.HARD,
            f"Build failed after merge: {detail}",
        )

    return CheckResult(
        "integration", True, CheckSeverity.HARD, "Merge and build succeeded"
    )


def run_deterministic_checks(
    outcome: dict[str, Any],
    mvi_item: dict[str, Any],
) -> list[CheckResult]:
    """Run all deterministic checks against crow outcome and MVI data."""
    return [
        _check_tests_pass(outcome),
        _check_no_secrets(outcome),
        _check_integration(outcome),
        _check_lint_passes(outcome),
        _check_coverage_no_drop(outcome),
        _check_acceptance_criteria(outcome, mvi_item),
    ]
