# Stage 4 Layer A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the wave-level Integrator crow and tool-equipped Council Fargate service so completed waves are routed through deterministic checks + 6-advisor adversarial review before reaching the founder gate.

**Architecture:** Two new components and three new wave states. The Integrator is a new `crow_kind=integrator` inside the existing Worker (lambdas/worker subpackage) that sets up per-PR worktrees on EFS, attempts an integration merge, and runs lint/typecheck/tests. The Council is the existing `lambdas/council/` Lambda code rewritten in place to run as a dedicated Fargate service with 6 advisors in parallel asyncio tasks, each opening its own Anthropic streaming conversation with a scoped tool palette. Murder reactor gains three new dispatch paths to route the wave through `integrating → (needs_rework | under_council_review) → under_human_review`.

**Tech Stack:** Python 3.12, Anthropic SDK (streaming + tool-use), FastAPI not used (poll-loop pattern), pytest + pytest-asyncio, moto for DDB mocking, AWS CDK (TypeScript) for Fargate service + IAM, asyncio for parallel advisors, subprocess for deterministic checks, GitPython or `git` CLI for worktree ops.

**Spec:** [docs/superpowers/specs/2026-05-16-council-layer-a-design.md](../specs/2026-05-16-council-layer-a-design.md)

**Loud-failure rule:** Every error path emits a structured `council_pipeline_error` event to the events table AND logs at ERROR with structured JSON. No `except Exception: pass` anywhere — lint rule enforced.

---

## Milestone M1 — Integrator crow + wave state machine extension (~5-6 days)

**M1 outcome:** A real wave's Integrator runs on Worker, attempts merge, runs deterministic checks, emits `IntegratorFindings` to DDB. Murder reactor routes the wave to `needs_rework` (dispatches fixers) or to a pending Council session (which nobody picks up yet — M2). Wave state machine has the three new states.

### Task 1: Add new wave statuses to the enum

**Files:**
- Modify: `lambdas/murder/src/murder/enums.py`
- Test: `lambdas/murder/tests/test_enums.py`

- [ ] **Step 1: Write the failing test**

```python
# lambdas/murder/tests/test_enums.py
from murder.enums import WaveStatus

def test_wave_status_includes_integrating():
    assert WaveStatus.INTEGRATING.value == "integrating"

def test_wave_status_includes_needs_rework():
    assert WaveStatus.NEEDS_REWORK.value == "needs_rework"

def test_wave_status_includes_under_council_review():
    assert WaveStatus.UNDER_COUNCIL_REVIEW.value == "under_council_review"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd lambdas/murder && pytest tests/test_enums.py -v`
Expected: FAIL — `AttributeError: INTEGRATING` (or similar) because the values don't exist yet.

- [ ] **Step 3: Add the new enum values**

Open `lambdas/murder/src/murder/enums.py`, find the existing `class WaveStatus(Enum):` block, add three new members:

```python
class WaveStatus(Enum):
    # ... existing values ...
    INTEGRATING = "integrating"
    NEEDS_REWORK = "needs_rework"
    UNDER_COUNCIL_REVIEW = "under_council_review"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd lambdas/murder && pytest tests/test_enums.py -v`
Expected: PASS, 3 tests.

- [ ] **Step 5: Commit**

```bash
git add lambdas/murder/src/murder/enums.py lambdas/murder/tests/test_enums.py
git commit -m "feat(murder): add integrating, needs_rework, under_council_review wave states"
```

### Task 2: IntegratorFindings dataclass

**Files:**
- Create: `lambdas/worker/src/worker/integrator/__init__.py`
- Create: `lambdas/worker/src/worker/integrator/findings.py`
- Create: `lambdas/worker/tests/integrator/__init__.py`
- Create: `lambdas/worker/tests/integrator/test_findings.py`

- [ ] **Step 1: Write the failing test**

```python
# lambdas/worker/tests/integrator/test_findings.py
from worker.integrator.findings import (
    IntegratorFindings,
    MergeConflict,
    CheckResult,
)

def test_check_result_skipped_is_not_failure():
    result = CheckResult(status="skipped", failures=[], duration_ms=0, command="mypy")
    assert result.status == "skipped"

def test_merge_conflict_carries_mvi_ownership():
    conflict = MergeConflict(
        pr_a=42, pr_b=43, files=["foo.py"], hunks=["<<<<<<<..."], mvi_a="m_1", mvi_b="m_2"
    )
    assert conflict.mvi_a == "m_1"

def test_integrator_findings_serializes():
    findings = IntegratorFindings(
        PK="P#proj1",
        SK="INTEGRATION#w1",
        wave_id="w1",
        pr_numbers=[42, 43],
        integration_branch="council-review-w1",
        merge_status="ok",
        merge_conflicts=[],
        lint=CheckResult(status="ok", failures=[], duration_ms=100, command="black --check ."),
        typecheck=None,
        tests=None,
        worktree_paths={42: "/mnt/repos/T/t1/r/.pr-42"},
        integration_worktree="/mnt/repos/T/t1/r/.integration",
        overall="ready_for_council",
        rework_reasons=[],
        started_at="2026-05-16T00:00:00Z",
        completed_at="2026-05-16T00:01:00Z",
        duration_ms=60000,
    )
    d = findings.to_dict()
    assert d["overall"] == "ready_for_council"
    assert d["merge_status"] == "ok"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd lambdas/worker && pytest tests/integrator/test_findings.py -v`
Expected: FAIL — `ModuleNotFoundError: worker.integrator`.

- [ ] **Step 3: Create the integrator package init**

```python
# lambdas/worker/src/worker/integrator/__init__.py
"""Integrator crow — wave-level integration + deterministic checks."""
```

```python
# lambdas/worker/tests/integrator/__init__.py
```

- [ ] **Step 4: Implement findings module**

```python
# lambdas/worker/src/worker/integrator/findings.py
"""IntegratorFindings dataclass + DDB write."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class CheckResult:
    status: Literal["ok", "fail", "timeout", "error", "skipped"]
    failures: list[str]
    duration_ms: int
    command: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "failures": self.failures,
            "duration_ms": self.duration_ms,
            "command": self.command,
        }


@dataclass
class MergeConflict:
    pr_a: int
    pr_b: int
    files: list[str]
    hunks: list[str]
    mvi_a: str
    mvi_b: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "pr_a": self.pr_a,
            "pr_b": self.pr_b,
            "files": self.files,
            "hunks": self.hunks,
            "mvi_a": self.mvi_a,
            "mvi_b": self.mvi_b,
        }


@dataclass
class IntegratorFindings:
    PK: str
    SK: str
    wave_id: str
    pr_numbers: list[int]
    integration_branch: str
    merge_status: Literal["ok", "conflict"]
    merge_conflicts: list[MergeConflict]
    lint: CheckResult | None
    typecheck: CheckResult | None
    tests: CheckResult | None
    worktree_paths: dict[int, str]
    integration_worktree: str
    overall: Literal["ready_for_council", "needs_rework"]
    rework_reasons: list[str]
    started_at: str
    completed_at: str
    duration_ms: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "PK": self.PK,
            "SK": self.SK,
            "wave_id": self.wave_id,
            "pr_numbers": self.pr_numbers,
            "integration_branch": self.integration_branch,
            "merge_status": self.merge_status,
            "merge_conflicts": [c.to_dict() for c in self.merge_conflicts],
            "lint": self.lint.to_dict() if self.lint else None,
            "typecheck": self.typecheck.to_dict() if self.typecheck else None,
            "tests": self.tests.to_dict() if self.tests else None,
            "worktree_paths": {str(k): v for k, v in self.worktree_paths.items()},
            "integration_worktree": self.integration_worktree,
            "overall": self.overall,
            "rework_reasons": self.rework_reasons,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "entityType": "IntegratorFindings",
        }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd lambdas/worker && pytest tests/integrator/test_findings.py -v`
Expected: PASS, 3 tests.

- [ ] **Step 6: Commit**

```bash
git add lambdas/worker/src/worker/integrator/ lambdas/worker/tests/integrator/
git commit -m "feat(integrator): add IntegratorFindings dataclass + serialization"
```

### Task 3: Per-PR worktree setup

**Files:**
- Create: `lambdas/worker/src/worker/integrator/worktree.py`
- Test: `lambdas/worker/tests/integrator/test_worktree.py`

- [ ] **Step 1: Write the failing test**

```python
# lambdas/worker/tests/integrator/test_worktree.py
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from worker.integrator.worktree import (
    add_pr_worktree,
    remove_worktree,
    WorktreeError,
)


def test_add_pr_worktree_calls_git_fetch_then_worktree_add():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
        path = add_pr_worktree(
            repo_path="/mnt/repos/T/t/r",
            pr_number=42,
        )
        assert path == "/mnt/repos/T/t/r/.pr-42"
        # First call fetches the PR ref
        assert "fetch" in mock_run.call_args_list[0].args[0]
        # Second call adds the worktree
        assert "worktree" in mock_run.call_args_list[1].args[0]


def test_add_pr_worktree_raises_on_fetch_failure():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout=b"", stderr=b"auth error")
        with pytest.raises(WorktreeError, match="fetch failed"):
            add_pr_worktree(repo_path="/mnt/repos/T/t/r", pr_number=42)


def test_remove_worktree_calls_git_worktree_remove():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
        remove_worktree(repo_path="/mnt/repos/T/t/r", worktree_path="/mnt/repos/T/t/r/.pr-42")
        assert "remove" in mock_run.call_args.args[0]
        assert "--force" in mock_run.call_args.args[0]


def test_remove_worktree_is_idempotent_on_missing():
    with patch("subprocess.run") as mock_run:
        # Simulate "worktree does not exist" - returncode 1 but harmless
        mock_run.return_value = MagicMock(returncode=1, stdout=b"", stderr=b"not a working tree")
        # Should NOT raise — cleanup must be best-effort
        remove_worktree(repo_path="/mnt/repos/T/t/r", worktree_path="/mnt/repos/T/t/r/.gone")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd lambdas/worker && pytest tests/integrator/test_worktree.py -v`
Expected: FAIL — `ModuleNotFoundError: worker.integrator.worktree`.

- [ ] **Step 3: Implement worktree.py**

```python
# lambdas/worker/src/worker/integrator/worktree.py
"""git worktree setup/cleanup per PR."""

from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger("integrator.worktree")


class WorktreeError(Exception):
    """Raised when a worktree operation fails in a way the caller must handle."""


def add_pr_worktree(repo_path: str, pr_number: int) -> str:
    """Fetch PR head and add a worktree at .pr-{pr_number}.

    Returns the absolute worktree path. Raises WorktreeError on failure.
    """
    pr_ref = f"refs/pull/{pr_number}/head"
    fetch = subprocess.run(
        ["git", "-C", repo_path, "fetch", "origin", pr_ref],
        capture_output=True,
    )
    if fetch.returncode != 0:
        raise WorktreeError(
            f"fetch failed for PR #{pr_number}: {fetch.stderr.decode()[:500]}"
        )

    worktree_path = f"{repo_path}/.pr-{pr_number}"
    add = subprocess.run(
        ["git", "-C", repo_path, "worktree", "add", worktree_path, "FETCH_HEAD"],
        capture_output=True,
    )
    if add.returncode != 0:
        raise WorktreeError(
            f"worktree add failed for PR #{pr_number}: {add.stderr.decode()[:500]}"
        )

    return worktree_path


def remove_worktree(repo_path: str, worktree_path: str) -> None:
    """Best-effort removal. Does NOT raise on failure (cleanup is non-critical)."""
    result = subprocess.run(
        ["git", "-C", repo_path, "worktree", "remove", "--force", worktree_path],
        capture_output=True,
    )
    if result.returncode != 0:
        # Cleanup failures are loud-logged but non-fatal
        logger.error(
            "worktree_remove_failed",
            extra={
                "worktree_path": worktree_path,
                "stderr": result.stderr.decode()[:500],
            },
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd lambdas/worker && pytest tests/integrator/test_worktree.py -v`
Expected: PASS, 4 tests.

- [ ] **Step 5: Commit**

```bash
git add lambdas/worker/src/worker/integrator/worktree.py lambdas/worker/tests/integrator/test_worktree.py
git commit -m "feat(integrator): add per-PR worktree setup + idempotent cleanup"
```

### Task 4: Integration merge

**Files:**
- Create: `lambdas/worker/src/worker/integrator/integration.py`
- Test: `lambdas/worker/tests/integrator/test_integration.py`

- [ ] **Step 1: Write the failing test**

```python
# lambdas/worker/tests/integrator/test_integration.py
import subprocess
from unittest.mock import patch, MagicMock

from worker.integrator.integration import (
    attempt_integration_merge,
    IntegrationResult,
)
from worker.integrator.findings import MergeConflict


def test_attempt_integration_clean_merge_returns_ok():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
        result = attempt_integration_merge(
            repo_path="/mnt/repos/T/t/r",
            integration_branch="council-review-w1",
            pr_to_mvi={42: "m_1", 43: "m_2"},
        )
        assert result.status == "ok"
        assert result.conflicts == []


def test_attempt_integration_with_conflict_captures_files():
    # First merge succeeds, second fails with conflict
    calls = [
        MagicMock(returncode=0, stdout=b"", stderr=b""),  # worktree add integration
        MagicMock(returncode=0, stdout=b"", stderr=b""),  # merge PR 42
        MagicMock(returncode=1, stdout=b"CONFLICT (content): Merge conflict in foo.py\n", stderr=b""),  # merge PR 43
        MagicMock(returncode=0, stdout=b"foo.py", stderr=b""),  # git diff --name-only
        MagicMock(returncode=0, stdout=b"<<<<<<< HEAD\n line\n=======\n line\n>>>>>>>", stderr=b""),  # git diff hunk
        MagicMock(returncode=0, stdout=b"", stderr=b""),  # merge --abort
    ]
    with patch("subprocess.run", side_effect=calls):
        result = attempt_integration_merge(
            repo_path="/mnt/repos/T/t/r",
            integration_branch="council-review-w1",
            pr_to_mvi={42: "m_1", 43: "m_2"},
        )
        assert result.status == "conflict"
        assert len(result.conflicts) == 1
        assert result.conflicts[0].pr_a == 42
        assert result.conflicts[0].pr_b == 43
        assert result.conflicts[0].mvi_a == "m_1"
        assert result.conflicts[0].mvi_b == "m_2"
        assert "foo.py" in result.conflicts[0].files
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd lambdas/worker && pytest tests/integrator/test_integration.py -v`
Expected: FAIL — `ModuleNotFoundError: worker.integrator.integration`.

- [ ] **Step 3: Implement integration.py**

```python
# lambdas/worker/src/worker/integrator/integration.py
"""Integration merge into council-review-{wave_id} branch."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from typing import Literal

from worker.integrator.findings import MergeConflict

logger = logging.getLogger("integrator.integration")


@dataclass
class IntegrationResult:
    status: Literal["ok", "conflict"]
    conflicts: list[MergeConflict] = field(default_factory=list)
    integration_path: str = ""


def attempt_integration_merge(
    repo_path: str,
    integration_branch: str,
    pr_to_mvi: dict[int, str],
) -> IntegrationResult:
    """Merge all PRs into a new integration branch.

    pr_to_mvi maps PR number to the MVI ID that produced it (for conflict routing).
    """
    integration_path = f"{repo_path}/.integration"

    # Create the integration worktree off origin/main
    add_result = subprocess.run(
        ["git", "-C", repo_path, "worktree", "add", "-B", integration_branch,
         integration_path, "origin/main"],
        capture_output=True,
    )
    if add_result.returncode != 0:
        # Treat as conflict-style failure so reactor routes to needs_rework
        return IntegrationResult(
            status="conflict",
            conflicts=[],
            integration_path=integration_path,
        )

    conflicts: list[MergeConflict] = []
    merged_pr_to_mvi: dict[int, str] = {}
    pr_numbers = sorted(pr_to_mvi.keys())

    for pr_number in pr_numbers:
        merge_result = subprocess.run(
            ["git", "-C", integration_path, "merge", "--no-ff", "-m",
             f"Integrate PR #{pr_number}", f"origin/pr-{pr_number}"],
            capture_output=True,
        )
        if merge_result.returncode != 0:
            # Capture conflict files via git diff --name-only --diff-filter=U
            files_result = subprocess.run(
                ["git", "-C", integration_path, "diff", "--name-only", "--diff-filter=U"],
                capture_output=True,
            )
            files = [f for f in files_result.stdout.decode().splitlines() if f]

            # Capture first hunk of first file as evidence
            hunks: list[str] = []
            if files:
                hunk_result = subprocess.run(
                    ["git", "-C", integration_path, "diff", files[0]],
                    capture_output=True,
                )
                hunk_text = hunk_result.stdout.decode()[:500]
                if hunk_text:
                    hunks.append(hunk_text)

            # Pair with the most recently merged PR (the one we conflicted against)
            prior_pr = next(iter(merged_pr_to_mvi.keys()), 0)
            conflicts.append(
                MergeConflict(
                    pr_a=prior_pr,
                    pr_b=pr_number,
                    files=files,
                    hunks=hunks,
                    mvi_a=merged_pr_to_mvi.get(prior_pr, ""),
                    mvi_b=pr_to_mvi[pr_number],
                )
            )

            # Abort and continue to capture more conflicts
            subprocess.run(
                ["git", "-C", integration_path, "merge", "--abort"],
                capture_output=True,
            )
            continue

        merged_pr_to_mvi[pr_number] = pr_to_mvi[pr_number]

    if conflicts:
        return IntegrationResult(
            status="conflict",
            conflicts=conflicts,
            integration_path=integration_path,
        )

    return IntegrationResult(
        status="ok",
        conflicts=[],
        integration_path=integration_path,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd lambdas/worker && pytest tests/integrator/test_integration.py -v`
Expected: PASS, 2 tests.

- [ ] **Step 5: Commit**

```bash
git add lambdas/worker/src/worker/integrator/integration.py lambdas/worker/tests/integrator/test_integration.py
git commit -m "feat(integrator): integration merge with MVI-routed conflict capture"
```

### Task 5: Deterministic check runners (lint)

**Files:**
- Create: `lambdas/worker/src/worker/integrator/checks/__init__.py`
- Create: `lambdas/worker/src/worker/integrator/checks/lint.py`
- Test: `lambdas/worker/tests/integrator/test_checks_lint.py`

- [ ] **Step 1: Write the failing test**

```python
# lambdas/worker/tests/integrator/test_checks_lint.py
from unittest.mock import patch, MagicMock

from worker.integrator.checks.lint import run_lint
from worker.integrator.findings import CheckResult


def test_run_lint_ok_when_black_and_flake8_clean():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
        result = run_lint(integration_path="/mnt/repos/T/t/r/.integration")
        assert result.status == "ok"
        assert result.failures == []


def test_run_lint_fail_when_black_reports_problems():
    calls = [
        MagicMock(returncode=1, stdout=b"would reformat foo.py\nwould reformat bar.py\n", stderr=b""),
        MagicMock(returncode=0, stdout=b"", stderr=b""),
    ]
    with patch("subprocess.run", side_effect=calls):
        result = run_lint(integration_path="/mnt/repos/T/t/r/.integration")
        assert result.status == "fail"
        assert "foo.py" in result.failures[0]


def test_run_lint_skipped_when_tools_missing():
    with patch("subprocess.run", side_effect=FileNotFoundError):
        result = run_lint(integration_path="/mnt/repos/T/t/r/.integration")
        assert result.status == "skipped"


def test_run_lint_timeout_treated_as_failure():
    import subprocess as sp
    with patch("subprocess.run", side_effect=sp.TimeoutExpired(cmd="black", timeout=60)):
        result = run_lint(integration_path="/mnt/repos/T/t/r/.integration")
        assert result.status == "timeout"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd lambdas/worker && pytest tests/integrator/test_checks_lint.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement lint check runner**

```python
# lambdas/worker/src/worker/integrator/checks/__init__.py
"""Deterministic check runners for the Integrator."""
```

```python
# lambdas/worker/src/worker/integrator/checks/lint.py
"""Lint check runner: black --check + flake8."""

from __future__ import annotations

import subprocess
import time

from worker.integrator.findings import CheckResult

LINT_TIMEOUT_SECONDS = 60


def run_lint(integration_path: str) -> CheckResult:
    """Run black --check then flake8 on the integration worktree."""
    start = time.time()
    failures: list[str] = []

    try:
        black = subprocess.run(
            ["black", "--check", "."],
            cwd=integration_path,
            capture_output=True,
            timeout=LINT_TIMEOUT_SECONDS,
        )
        if black.returncode != 0:
            failures.extend(
                line.strip()
                for line in black.stdout.decode().splitlines()[:5]
                if line.strip()
            )
    except FileNotFoundError:
        # black not installed in this project — skip the whole lint phase
        return CheckResult(
            status="skipped",
            failures=[],
            duration_ms=int((time.time() - start) * 1000),
            command="black --check .",
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            status="timeout",
            failures=["black timed out"],
            duration_ms=LINT_TIMEOUT_SECONDS * 1000,
            command="black --check .",
        )

    try:
        flake = subprocess.run(
            ["flake8", "."],
            cwd=integration_path,
            capture_output=True,
            timeout=LINT_TIMEOUT_SECONDS,
        )
        if flake.returncode != 0:
            failures.extend(
                line.strip()
                for line in flake.stdout.decode().splitlines()[:5]
                if line.strip()
            )
    except FileNotFoundError:
        pass  # flake8 not installed — black-only result still counts
    except subprocess.TimeoutExpired:
        return CheckResult(
            status="timeout",
            failures=["flake8 timed out"],
            duration_ms=LINT_TIMEOUT_SECONDS * 1000,
            command="flake8 .",
        )

    duration_ms = int((time.time() - start) * 1000)
    return CheckResult(
        status="fail" if failures else "ok",
        failures=failures,
        duration_ms=duration_ms,
        command="black --check . && flake8 .",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd lambdas/worker && pytest tests/integrator/test_checks_lint.py -v`
Expected: PASS, 4 tests.

- [ ] **Step 5: Commit**

```bash
git add lambdas/worker/src/worker/integrator/checks/ lambdas/worker/tests/integrator/test_checks_lint.py
git commit -m "feat(integrator): lint check runner with timeout + skip-when-missing"
```

### Task 6: Deterministic check runners (typecheck)

**Files:**
- Create: `lambdas/worker/src/worker/integrator/checks/typecheck.py`
- Test: `lambdas/worker/tests/integrator/test_checks_typecheck.py`

- [ ] **Step 1: Write the failing test**

```python
# lambdas/worker/tests/integrator/test_checks_typecheck.py
from unittest.mock import patch, MagicMock

from worker.integrator.checks.typecheck import run_typecheck


def test_run_typecheck_ok_when_mypy_clean():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=b"Success: no issues found", stderr=b"")
        result = run_typecheck(integration_path="/mnt/repos/T/t/r/.integration")
        assert result.status == "ok"


def test_run_typecheck_fail_captures_first_5_errors():
    mypy_output = b"""src/foo.py:10: error: incompatible types
src/bar.py:20: error: missing return type
src/baz.py:5: error: unused import
src/qux.py:100: error: invalid syntax
src/zap.py:1: error: name not found
src/extra.py:99: error: this should not appear
"""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout=mypy_output, stderr=b"")
        result = run_typecheck(integration_path="/mnt/repos/T/t/r/.integration")
        assert result.status == "fail"
        assert len(result.failures) == 5
        assert "extra.py" not in result.failures[-1]


def test_run_typecheck_skipped_when_mypy_missing():
    with patch("subprocess.run", side_effect=FileNotFoundError):
        result = run_typecheck(integration_path="/mnt/repos/T/t/r/.integration")
        assert result.status == "skipped"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd lambdas/worker && pytest tests/integrator/test_checks_typecheck.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement typecheck runner**

```python
# lambdas/worker/src/worker/integrator/checks/typecheck.py
"""Type check runner: mypy."""

from __future__ import annotations

import subprocess
import time

from worker.integrator.findings import CheckResult

TYPECHECK_TIMEOUT_SECONDS = 120


def run_typecheck(integration_path: str) -> CheckResult:
    """Run mypy on the integration worktree."""
    start = time.time()
    try:
        result = subprocess.run(
            ["mypy", "."],
            cwd=integration_path,
            capture_output=True,
            timeout=TYPECHECK_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        return CheckResult(
            status="skipped",
            failures=[],
            duration_ms=int((time.time() - start) * 1000),
            command="mypy .",
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            status="timeout",
            failures=["mypy timed out"],
            duration_ms=TYPECHECK_TIMEOUT_SECONDS * 1000,
            command="mypy .",
        )

    duration_ms = int((time.time() - start) * 1000)
    if result.returncode == 0:
        return CheckResult(status="ok", failures=[], duration_ms=duration_ms, command="mypy .")

    failures = [
        line.strip()
        for line in result.stdout.decode().splitlines()[:5]
        if line.strip() and "error:" in line
    ]
    return CheckResult(
        status="fail",
        failures=failures,
        duration_ms=duration_ms,
        command="mypy .",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd lambdas/worker && pytest tests/integrator/test_checks_typecheck.py -v`
Expected: PASS, 3 tests.

- [ ] **Step 5: Commit**

```bash
git add lambdas/worker/src/worker/integrator/checks/typecheck.py lambdas/worker/tests/integrator/test_checks_typecheck.py
git commit -m "feat(integrator): typecheck runner (mypy) with first-5-errors capture"
```

### Task 7: Deterministic check runners (tests)

**Files:**
- Create: `lambdas/worker/src/worker/integrator/checks/tests.py`
- Test: `lambdas/worker/tests/integrator/test_checks_tests.py`

- [ ] **Step 1: Write the failing test**

```python
# lambdas/worker/tests/integrator/test_checks_tests.py
from unittest.mock import patch, MagicMock

from worker.integrator.checks.tests import run_tests


def test_run_tests_ok_when_pytest_passes():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=b"5 passed", stderr=b"")
        result = run_tests(integration_path="/mnt/repos/T/t/r/.integration")
        assert result.status == "ok"


def test_run_tests_fail_captures_first_5_failures():
    pytest_output = b"""FAILED tests/test_a.py::test_one - AssertionError
FAILED tests/test_a.py::test_two - ValueError
FAILED tests/test_b.py::test_three - KeyError
FAILED tests/test_c.py::test_four - TypeError
FAILED tests/test_d.py::test_five - RuntimeError
FAILED tests/test_e.py::test_six - LookupError
1 passed, 6 failed
"""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout=pytest_output, stderr=b"")
        result = run_tests(integration_path="/mnt/repos/T/t/r/.integration")
        assert result.status == "fail"
        assert len(result.failures) == 5


def test_run_tests_skipped_when_pytest_missing():
    with patch("subprocess.run", side_effect=FileNotFoundError):
        result = run_tests(integration_path="/mnt/repos/T/t/r/.integration")
        assert result.status == "skipped"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd lambdas/worker && pytest tests/integrator/test_checks_tests.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement test runner**

```python
# lambdas/worker/src/worker/integrator/checks/tests.py
"""Tests check runner: pytest."""

from __future__ import annotations

import subprocess
import time

from worker.integrator.findings import CheckResult

TESTS_TIMEOUT_SECONDS = 300


def run_tests(integration_path: str) -> CheckResult:
    """Run pytest on the integration worktree."""
    start = time.time()
    try:
        result = subprocess.run(
            ["pytest", "--tb=short", "-q"],
            cwd=integration_path,
            capture_output=True,
            timeout=TESTS_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        return CheckResult(
            status="skipped",
            failures=[],
            duration_ms=int((time.time() - start) * 1000),
            command="pytest --tb=short -q",
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            status="timeout",
            failures=["pytest timed out — split into smaller suites or raise timeout"],
            duration_ms=TESTS_TIMEOUT_SECONDS * 1000,
            command="pytest --tb=short -q",
        )

    duration_ms = int((time.time() - start) * 1000)
    if result.returncode == 0:
        return CheckResult(status="ok", failures=[], duration_ms=duration_ms, command="pytest --tb=short -q")

    failures = [
        line.strip()
        for line in result.stdout.decode().splitlines()[:50]
        if line.strip().startswith("FAILED")
    ][:5]
    return CheckResult(
        status="fail",
        failures=failures,
        duration_ms=duration_ms,
        command="pytest --tb=short -q",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd lambdas/worker && pytest tests/integrator/test_checks_tests.py -v`
Expected: PASS, 3 tests.

- [ ] **Step 5: Commit**

```bash
git add lambdas/worker/src/worker/integrator/checks/tests.py lambdas/worker/tests/integrator/test_checks_tests.py
git commit -m "feat(integrator): pytest runner with first-5-failures capture"
```

### Task 8: Check orchestration runner

**Files:**
- Create: `lambdas/worker/src/worker/integrator/checks/runner.py`
- Test: `lambdas/worker/tests/integrator/test_checks_runner.py`

- [ ] **Step 1: Write the failing test**

```python
# lambdas/worker/tests/integrator/test_checks_runner.py
from unittest.mock import patch

from worker.integrator.checks.runner import run_all_checks
from worker.integrator.findings import CheckResult


def test_run_all_checks_returns_three_results():
    ok = CheckResult(status="ok", failures=[], duration_ms=10, command="x")
    with patch("worker.integrator.checks.runner.run_lint", return_value=ok), \
         patch("worker.integrator.checks.runner.run_typecheck", return_value=ok), \
         patch("worker.integrator.checks.runner.run_tests", return_value=ok):
        lint, typecheck, tests = run_all_checks("/integration")
        assert lint.status == "ok"
        assert typecheck.status == "ok"
        assert tests.status == "ok"


def test_run_all_checks_aggregates_overall_ok_when_all_pass_or_skip():
    from worker.integrator.checks.runner import overall_from_checks
    ok = CheckResult(status="ok", failures=[], duration_ms=10, command="x")
    skipped = CheckResult(status="skipped", failures=[], duration_ms=0, command="y")
    overall, reasons = overall_from_checks(ok, skipped, ok)
    assert overall == "ready_for_council"
    assert reasons == []


def test_run_all_checks_aggregates_overall_needs_rework_on_any_fail():
    from worker.integrator.checks.runner import overall_from_checks
    ok = CheckResult(status="ok", failures=[], duration_ms=10, command="x")
    fail = CheckResult(
        status="fail",
        failures=["foo.py:1: error: bad"],
        duration_ms=5,
        command="mypy .",
    )
    overall, reasons = overall_from_checks(ok, fail, ok)
    assert overall == "needs_rework"
    assert any("typecheck" in r for r in reasons)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd lambdas/worker && pytest tests/integrator/test_checks_runner.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement runner**

```python
# lambdas/worker/src/worker/integrator/checks/runner.py
"""Orchestrates all deterministic checks and aggregates overall verdict."""

from __future__ import annotations

from typing import Literal

from worker.integrator.checks.lint import run_lint
from worker.integrator.checks.tests import run_tests
from worker.integrator.checks.typecheck import run_typecheck
from worker.integrator.findings import CheckResult


def run_all_checks(integration_path: str) -> tuple[CheckResult, CheckResult, CheckResult]:
    """Run lint, typecheck, tests in sequence. Returns (lint, typecheck, tests)."""
    return (
        run_lint(integration_path),
        run_typecheck(integration_path),
        run_tests(integration_path),
    )


def overall_from_checks(
    lint: CheckResult,
    typecheck: CheckResult,
    tests: CheckResult,
) -> tuple[Literal["ready_for_council", "needs_rework"], list[str]]:
    """Aggregate the three check results into an overall verdict + reasons."""
    failed_checks: list[tuple[str, CheckResult]] = []
    for name, result in [("lint", lint), ("typecheck", typecheck), ("tests", tests)]:
        if result.status in ("fail", "timeout", "error"):
            failed_checks.append((name, result))

    if not failed_checks:
        return "ready_for_council", []

    reasons: list[str] = []
    for name, result in failed_checks:
        if result.status == "timeout":
            reasons.append(f"{name} timed out after {result.duration_ms // 1000}s")
        elif result.status == "error":
            reasons.append(f"{name} errored: {result.failures[0] if result.failures else 'unknown'}")
        else:
            top_failures = "; ".join(result.failures[:3])
            reasons.append(f"{name} failed: {top_failures}")

    return "needs_rework", reasons
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd lambdas/worker && pytest tests/integrator/test_checks_runner.py -v`
Expected: PASS, 3 tests.

- [ ] **Step 5: Commit**

```bash
git add lambdas/worker/src/worker/integrator/checks/runner.py lambdas/worker/tests/integrator/test_checks_runner.py
git commit -m "feat(integrator): check orchestration + overall-verdict aggregation"
```

### Task 9: Loud-failure event helper

**Files:**
- Create: `lambdas/worker/src/worker/integrator/events.py`
- Test: `lambdas/worker/tests/integrator/test_events.py`

- [ ] **Step 1: Write the failing test**

```python
# lambdas/worker/tests/integrator/test_events.py
from unittest.mock import MagicMock

from worker.integrator.events import emit_pipeline_error


def test_emit_pipeline_error_writes_to_events_table_and_logs():
    blackboard = MagicMock()
    emit_pipeline_error(
        blackboard=blackboard,
        project_id="p1",
        wave_id="w1",
        phase="integrator-fetch",
        error_class="WorktreeError",
        error_message="fetch failed for PR #42",
        traceback_head="Traceback...\n  ...",
        retry_count=2,
        final=True,
    )
    assert blackboard.write_event.called
    args = blackboard.write_event.call_args
    event_item = args.kwargs["event_item"] if "event_item" in args.kwargs else args.args[0]
    assert event_item["event_type"] == "council_pipeline_error"
    assert event_item["phase"] == "integrator-fetch"
    assert event_item["final"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd lambdas/worker && pytest tests/integrator/test_events.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement events.py**

```python
# lambdas/worker/src/worker/integrator/events.py
"""Loud-failure event emission helper."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("integrator.events")


def emit_pipeline_error(
    blackboard: Any,
    project_id: str,
    wave_id: str,
    phase: str,
    error_class: str,
    error_message: str,
    traceback_head: str = "",
    session_id: str | None = None,
    retry_count: int = 0,
    final: bool = False,
) -> None:
    """Emit a council_pipeline_error event AND log at ERROR with structured JSON."""
    now = datetime.now(timezone.utc).isoformat()
    event_id = uuid.uuid4().hex[:12]
    event_item = {
        "PK": f"P#{project_id}",
        "SK": f"E#{now}#{event_id}",
        "event_type": "council_pipeline_error",
        "phase": phase,
        "error_class": error_class,
        "error_message": error_message[:1000],
        "traceback_head": traceback_head[:1000],
        "wave_id": wave_id,
        "session_id": session_id,
        "retry_count": retry_count,
        "final": final,
        "created_at": now,
        # Events table TTL is expires_at (per existing infra) — 24h from now in epoch seconds
        "expires_at": int(datetime.now(timezone.utc).timestamp()) + 86400,
    }
    blackboard.write_event(event_item=event_item)
    logger.error(
        json.dumps(
            {
                "event": "council_pipeline_error",
                "phase": phase,
                "wave_id": wave_id,
                "session_id": session_id,
                "error_class": error_class,
                "error_message": error_message[:200],
                "retry_count": retry_count,
                "final": final,
            }
        )
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd lambdas/worker && pytest tests/integrator/test_events.py -v`
Expected: PASS, 1 test.

- [ ] **Step 5: Commit**

```bash
git add lambdas/worker/src/worker/integrator/events.py lambdas/worker/tests/integrator/test_events.py
git commit -m "feat(integrator): loud-failure pipeline_error emission helper"
```

### Task 10: Integrator handler — wire all phases together

**Files:**
- Create: `lambdas/worker/src/worker/integrator/handler.py`
- Test: `lambdas/worker/tests/integrator/test_handler.py`

- [ ] **Step 1: Write the failing test**

```python
# lambdas/worker/tests/integrator/test_handler.py
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from worker.integrator.findings import CheckResult, IntegrationResult, MergeConflict
from worker.integrator.handler import run_integrator


def _ok_result():
    return CheckResult(status="ok", failures=[], duration_ms=10, command="x")


def test_run_integrator_happy_path_writes_findings_ready_for_council():
    blackboard = MagicMock()
    with patch("worker.integrator.handler.add_pr_worktree", return_value="/mnt/repos/T/t/r/.pr-42"), \
         patch("worker.integrator.handler.attempt_integration_merge") as merge, \
         patch("worker.integrator.handler.run_all_checks", return_value=(_ok_result(), _ok_result(), _ok_result())), \
         patch("worker.integrator.handler.remove_worktree"):
        merge.return_value = MagicMock(status="ok", conflicts=[], integration_path="/mnt/repos/T/t/r/.integration")
        run_integrator(
            blackboard=blackboard,
            project_id="p1",
            wave_id="w1",
            repo_path="/mnt/repos/T/t/r",
            pr_to_mvi={42: "m_1"},
        )
        # Findings written exactly once
        assert blackboard.write_item.called
        written = blackboard.write_item.call_args.args[0]
        assert written["SK"] == "INTEGRATION#w1"
        assert written["overall"] == "ready_for_council"


def test_run_integrator_conflict_skips_checks_and_writes_needs_rework():
    blackboard = MagicMock()
    conflict = MergeConflict(pr_a=42, pr_b=43, files=["foo.py"], hunks=[], mvi_a="m1", mvi_b="m2")
    with patch("worker.integrator.handler.add_pr_worktree", return_value="/mnt/repos/T/t/r/.pr-42"), \
         patch("worker.integrator.handler.attempt_integration_merge") as merge, \
         patch("worker.integrator.handler.run_all_checks") as checks, \
         patch("worker.integrator.handler.remove_worktree"):
        merge.return_value = MagicMock(status="conflict", conflicts=[conflict], integration_path="/.integration")
        run_integrator(
            blackboard=blackboard,
            project_id="p1",
            wave_id="w1",
            repo_path="/mnt/repos/T/t/r",
            pr_to_mvi={42: "m1", 43: "m2"},
        )
        # Checks NOT run on conflict
        checks.assert_not_called()
        written = blackboard.write_item.call_args.args[0]
        assert written["overall"] == "needs_rework"
        assert written["merge_status"] == "conflict"


def test_run_integrator_emits_pipeline_error_on_fetch_failure():
    from worker.integrator.worktree import WorktreeError
    blackboard = MagicMock()
    with patch("worker.integrator.handler.add_pr_worktree", side_effect=WorktreeError("fetch failed")):
        run_integrator(
            blackboard=blackboard,
            project_id="p1",
            wave_id="w1",
            repo_path="/mnt/repos/T/t/r",
            pr_to_mvi={42: "m_1"},
        )
        # Loud failure event was emitted
        assert blackboard.write_event.called
        # Findings still written (so reactor can route to needs_rework)
        written = blackboard.write_item.call_args.args[0]
        assert written["overall"] == "needs_rework"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd lambdas/worker && pytest tests/integrator/test_handler.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement handler**

```python
# lambdas/worker/src/worker/integrator/handler.py
"""Integrator entry: orchestrate worktree setup → merge → checks → findings."""

from __future__ import annotations

import logging
import time
import traceback
from datetime import datetime, timezone
from typing import Any

from worker.integrator.checks.runner import overall_from_checks, run_all_checks
from worker.integrator.events import emit_pipeline_error
from worker.integrator.findings import IntegratorFindings
from worker.integrator.integration import attempt_integration_merge
from worker.integrator.worktree import WorktreeError, add_pr_worktree, remove_worktree

logger = logging.getLogger("integrator.handler")


def run_integrator(
    blackboard: Any,
    project_id: str,
    wave_id: str,
    repo_path: str,
    pr_to_mvi: dict[int, str],
) -> None:
    """Run the full integrator flow for a wave.

    Always writes an IntegratorFindings record to DDB so the Murder reactor
    has something to route on, even on failure paths.
    """
    started_at = datetime.now(timezone.utc).isoformat()
    start = time.time()
    integration_branch = f"council-review-{wave_id}"
    worktree_paths: dict[int, str] = {}
    integration_path = f"{repo_path}/.integration"

    # Phase A — per-PR worktrees
    fetch_error: WorktreeError | None = None
    try:
        for pr_number in sorted(pr_to_mvi.keys()):
            worktree_paths[pr_number] = add_pr_worktree(repo_path, pr_number)
    except WorktreeError as e:
        fetch_error = e
        emit_pipeline_error(
            blackboard=blackboard,
            project_id=project_id,
            wave_id=wave_id,
            phase="integrator-fetch",
            error_class=type(e).__name__,
            error_message=str(e),
            traceback_head=traceback.format_exc()[:1000],
            retry_count=0,
            final=True,
        )

    findings = IntegratorFindings(
        PK=f"P#{project_id}",
        SK=f"INTEGRATION#{wave_id}",
        wave_id=wave_id,
        pr_numbers=sorted(pr_to_mvi.keys()),
        integration_branch=integration_branch,
        merge_status="conflict",
        merge_conflicts=[],
        lint=None,
        typecheck=None,
        tests=None,
        worktree_paths=worktree_paths,
        integration_worktree=integration_path,
        overall="needs_rework",
        rework_reasons=[],
        started_at=started_at,
        completed_at="",
        duration_ms=0,
    )

    if fetch_error:
        findings.rework_reasons = [f"unable to fetch PRs: {fetch_error}"]
        _finalize_and_write(blackboard, findings, start)
        return

    # Phase B — integration merge
    try:
        merge_result = attempt_integration_merge(
            repo_path=repo_path,
            integration_branch=integration_branch,
            pr_to_mvi=pr_to_mvi,
        )
    except Exception as e:  # noqa: BLE001 — loud-fail catch
        emit_pipeline_error(
            blackboard=blackboard,
            project_id=project_id,
            wave_id=wave_id,
            phase="integrator-merge",
            error_class=type(e).__name__,
            error_message=str(e),
            traceback_head=traceback.format_exc()[:1000],
            final=True,
        )
        findings.rework_reasons = [f"merge phase crashed: {type(e).__name__}"]
        _finalize_and_write(blackboard, findings, start)
        _cleanup(repo_path, worktree_paths, integration_path)
        return

    findings.merge_status = merge_result.status
    findings.merge_conflicts = merge_result.conflicts
    findings.integration_worktree = merge_result.integration_path

    if merge_result.status == "conflict":
        findings.overall = "needs_rework"
        findings.rework_reasons = [
            f"merge conflict between PR #{c.pr_a} and PR #{c.pr_b} ({len(c.files)} files)"
            for c in merge_result.conflicts
        ]
        _finalize_and_write(blackboard, findings, start)
        _cleanup(repo_path, worktree_paths, integration_path)
        return

    # Phase C — deterministic checks
    try:
        lint, typecheck, tests = run_all_checks(merge_result.integration_path)
    except Exception as e:  # noqa: BLE001
        emit_pipeline_error(
            blackboard=blackboard,
            project_id=project_id,
            wave_id=wave_id,
            phase="integrator-checks",
            error_class=type(e).__name__,
            error_message=str(e),
            traceback_head=traceback.format_exc()[:1000],
            final=True,
        )
        findings.rework_reasons = [f"check phase crashed: {type(e).__name__}"]
        _finalize_and_write(blackboard, findings, start)
        _cleanup(repo_path, worktree_paths, integration_path)
        return

    findings.lint = lint
    findings.typecheck = typecheck
    findings.tests = tests
    overall, reasons = overall_from_checks(lint, typecheck, tests)
    findings.overall = overall
    findings.rework_reasons = reasons

    _finalize_and_write(blackboard, findings, start)
    _cleanup(repo_path, worktree_paths, integration_path)


def _finalize_and_write(blackboard: Any, findings: IntegratorFindings, start: float) -> None:
    findings.completed_at = datetime.now(timezone.utc).isoformat()
    findings.duration_ms = int((time.time() - start) * 1000)
    blackboard.write_item(findings.to_dict())


def _cleanup(repo_path: str, worktree_paths: dict[int, str], integration_path: str) -> None:
    for path in worktree_paths.values():
        remove_worktree(repo_path, path)
    remove_worktree(repo_path, integration_path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd lambdas/worker && pytest tests/integrator/test_handler.py -v`
Expected: PASS, 3 tests.

- [ ] **Step 5: Commit**

```bash
git add lambdas/worker/src/worker/integrator/handler.py lambdas/worker/tests/integrator/test_handler.py
git commit -m "feat(integrator): wire phases A/B/C + loud-failure handling in handler"
```

### Task 11: Worker dispatch on crow_kind=integrator

**Files:**
- Modify: `lambdas/worker/src/worker/handler.py`
- Modify: `lambdas/worker/tests/test_handler.py` (or add a new test file if none)

- [ ] **Step 1: Inspect existing worker handler to locate dispatch point**

Run: `grep -n "crow_kind\|def lambda_handler\|def _dispatch\|def _run_crow" lambdas/worker/src/worker/handler.py | head -20`

Locate the dispatch — there will be an if/elif chain that picks based on `crow_kind`. Note the existing pattern.

- [ ] **Step 2: Write the failing test**

```python
# lambdas/worker/tests/test_handler_integrator_dispatch.py
from unittest.mock import patch, MagicMock

from worker.handler import dispatch_crow  # adjust import to match existing function name


def test_dispatch_crow_routes_integrator_to_run_integrator():
    with patch("worker.handler.run_integrator") as mock_run:
        task = {
            "crow_kind": "integrator",
            "wave_id": "w1",
            "project_id": "p1",
            "repo_path": "/mnt/repos/T/t/r",
            "pr_to_mvi": {"42": "m1", "43": "m2"},
        }
        dispatch_crow(task=task, blackboard=MagicMock())
        assert mock_run.called
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["wave_id"] == "w1"
        assert call_kwargs["pr_to_mvi"] == {42: "m1", 43: "m2"}  # str keys → int
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd lambdas/worker && pytest tests/test_handler_integrator_dispatch.py -v`
Expected: FAIL — no integrator branch yet.

- [ ] **Step 4: Add the integrator branch to existing dispatch**

Open `lambdas/worker/src/worker/handler.py`. Find the dispatch function (whatever it's called locally — likely `dispatch_crow`, `_run_crow`, or a `match` block). Add:

```python
from worker.integrator.handler import run_integrator

# ...inside the dispatch:
if task["crow_kind"] == "integrator":
    return run_integrator(
        blackboard=blackboard,
        project_id=task["project_id"],
        wave_id=task["wave_id"],
        repo_path=task["repo_path"],
        pr_to_mvi={int(k): v for k, v in task.get("pr_to_mvi", {}).items()},
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd lambdas/worker && pytest tests/test_handler_integrator_dispatch.py tests/integrator/ -v`
Expected: PASS, all tests including the integrator suite.

- [ ] **Step 6: Commit**

```bash
git add lambdas/worker/src/worker/handler.py lambdas/worker/tests/test_handler_integrator_dispatch.py
git commit -m "feat(worker): dispatch crow_kind=integrator to integrator subpackage"
```

### Task 12: Murder reactor — handle wave ready for review

**Files:**
- Modify: `lambdas/murder/src/murder/reactor.py`
- Modify: `lambdas/murder/tests/test_reactor.py` (add new test class)

- [ ] **Step 1: Write the failing test**

```python
# lambdas/murder/tests/test_reactor.py — add inside the existing file
class TestHandleWaveReviewReady:
    def test_all_mvis_ready_writes_integrator_task_and_transitions_wave(
        self, blackboard, logger
    ):
        # Setup: wave with 2 MVIs, both ready_to_ship
        blackboard.write_item({"PK": "P#p1", "SK": "S#w1", "level": "wave",
                               "status": "review", "wave_id": "w1"})
        blackboard.write_item({"PK": "P#p1", "SK": "S#w1#m_1", "level": "murder",
                               "status": "ready_to_ship", "pr_number": 42, "mvi_id": "m_1"})
        blackboard.write_item({"PK": "P#p1", "SK": "S#w1#m_2", "level": "murder",
                               "status": "ready_to_ship", "pr_number": 43, "mvi_id": "m_2"})

        from murder.reactor import _maybe_start_integrator
        _maybe_start_integrator(
            blackboard=blackboard,
            pk="P#p1",
            wave_id="w1",
            logger=logger,
        )

        # Wave transitions to integrating
        wave = blackboard.read("P#p1", "S#w1")
        assert wave["status"] == "integrating"

        # Integrator task written
        task = blackboard.read("P#p1", "S#w1/integrator-task")
        assert task is not None
        assert task["crow_kind"] == "integrator"
        assert task["pr_to_mvi"] == {"42": "m_1", "43": "m_2"}

    def test_not_all_mvis_ready_does_nothing(self, blackboard, logger):
        blackboard.write_item({"PK": "P#p1", "SK": "S#w2", "level": "wave",
                               "status": "review", "wave_id": "w2"})
        blackboard.write_item({"PK": "P#p1", "SK": "S#w2#m_1", "level": "murder",
                               "status": "ready_to_ship", "pr_number": 42})
        blackboard.write_item({"PK": "P#p1", "SK": "S#w2#m_2", "level": "murder",
                               "status": "executing"})

        from murder.reactor import _maybe_start_integrator
        _maybe_start_integrator(
            blackboard=blackboard,
            pk="P#p1",
            wave_id="w2",
            logger=logger,
        )

        wave = blackboard.read("P#p1", "S#w2")
        assert wave["status"] == "review"
        assert blackboard.read("P#p1", "S#w2/integrator-task") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd lambdas/murder && pytest tests/test_reactor.py::TestHandleWaveReviewReady -v`
Expected: FAIL — `_maybe_start_integrator` does not exist.

- [ ] **Step 3: Implement `_maybe_start_integrator` in reactor.py**

Add to `lambdas/murder/src/murder/reactor.py` (place near `_trigger_council_review` around line 961):

```python
def _maybe_start_integrator(
    blackboard: Blackboard,
    pk: str,
    wave_id: str,
    logger: StructuredLogger,
) -> None:
    """If all MVIs in the wave are ready_to_ship, transition wave to integrating
    and write an integrator task for the Worker."""
    mvis = blackboard.query(pk, f"S#{wave_id}#m")
    if not mvis:
        return

    not_ready = [m for m in mvis if m.get("status") != "ready_to_ship"]
    if not_ready:
        return

    pr_to_mvi: dict[str, str] = {}
    for mvi in mvis:
        pr_number = mvi.get("pr_number")
        mvi_id = mvi.get("mvi_id") or mvi["SK"].split("#m")[-1].split("#")[0]
        if pr_number is not None:
            pr_to_mvi[str(pr_number)] = mvi_id

    if not pr_to_mvi:
        return

    # Transition wave → integrating
    blackboard.update_item(
        pk=pk,
        sk=f"S#{wave_id}",
        updates={"status": "integrating"},
    )

    # Resolve repo_path from project metadata
    project = blackboard.read(pk, "META")
    repo_path = project.get("repo_path", f"/mnt/repos{pk.replace('P#', '/T/')}/repo") if project else ""

    # Write integrator task
    blackboard.write_item({
        "PK": pk,
        "SK": f"S#{wave_id}/integrator-task",
        "level": "wave",
        "entityType": "CrowTask",
        "crow_kind": "integrator",
        "wave_id": wave_id,
        "project_id": pk.replace("P#", ""),
        "repo_path": repo_path,
        "pr_to_mvi": pr_to_mvi,
        "claimed": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    logger.event(
        "integrator_dispatched",
        wave_id=wave_id,
        pr_count=len(pr_to_mvi),
    )
```

- [ ] **Step 4: Wire into the existing `_handle_mvi_ready`**

Find `_handle_mvi_ready` (around line 337). At the end of the function, after the existing logic that may transition to `review`, add:

```python
# If all MVIs are ready_to_ship, start the integrator
if root and root.get("status") in ("review", "executing"):
    _maybe_start_integrator(
        blackboard=blackboard,
        pk=pk,
        wave_id=wave_id,
        logger=logger,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd lambdas/murder && pytest tests/test_reactor.py::TestHandleWaveReviewReady -v`
Expected: PASS, 2 tests.

Then run the full reactor suite to ensure no regressions:
Run: `cd lambdas/murder && pytest tests/test_reactor.py -v`
Expected: PASS, all tests.

- [ ] **Step 6: Commit**

```bash
git add lambdas/murder/src/murder/reactor.py lambdas/murder/tests/test_reactor.py
git commit -m "feat(murder): dispatch integrator when all MVIs reach ready_to_ship"
```

### Task 13: Murder reactor — handle integration complete

**Files:**
- Modify: `lambdas/murder/src/murder/reactor.py`
- Modify: `lambdas/murder/src/murder/handler.py` (Stream dispatch wiring)
- Modify: `lambdas/murder/tests/test_reactor.py`

- [ ] **Step 1: Write the failing test**

```python
# lambdas/murder/tests/test_reactor.py — add new class
class TestHandleIntegrationComplete:
    def test_ready_for_council_writes_council_task_and_transitions_wave(
        self, blackboard, logger
    ):
        blackboard.write_item({"PK": "P#p1", "SK": "S#w1", "level": "wave",
                               "status": "integrating", "wave_id": "w1",
                               "auto_mode": "on"})

        findings = {
            "PK": "P#p1",
            "SK": "INTEGRATION#w1",
            "wave_id": "w1",
            "overall": "ready_for_council",
            "merge_status": "ok",
            "rework_reasons": [],
        }

        from murder.reactor import react_to_integration_complete
        react_to_integration_complete(
            blackboard=blackboard,
            findings=findings,
            logger=logger,
        )

        wave = blackboard.read("P#p1", "S#w1")
        assert wave["status"] == "under_council_review"

        # COUNCIL# row was written
        sessions = blackboard.query("P#p1", "COUNCIL#")
        assert len(sessions) == 1
        assert sessions[0]["status"] == "pending"
        assert sessions[0]["wave_id"] == "w1"
        assert sessions[0]["integration_sk"] == "INTEGRATION#w1"

    def test_needs_rework_dispatches_fixers_per_affected_mvi(
        self, blackboard, logger
    ):
        blackboard.write_item({"PK": "P#p1", "SK": "S#w1", "level": "wave",
                               "status": "integrating", "wave_id": "w1"})
        blackboard.write_item({"PK": "P#p1", "SK": "S#w1#m_1", "level": "murder",
                               "status": "ready_to_ship", "mvi_id": "m_1"})
        blackboard.write_item({"PK": "P#p1", "SK": "S#w1#m_2", "level": "murder",
                               "status": "ready_to_ship", "mvi_id": "m_2"})

        findings = {
            "PK": "P#p1",
            "SK": "INTEGRATION#w1",
            "wave_id": "w1",
            "overall": "needs_rework",
            "merge_status": "conflict",
            "rework_reasons": ["merge conflict between PR #42 and PR #43 (1 files)"],
            "merge_conflicts": [{"pr_a": 42, "pr_b": 43, "mvi_a": "m_1", "mvi_b": "m_2",
                                 "files": ["foo.py"], "hunks": []}],
        }

        from murder.reactor import react_to_integration_complete
        react_to_integration_complete(
            blackboard=blackboard,
            findings=findings,
            logger=logger,
        )

        wave = blackboard.read("P#p1", "S#w1")
        # Wave returned to executing so fixers can run
        assert wave["status"] == "executing"

        # Both MVIs that conflicted got their status flipped back to executing
        mvi_1 = blackboard.read("P#p1", "S#w1#m_1")
        mvi_2 = blackboard.read("P#p1", "S#w1#m_2")
        assert mvi_1["status"] == "executing"
        assert mvi_2["status"] == "executing"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd lambdas/murder && pytest tests/test_reactor.py::TestHandleIntegrationComplete -v`
Expected: FAIL — `react_to_integration_complete` does not exist.

- [ ] **Step 3: Implement `react_to_integration_complete`**

Add to `lambdas/murder/src/murder/reactor.py`:

```python
def react_to_integration_complete(
    blackboard: Blackboard,
    findings: dict[str, Any],
    logger: StructuredLogger,
) -> None:
    """Route on IntegratorFindings.overall: ready_for_council or needs_rework."""
    pk = findings["PK"]
    wave_id = findings["wave_id"]
    overall = findings["overall"]

    if overall == "ready_for_council":
        # Transition wave → under_council_review
        blackboard.update_item(
            pk=pk,
            sk=f"S#{wave_id}",
            updates={"status": "under_council_review"},
        )

        session_id = f"wr_{wave_id}_{uuid.uuid4().hex[:8]}"
        blackboard.write_item({
            "PK": pk,
            "SK": f"COUNCIL#{session_id}",
            "level": "council",
            "status": "pending",
            "type": "wave_review",
            "wave_id": wave_id,
            "integration_sk": findings["SK"],
            "auto_mode": "off",  # M3 will wire auto_mode from wave root
            "created_at": datetime.now(timezone.utc).isoformat(),
            "entityType": "CouncilSession",
        })

        logger.event(
            "council_session_created",
            wave_id=wave_id,
            session_id=session_id,
        )
        return

    if overall == "needs_rework":
        # Transition wave back to executing
        blackboard.update_item(
            pk=pk,
            sk=f"S#{wave_id}",
            updates={"status": "executing"},
        )

        # For each conflict, flip both MVIs back to executing so fixers pick them up
        affected_mvi_ids: set[str] = set()
        for conflict in findings.get("merge_conflicts", []):
            if conflict.get("mvi_a"):
                affected_mvi_ids.add(conflict["mvi_a"])
            if conflict.get("mvi_b"):
                affected_mvi_ids.add(conflict["mvi_b"])

        for mvi_id in affected_mvi_ids:
            blackboard.update_item(
                pk=pk,
                sk=f"S#{wave_id}#m{mvi_id}",
                updates={
                    "status": "executing",
                    "rework_reason": "merge conflict",
                },
            )

        logger.event(
            "wave_needs_rework",
            wave_id=wave_id,
            affected_mvi_count=len(affected_mvi_ids),
            reasons=findings.get("rework_reasons", []),
        )
```

- [ ] **Step 4: Wire INTEGRATION# Stream inserts into the handler**

Open `lambdas/murder/src/murder/handler.py`. Find the dispatch switch on stream records. Add a branch for `SK begins with INTEGRATION#`:

```python
# Inside the stream-record dispatch:
elif sk.startswith("INTEGRATION#") and event_name == "INSERT":
    react_to_integration_complete(
        blackboard=blackboard,
        findings=new_image,
        logger=logger,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd lambdas/murder && pytest tests/test_reactor.py::TestHandleIntegrationComplete -v`
Expected: PASS, 2 tests.

Run the full reactor + handler test suites:
Run: `cd lambdas/murder && pytest tests/ -v`
Expected: PASS, all tests.

- [ ] **Step 6: Commit**

```bash
git add lambdas/murder/src/murder/reactor.py lambdas/murder/src/murder/handler.py lambdas/murder/tests/test_reactor.py
git commit -m "feat(murder): route INTEGRATION# results to council or fixer dispatch"
```

### Task 14: M1 integration test — end-to-end against moto DDB

**Files:**
- Create: `tests/integration/test_stage4_m1.py` (new directory if missing)

- [ ] **Step 1: Set up integration test directory + conftest**

```python
# tests/integration/__init__.py
```

```python
# tests/integration/conftest.py
"""Shared fixtures for Stage 4 integration tests."""

import os
import pytest


@pytest.fixture(autouse=True)
def aws_creds():
    """Moto needs these to refuse to talk to real AWS."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
```

- [ ] **Step 2: Write the failing integration test**

```python
# tests/integration/test_stage4_m1.py
"""Stage 4 M1 integration: integrator + Murder reactor end-to-end."""

import pytest
from unittest.mock import patch
import boto3
from moto import mock_aws


@mock_aws
def test_m1_conflict_path_routes_wave_back_to_executing():
    """When Integrator finds a merge conflict, Murder reactor flips affected MVIs
    back to executing so fixer crows can take over."""
    # Setup moto DDB table matching production schema
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.create_table(
        TableName="cawnex-test",
        KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"},
                   {"AttributeName": "SK", "KeyType": "RANGE"}],
        AttributeDefinitions=[{"AttributeName": "PK", "AttributeType": "S"},
                              {"AttributeName": "SK", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Seed: wave + 2 MVIs both ready_to_ship
    table.put_item(Item={"PK": "P#p1", "SK": "S#w1", "level": "wave",
                         "status": "review", "wave_id": "w1"})
    table.put_item(Item={"PK": "P#p1", "SK": "S#w1#m_1", "level": "murder",
                         "status": "ready_to_ship", "pr_number": 42, "mvi_id": "m_1"})
    table.put_item(Item={"PK": "P#p1", "SK": "S#w1#m_2", "level": "murder",
                         "status": "ready_to_ship", "pr_number": 43, "mvi_id": "m_2"})
    table.put_item(Item={"PK": "P#p1", "SK": "META",
                         "repo_path": "/mnt/repos/T/dev-tenant/repo"})

    # Simulate Murder reactor triggering integrator
    from murder.blackboard import Blackboard
    from murder.logging import StructuredLogger
    from murder.reactor import _maybe_start_integrator

    blackboard = Blackboard(table_name="cawnex-test", events_table_name="cawnex-events-test")
    logger = StructuredLogger("test")
    _maybe_start_integrator(
        blackboard=blackboard,
        pk="P#p1",
        wave_id="w1",
        logger=logger,
    )

    # Integrator task is written
    task = blackboard.read("P#p1", "S#w1/integrator-task")
    assert task is not None
    assert task["crow_kind"] == "integrator"
    assert blackboard.read("P#p1", "S#w1")["status"] == "integrating"

    # Simulate Integrator running and writing IntegratorFindings with conflict
    findings = {
        "PK": "P#p1",
        "SK": "INTEGRATION#w1",
        "wave_id": "w1",
        "overall": "needs_rework",
        "merge_status": "conflict",
        "rework_reasons": ["merge conflict between PR #42 and PR #43"],
        "merge_conflicts": [{"pr_a": 42, "pr_b": 43, "mvi_a": "m_1", "mvi_b": "m_2",
                             "files": ["foo.py"], "hunks": []}],
    }
    blackboard.write_item(findings)

    # Simulate stream event triggering react_to_integration_complete
    from murder.reactor import react_to_integration_complete
    react_to_integration_complete(blackboard=blackboard, findings=findings, logger=logger)

    # Both affected MVIs are back to executing
    assert blackboard.read("P#p1", "S#w1#m_1")["status"] == "executing"
    assert blackboard.read("P#p1", "S#w1#m_2")["status"] == "executing"
    # Wave is back to executing
    assert blackboard.read("P#p1", "S#w1")["status"] == "executing"
```

- [ ] **Step 3: Run the integration test**

Run: `pytest tests/integration/test_stage4_m1.py -v`
Expected: PASS.

If the test fails because of `Blackboard` import or table name issues, fix the imports — do not skip the test.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/
git commit -m "test(integration): M1 conflict-path routes wave back to executing"
```

### M1 wrap-up: run full suite + tag completion

- [ ] **Step 1: Run all tests across all packages**

```bash
pytest lambdas/worker/tests/integrator/ -v
pytest lambdas/murder/tests/ -v
pytest tests/integration/ -v
```

Expected: all pass.

- [ ] **Step 2: Manual sanity check — make sure new code is importable from worker entry**

```bash
cd lambdas/worker
python -c "from worker.integrator.handler import run_integrator; print('OK')"
```

Expected: prints `OK`.

- [ ] **Step 3: Commit M1 completion marker**

If you maintain a CHANGELOG or feature flag, mark M1 complete. Otherwise no-op.

---

## Milestone M2 — Council Fargate service (~5-6 days)

**M2 outcome:** Council session written by M1's reactor is picked up by a new Council Fargate service. 6 advisors investigate in parallel asyncio tasks, each with scoped tool palette. CouncilDecision is written. Reflection writes learnings to MEM#. Existing Council Lambda still exists alongside (deleted in M3).

### Task 15: Rename AdvisorType enum to wave-review lenses

**Files:**
- Modify: `lambdas/council/src/council/enums.py`
- Modify: `lambdas/council/tests/test_models.py` (and any other test using old names)
- Modify: `docs/design/council-protocol.md`

- [ ] **Step 1: Inspect current usage**

```bash
grep -rn "QUALITY\|MARKET\|MATURITY" lambdas/council/ docs/design/council-protocol.md
```

Note every file referencing the old names.

- [ ] **Step 2: Write the failing test for the new names**

```python
# lambdas/council/tests/test_models.py — add
def test_advisor_type_has_architecture():
    from council.enums import AdvisorType
    assert AdvisorType.ARCHITECTURE.value == "architecture"

def test_advisor_type_has_ux():
    from council.enums import AdvisorType
    assert AdvisorType.UX.value == "ux"

def test_advisor_type_has_cost():
    from council.enums import AdvisorType
    assert AdvisorType.COST.value == "cost"

def test_advisor_type_no_longer_has_quality():
    from council.enums import AdvisorType
    assert not hasattr(AdvisorType, "QUALITY")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd lambdas/council && pytest tests/test_models.py -v`
Expected: FAIL — old names still present.

- [ ] **Step 4: Rename the enum**

Edit `lambdas/council/src/council/enums.py`:

```python
class AdvisorType(Enum):
    SECURITY = "security"
    ARCHITECTURE = "architecture"
    CLARITY = "clarity"
    PERFORMANCE = "performance"
    UX = "ux"
    COST = "cost"


VETO_ADVISORS = {AdvisorType.SECURITY, AdvisorType.CLARITY}
```

- [ ] **Step 5: Update existing test files for the rename**

For every test referencing `AdvisorType.QUALITY`, `AdvisorType.MARKET`, `AdvisorType.MATURITY`:
- `AdvisorType.QUALITY` → `AdvisorType.ARCHITECTURE`
- `AdvisorType.MARKET` → `AdvisorType.COST`
- `AdvisorType.MATURITY` → `AdvisorType.UX`

These mappings are arbitrary for testing purposes — the goal is the suite continues to pass; semantic mapping is handled by the new system prompts written in later tasks.

- [ ] **Step 6: Update docs/design/council-protocol.md**

Find the advisor list and rename: Quality → Architecture, Market → Cost, Maturity → UX. Add a note at the top:

```markdown
> **Note:** Advisor names were updated 2026-05-16 from wave-planning lenses
> (Quality / Market / Maturity) to wave-review lenses (Architecture / UX / Cost).
> The veto pair (Security + Clarity) is unchanged.
```

- [ ] **Step 7: Rename prompt files**

```bash
cd lambdas/council/prompts/advisors
git mv quality.md architecture.md
git mv market.md cost.md
git mv maturity.md ux.md
```

The prompt content will be rewritten in Task 19 (advisor system prompts). For now the filename rename is enough.

- [ ] **Step 8: Run all council tests**

Run: `cd lambdas/council && pytest tests/ -v`
Expected: PASS, all existing tests now use new names.

- [ ] **Step 9: Commit**

```bash
git add lambdas/council/src/council/enums.py lambdas/council/tests/ lambdas/council/prompts/ docs/design/council-protocol.md
git commit -m "refactor(council): rename advisor enum to wave-review lenses (Architecture/UX/Cost)"
```

### Task 16: Extend AdvisorVote with investigation_trace + cited_evidence

**Files:**
- Modify: `lambdas/council/src/council/models.py`
- Modify: `lambdas/council/tests/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# lambdas/council/tests/test_models.py — add
def test_advisor_vote_has_investigation_trace():
    from council.models import AdvisorVote, ToolCall
    from council.enums import AdvisorType, VoteType
    vote = AdvisorVote(
        advisor=AdvisorType.SECURITY,
        vote=VoteType.APPROVE,
        scores={},
        reasoning="ok",
        confidence=0.8,
        investigation_trace=[
            ToolCall(
                tool_name="read_file",
                args={"path": "foo.py"},
                result_summary="def foo()...",
                duration_ms=15,
                error=None,
            ),
        ],
    )
    assert len(vote.investigation_trace) == 1
    d = vote.to_dict()
    assert "investigation_trace" in d
    assert d["investigation_trace"][0]["tool_name"] == "read_file"


def test_advisor_vote_has_cited_evidence():
    from council.models import AdvisorVote, CitedEvidence
    from council.enums import AdvisorType, VoteType
    vote = AdvisorVote(
        advisor=AdvisorType.ARCHITECTURE,
        vote=VoteType.BLOCK,
        scores={},
        reasoning="circular dep",
        confidence=0.9,
        cited_evidence=[
            CitedEvidence(
                file_path="apps/api/foo.py",
                line_range=(42, 50),
                pr_number=5,
                reason="imports apps/api/bar which imports back",
            ),
        ],
    )
    d = vote.to_dict()
    assert d["cited_evidence"][0]["file_path"] == "apps/api/foo.py"
    assert d["cited_evidence"][0]["line_range"] == [42, 50]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd lambdas/council && pytest tests/test_models.py -v`
Expected: FAIL.

- [ ] **Step 3: Add ToolCall + CitedEvidence + extend AdvisorVote**

Edit `lambdas/council/src/council/models.py` — add new dataclasses + extend existing AdvisorVote:

```python
@dataclass
class ToolCall:
    tool_name: str
    args: dict[str, Any]
    result_summary: str
    duration_ms: int
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = {
            "tool_name": self.tool_name,
            "args": self.args,
            "result_summary": self.result_summary,
            "duration_ms": self.duration_ms,
        }
        if self.error:
            d["error"] = self.error
        return d


@dataclass
class CitedEvidence:
    file_path: str
    line_range: tuple[int, int] | None = None
    pr_number: int | None = None
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"file_path": self.file_path, "reason": self.reason}
        if self.line_range:
            d["line_range"] = list(self.line_range)
        if self.pr_number is not None:
            d["pr_number"] = self.pr_number
        return d
```

Add to existing `AdvisorVote` dataclass (preserve all existing fields):

```python
@dataclass
class AdvisorVote:
    # ... existing fields preserved ...
    investigation_trace: list[ToolCall] = field(default_factory=list)
    cited_evidence: list[CitedEvidence] = field(default_factory=list)
    # tokens_consumed derived from existing cost.tokens_in + cost.tokens_out
```

Extend `to_dict()` in `AdvisorVote`:

```python
def to_dict(self) -> dict[str, Any]:
    d: dict[str, Any] = {
        # ... existing keys ...
    }
    if self.investigation_trace:
        d["investigation_trace"] = [t.to_dict() for t in self.investigation_trace]
    if self.cited_evidence:
        d["cited_evidence"] = [c.to_dict() for c in self.cited_evidence]
    return d
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd lambdas/council && pytest tests/test_models.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lambdas/council/src/council/models.py lambdas/council/tests/test_models.py
git commit -m "feat(council): add investigation_trace + cited_evidence to AdvisorVote"
```

### Task 17: Tool implementations — filesystem (read_file, grep, list_directory)

**Files:**
- Create: `lambdas/council/src/council/tools/__init__.py`
- Create: `lambdas/council/src/council/tools/filesystem.py`
- Create: `lambdas/council/tests/test_tools_filesystem.py`

- [ ] **Step 1: Write the failing test**

```python
# lambdas/council/tests/test_tools_filesystem.py
import os
import tempfile
import pytest

from council.tools.filesystem import read_file, grep, list_directory


@pytest.fixture
def tmp_repo():
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(f"{d}/apps/api", exist_ok=True)
        with open(f"{d}/apps/api/foo.py", "w") as f:
            f.write("def hello():\n    return 'world'\n")
        yield d


def test_read_file_returns_full_contents(tmp_repo):
    result = read_file(path=f"{tmp_repo}/apps/api/foo.py")
    assert "def hello" in result["content"]


def test_read_file_returns_line_range(tmp_repo):
    result = read_file(path=f"{tmp_repo}/apps/api/foo.py", line_start=1, line_end=1)
    assert result["content"].startswith("def hello")
    assert "return" not in result["content"]


def test_read_file_missing_returns_error(tmp_repo):
    result = read_file(path=f"{tmp_repo}/no/such/file.py")
    assert result["error"] == "file_not_found"


def test_grep_finds_matches(tmp_repo):
    result = grep(pattern="hello", path=tmp_repo)
    assert any("foo.py" in m["file"] for m in result["matches"])


def test_grep_empty_results_is_not_error(tmp_repo):
    result = grep(pattern="nonexistent_pattern", path=tmp_repo)
    assert result["matches"] == []
    assert "error" not in result


def test_list_directory_lists_files(tmp_repo):
    result = list_directory(path=f"{tmp_repo}/apps/api")
    assert "foo.py" in result["entries"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd lambdas/council && pytest tests/test_tools_filesystem.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement filesystem tools**

```python
# lambdas/council/src/council/tools/__init__.py
"""Council advisor tools — read-only investigation against EFS + GitHub."""
```

```python
# lambdas/council/src/council/tools/filesystem.py
"""Filesystem investigation tools: read_file, grep, list_directory."""

from __future__ import annotations

import os
import re
import subprocess
from typing import Any


def read_file(path: str, line_start: int | None = None, line_end: int | None = None) -> dict[str, Any]:
    """Return file contents or a structured error.

    line_start and line_end are 1-indexed and inclusive.
    """
    if not os.path.isfile(path):
        return {"error": "file_not_found", "path": path}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except (OSError, PermissionError) as e:
        return {"error": "read_error", "message": str(e)[:200]}

    if line_start is not None or line_end is not None:
        start = (line_start or 1) - 1
        end = line_end if line_end is not None else len(lines)
        content = "".join(lines[start:end])
    else:
        content = "".join(lines)
    return {"content": content[:50000], "path": path, "line_count": len(lines)}


def grep(pattern: str, path: str = ".", max_results: int = 50) -> dict[str, Any]:
    """Search for pattern across files under path."""
    try:
        re.compile(pattern)
    except re.error as e:
        return {"error": "invalid_regex", "message": str(e)}

    try:
        result = subprocess.run(
            ["grep", "-rn", "--include=*.py", "--include=*.swift", "--include=*.ts",
             "--include=*.md", "-E", pattern, path],
            capture_output=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return {"error": "grep_timeout"}

    matches: list[dict[str, Any]] = []
    for line in result.stdout.decode(errors="replace").splitlines()[:max_results]:
        parts = line.split(":", 2)
        if len(parts) == 3:
            matches.append({"file": parts[0], "line": int(parts[1]), "match": parts[2][:200]})
    return {"matches": matches}


def list_directory(path: str) -> dict[str, Any]:
    """List the immediate entries of a directory."""
    if not os.path.isdir(path):
        return {"error": "not_a_directory", "path": path}
    try:
        entries = sorted(os.listdir(path))
    except (OSError, PermissionError) as e:
        return {"error": "list_error", "message": str(e)[:200]}
    return {"entries": entries[:200], "path": path}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd lambdas/council && pytest tests/test_tools_filesystem.py -v`
Expected: PASS, 6 tests.

- [ ] **Step 5: Commit**

```bash
git add lambdas/council/src/council/tools/ lambdas/council/tests/test_tools_filesystem.py
git commit -m "feat(council): filesystem tools (read_file, grep, list_directory)"
```

### Task 18: Tool implementations — git + github

**Files:**
- Create: `lambdas/council/src/council/tools/git.py`
- Create: `lambdas/council/src/council/tools/github.py`
- Create: `lambdas/council/tests/test_tools_git.py`

- [ ] **Step 1: Write the failing test**

```python
# lambdas/council/tests/test_tools_git.py
from unittest.mock import patch, MagicMock

from council.tools.git import git_log_for_file, get_pr_diff, read_integration_file
from council.tools.github import get_pr_metadata


def test_git_log_for_file_returns_recent_commits():
    log_output = b"""abc123 alice 2026-01-01 added foo
def456 bob 2026-01-02 refactored foo
"""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=log_output, stderr=b"")
        result = git_log_for_file(repo_path="/r", file_path="foo.py", max_entries=5)
        assert len(result["commits"]) == 2
        assert result["commits"][0]["sha"] == "abc123"


def test_get_pr_diff_reads_from_worktree():
    diff_output = b"""diff --git a/foo.py b/foo.py
--- a/foo.py
+++ b/foo.py
@@ -1 +1,2 @@
+# new line
"""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=diff_output, stderr=b"")
        result = get_pr_diff(worktree_path="/r/.pr-42")
        assert "new line" in result["diff"]


def test_read_integration_file_reads_from_integration_worktree(tmp_path):
    integration = tmp_path / ".integration"
    integration.mkdir()
    (integration / "merged.py").write_text("merged content")
    result = read_integration_file(integration_path=str(integration), path="merged.py")
    assert result["content"] == "merged content"


def test_get_pr_metadata_fetches_from_github_api():
    response = {
        "number": 42, "title": "Fix bug", "user": {"login": "alice"},
        "head": {"sha": "abc"}, "body": "Description here",
    }
    with patch("urllib.request.urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = (
            b'{"number":42,"title":"Fix bug","user":{"login":"alice"},'
            b'"head":{"sha":"abc"},"body":"Description here"}'
        )
        result = get_pr_metadata(repo="org/r", pr_number=42, github_token="t")
        assert result["title"] == "Fix bug"
        assert result["author"] == "alice"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd lambdas/council && pytest tests/test_tools_git.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement git tools**

```python
# lambdas/council/src/council/tools/git.py
"""Git-based investigation tools."""

from __future__ import annotations

import os
import subprocess
from typing import Any


def git_log_for_file(repo_path: str, file_path: str, max_entries: int = 10) -> dict[str, Any]:
    """Return recent commits touching file_path."""
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "log", f"-{max_entries}",
             "--pretty=format:%h %an %ad %s", "--date=short", "--", file_path],
            capture_output=True,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        return {"error": "git_log_timeout"}
    if result.returncode != 0:
        return {"error": "git_log_failed", "stderr": result.stderr.decode()[:200]}

    commits: list[dict[str, Any]] = []
    for line in result.stdout.decode().splitlines():
        parts = line.split(" ", 3)
        if len(parts) == 4:
            commits.append({"sha": parts[0], "author": parts[1], "date": parts[2], "subject": parts[3]})
    return {"commits": commits}


def get_pr_diff(worktree_path: str) -> dict[str, Any]:
    """Return the diff of the PR's worktree against origin/main."""
    try:
        result = subprocess.run(
            ["git", "-C", worktree_path, "diff", "origin/main..."],
            capture_output=True,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        return {"error": "git_diff_timeout"}
    if result.returncode != 0:
        return {"error": "git_diff_failed", "stderr": result.stderr.decode()[:200]}
    return {"diff": result.stdout.decode()[:100000]}


def read_integration_file(integration_path: str, path: str) -> dict[str, Any]:
    """Read a file from the integration worktree (post-merge state)."""
    full = os.path.join(integration_path, path)
    if not os.path.isfile(full):
        return {"error": "file_not_found", "path": full}
    try:
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(50000)
    except (OSError, PermissionError) as e:
        return {"error": "read_error", "message": str(e)[:200]}
    return {"content": content, "path": full}
```

- [ ] **Step 4: Implement github metadata tool**

```python
# lambdas/council/src/council/tools/github.py
"""GitHub REST API: PR metadata only (no clone)."""

from __future__ import annotations

import json
import urllib.request
from typing import Any


def get_pr_metadata(repo: str, pr_number: int, github_token: str) -> dict[str, Any]:
    """Fetch PR metadata via GitHub REST API."""
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "cawnex-council",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read())
    except Exception as e:  # noqa: BLE001
        return {"error": "github_api_error", "message": str(e)[:200]}

    return {
        "number": data.get("number"),
        "title": data.get("title", "")[:300],
        "author": data.get("user", {}).get("login", ""),
        "head_sha": data.get("head", {}).get("sha", ""),
        "body": (data.get("body") or "")[:2000],
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd lambdas/council && pytest tests/test_tools_git.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add lambdas/council/src/council/tools/git.py lambdas/council/src/council/tools/github.py lambdas/council/tests/test_tools_git.py
git commit -m "feat(council): git + github metadata investigation tools"
```

### Task 19: Per-advisor tool palette + scoping enforcement

**Files:**
- Create: `lambdas/council/src/council/tools/palette.py`
- Create: `lambdas/council/tests/test_tools_palette.py`

- [ ] **Step 1: Write the failing test**

```python
# lambdas/council/tests/test_tools_palette.py
from council.enums import AdvisorType
from council.tools.palette import get_palette, is_in_scope, execute_tool


def test_security_palette_includes_git_log_for_file():
    tools = get_palette(AdvisorType.SECURITY)
    assert any(t["name"] == "git_log_for_file" for t in tools)


def test_ux_palette_does_not_include_git_log_for_file():
    tools = get_palette(AdvisorType.UX)
    assert not any(t["name"] == "git_log_for_file" for t in tools)


def test_ux_read_file_on_ios_path_is_in_scope():
    assert is_in_scope(AdvisorType.UX, "read_file", {"path": "/repo/apps/ios/foo.swift"})


def test_ux_read_file_on_api_path_is_out_of_scope():
    assert not is_in_scope(AdvisorType.UX, "read_file", {"path": "/repo/apps/api/foo.py"})


def test_cost_read_file_on_infra_path_is_in_scope():
    assert is_in_scope(AdvisorType.COST, "read_file", {"path": "/repo/infra/lib/foo.ts"})


def test_cost_read_file_on_api_path_is_out_of_scope():
    assert not is_in_scope(AdvisorType.COST, "read_file", {"path": "/repo/apps/api/foo.py"})


def test_security_read_file_on_anywhere_is_in_scope():
    assert is_in_scope(AdvisorType.SECURITY, "read_file", {"path": "/repo/anywhere/foo.py"})


def test_execute_tool_returns_out_of_scope_error_for_disallowed_path():
    result = execute_tool(
        advisor=AdvisorType.UX,
        tool_name="read_file",
        args={"path": "/repo/apps/api/foo.py"},
        context={"repo_path": "/repo", "github_token": ""},
    )
    assert result["tool_error"] == "out_of_scope"
    assert result["advisor"] == "ux"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd lambdas/council && pytest tests/test_tools_palette.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement palette**

```python
# lambdas/council/src/council/tools/palette.py
"""Per-advisor tool palette with path-scoping enforcement."""

from __future__ import annotations

from typing import Any, Callable

from council.enums import AdvisorType
from council.tools.filesystem import grep, list_directory, read_file
from council.tools.git import get_pr_diff, git_log_for_file, read_integration_file
from council.tools.github import get_pr_metadata


# Tool definitions in Anthropic tool-use schema format
ALL_TOOL_SPECS: dict[str, dict[str, Any]] = {
    "read_file": {
        "name": "read_file",
        "description": "Read a file from the codebase. Optionally specify line_start/line_end.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "line_start": {"type": "integer"},
                "line_end": {"type": "integer"},
            },
            "required": ["path"],
        },
    },
    "grep": {
        "name": "grep",
        "description": "Search for a regex pattern across files.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "path": {"type": "string"},
            },
            "required": ["pattern"],
        },
    },
    "list_directory": {
        "name": "list_directory",
        "description": "List the entries of a directory.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    "git_log_for_file": {
        "name": "git_log_for_file",
        "description": "Return recent commits touching a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "max_entries": {"type": "integer"},
            },
            "required": ["file_path"],
        },
    },
    "get_pr_diff": {
        "name": "get_pr_diff",
        "description": "Return the diff of a PR's worktree against origin/main.",
        "input_schema": {
            "type": "object",
            "properties": {"pr_number": {"type": "integer"}},
            "required": ["pr_number"],
        },
    },
    "read_integration_file": {
        "name": "read_integration_file",
        "description": "Read a file from the merged integration worktree (post-merge state).",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    "get_pr_metadata": {
        "name": "get_pr_metadata",
        "description": "Fetch PR metadata from GitHub (title, author, head_sha, body).",
        "input_schema": {
            "type": "object",
            "properties": {"pr_number": {"type": "integer"}},
            "required": ["pr_number"],
        },
    },
}


_PALETTES: dict[AdvisorType, list[str]] = {
    AdvisorType.SECURITY: [
        "read_file", "grep", "list_directory", "git_log_for_file",
        "get_pr_diff", "read_integration_file", "get_pr_metadata",
    ],
    AdvisorType.ARCHITECTURE: [
        "read_file", "grep", "list_directory", "git_log_for_file",
        "get_pr_diff", "read_integration_file", "get_pr_metadata",
    ],
    AdvisorType.CLARITY: [
        "read_file", "grep", "get_pr_diff", "read_integration_file", "get_pr_metadata",
    ],
    AdvisorType.PERFORMANCE: [
        "read_file", "grep", "git_log_for_file",
        "get_pr_diff", "read_integration_file", "get_pr_metadata",
    ],
    AdvisorType.UX: [
        "read_file", "grep", "get_pr_diff", "read_integration_file", "get_pr_metadata",
    ],
    AdvisorType.COST: [
        "read_file", "grep", "list_directory",
        "get_pr_diff", "read_integration_file", "get_pr_metadata",
    ],
}


def get_palette(advisor: AdvisorType) -> list[dict[str, Any]]:
    """Return the tool definitions available to this advisor."""
    return [ALL_TOOL_SPECS[name] for name in _PALETTES[advisor]]


def is_in_scope(advisor: AdvisorType, tool_name: str, args: dict[str, Any]) -> bool:
    """Path-scoping enforcement. UX scoped to apps/ios/. Cost scoped to infra/."""
    path = args.get("path", "")
    if not path:
        return True

    if advisor == AdvisorType.UX:
        return "/apps/ios/" in path or path.endswith(".strings") or path.endswith(".swift")
    if advisor == AdvisorType.COST:
        return "/infra/" in path

    return True


def execute_tool(
    advisor: AdvisorType,
    tool_name: str,
    args: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    """Execute a tool call for an advisor, enforcing palette + scope."""
    if tool_name not in _PALETTES[advisor]:
        return {"tool_error": "not_in_palette", "advisor": advisor.value, "tool": tool_name}

    if not is_in_scope(advisor, tool_name, args):
        return {
            "tool_error": "out_of_scope",
            "advisor": advisor.value,
            "tool": tool_name,
            "path": args.get("path"),
        }

    if tool_name == "read_file":
        return read_file(**args)
    if tool_name == "grep":
        path = args.get("path", context.get("repo_path", "."))
        return grep(pattern=args["pattern"], path=path)
    if tool_name == "list_directory":
        return list_directory(**args)
    if tool_name == "git_log_for_file":
        return git_log_for_file(
            repo_path=context["repo_path"],
            file_path=args["file_path"],
            max_entries=args.get("max_entries", 10),
        )
    if tool_name == "get_pr_diff":
        worktree = context["worktree_paths"].get(args["pr_number"])
        if not worktree:
            return {"tool_error": "pr_not_in_context", "pr_number": args["pr_number"]}
        return get_pr_diff(worktree_path=worktree)
    if tool_name == "read_integration_file":
        return read_integration_file(
            integration_path=context["integration_path"],
            path=args["path"],
        )
    if tool_name == "get_pr_metadata":
        return get_pr_metadata(
            repo=context["repo"],
            pr_number=args["pr_number"],
            github_token=context.get("github_token", ""),
        )

    return {"tool_error": "unknown_tool", "tool": tool_name}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd lambdas/council && pytest tests/test_tools_palette.py -v`
Expected: PASS, 8 tests.

- [ ] **Step 5: Commit**

```bash
git add lambdas/council/src/council/tools/palette.py lambdas/council/tests/test_tools_palette.py
git commit -m "feat(council): per-advisor tool palette + path-scoping enforcement"
```

### Task 20: Investigation trace builder

**Files:**
- Create: `lambdas/council/src/council/tools/trace.py`
- Create: `lambdas/council/tests/test_tools_trace.py`

- [ ] **Step 1: Write the failing test**

```python
# lambdas/council/tests/test_tools_trace.py
from council.tools.trace import TraceBuilder


def test_trace_builder_records_tool_calls():
    builder = TraceBuilder()
    builder.record(tool_name="read_file", args={"path": "foo.py"},
                   result_summary="def foo()...", duration_ms=10)
    builder.record(tool_name="grep", args={"pattern": "tenant_id"},
                   result_summary="3 matches", duration_ms=20)
    trace = builder.build()
    assert len(trace) == 2
    assert trace[0].tool_name == "read_file"
    assert trace[1].duration_ms == 20


def test_trace_builder_records_errors():
    builder = TraceBuilder()
    builder.record(tool_name="read_file", args={"path": "missing.py"},
                   result_summary="", duration_ms=5, error="file_not_found")
    trace = builder.build()
    assert trace[0].error == "file_not_found"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd lambdas/council && pytest tests/test_tools_trace.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement TraceBuilder**

```python
# lambdas/council/src/council/tools/trace.py
"""Build investigation_trace as tool calls happen."""

from __future__ import annotations

from typing import Any

from council.models import ToolCall


class TraceBuilder:
    def __init__(self) -> None:
        self._calls: list[ToolCall] = []

    def record(
        self,
        tool_name: str,
        args: dict[str, Any],
        result_summary: str,
        duration_ms: int,
        error: str | None = None,
    ) -> None:
        self._calls.append(
            ToolCall(
                tool_name=tool_name,
                args=args,
                result_summary=result_summary[:200],
                duration_ms=duration_ms,
                error=error,
            )
        )

    def build(self) -> list[ToolCall]:
        return list(self._calls)

    def call_count(self) -> int:
        return len(self._calls)

    def error_count(self) -> int:
        return sum(1 for c in self._calls if c.error is not None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd lambdas/council && pytest tests/test_tools_trace.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lambdas/council/src/council/tools/trace.py lambdas/council/tests/test_tools_trace.py
git commit -m "feat(council): TraceBuilder for investigation_trace records"
```

### Task 21: Anthropic streaming + tool-use client

**Files:**
- Modify: `lambdas/council/src/council/_claude_client.py` → rename to `claude_client.py`
- Create: `lambdas/council/tests/test_claude_client.py`

- [ ] **Step 1: Rename existing file + write the failing test**

```bash
git mv lambdas/council/src/council/_claude_client.py lambdas/council/src/council/claude_client.py
```

```python
# lambdas/council/tests/test_claude_client.py
import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from council.claude_client import run_tool_use_loop, ToolUseResult


@pytest.mark.asyncio
async def test_tool_use_loop_terminates_on_submit_vote():
    """When model emits submit_vote, the loop returns immediately."""
    # Mock a streaming response that emits a tool_use of submit_vote
    mock_stream = AsyncMock()
    mock_stream.__aiter__.return_value = iter([
        MagicMock(type="content_block_start", content_block=MagicMock(
            type="tool_use", name="submit_vote",
            input={"vote": "approve", "confidence": 0.8, "reasoning": "looks good"},
        )),
        MagicMock(type="message_stop"),
    ])

    with patch("council.claude_client.anthropic.AsyncAnthropic") as mock_client:
        mock_client.return_value.messages.stream.return_value.__aenter__.return_value = mock_stream
        result = await run_tool_use_loop(
            system_prompt="you are security",
            user_message="evaluate the wave",
            tools=[],
            max_tool_calls=15,
            wall_clock_seconds=180,
            tool_executor=lambda name, args: {"result": "ok"},
        )
    assert result.terminated_by == "submit_vote"


@pytest.mark.asyncio
async def test_tool_use_loop_terminates_on_call_cap():
    """When 15 tool calls happen without submit_vote, loop returns abstain."""
    # This requires the loop to count tool calls; the implementation is
    # responsible for stopping at the cap. We assert the result reflects it.
    # See implementation step for the cap-counting logic.
    pass  # Filled when implementation is in place
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd lambdas/council && pytest tests/test_claude_client.py -v`
Expected: FAIL — `run_tool_use_loop` doesn't exist yet.

- [ ] **Step 3: Implement claude_client.py**

```python
# lambdas/council/src/council/claude_client.py
"""Anthropic streaming + tool-use loop for advisor investigations."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import anthropic

logger = logging.getLogger("council.claude_client")


@dataclass
class ToolUseResult:
    final_vote: dict[str, Any] | None
    terminated_by: str  # "submit_vote" | "call_cap" | "time_cap" | "api_error"
    tool_calls_made: int
    tokens_consumed: int
    trace_entries: list[dict[str, Any]] = field(default_factory=list)


SUBMIT_VOTE_TOOL = {
    "name": "submit_vote",
    "description": "Submit your final vote on this wave. Call this exactly once to finish.",
    "input_schema": {
        "type": "object",
        "properties": {
            "vote": {"type": "string", "enum": ["approve", "approve_with_condition", "abstain", "block"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "reasoning": {"type": "string"},
            "blockers": {"type": "array", "items": {"type": "string"}},
            "condition": {"type": "string"},
            "cited_evidence": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string"},
                        "line_range": {"type": "array", "items": {"type": "integer"}},
                        "pr_number": {"type": "integer"},
                        "reason": {"type": "string"},
                    },
                },
            },
        },
        "required": ["vote", "confidence", "reasoning"],
    },
}


async def run_tool_use_loop(
    system_prompt: str,
    user_message: str,
    tools: list[dict[str, Any]],
    max_tool_calls: int,
    wall_clock_seconds: int,
    tool_executor: Callable[[str, dict[str, Any]], dict[str, Any]],
    model: str = "claude-haiku-4-5-20251001",
) -> ToolUseResult:
    """Run an advisor's tool-use loop against Anthropic. Returns ToolUseResult."""
    full_tools = tools + [SUBMIT_VOTE_TOOL]
    messages = [{"role": "user", "content": user_message}]
    tool_calls_made = 0
    tokens_in = 0
    tokens_out = 0
    trace_entries: list[dict[str, Any]] = []
    start = time.time()

    client = anthropic.AsyncAnthropic()

    while True:
        elapsed = time.time() - start
        if elapsed > wall_clock_seconds:
            return ToolUseResult(
                final_vote=None,
                terminated_by="time_cap",
                tool_calls_made=tool_calls_made,
                tokens_consumed=tokens_in + tokens_out,
                trace_entries=trace_entries,
            )

        try:
            async with client.messages.stream(
                model=model,
                max_tokens=4000,
                system=system_prompt,
                tools=full_tools,
                messages=messages,
            ) as stream:
                tool_use_blocks: list[dict[str, Any]] = []
                async for event in stream:
                    if event.type == "content_block_start" and event.content_block.type == "tool_use":
                        tool_use_blocks.append({
                            "id": event.content_block.id,
                            "name": event.content_block.name,
                            "input": event.content_block.input,
                        })
                # Capture usage
                final_msg = await stream.get_final_message()
                tokens_in += final_msg.usage.input_tokens
                tokens_out += final_msg.usage.output_tokens
        except anthropic.APIError as e:
            logger.error(json.dumps({
                "event": "advisor_api_error",
                "error_class": type(e).__name__,
                "message": str(e)[:200],
            }))
            return ToolUseResult(
                final_vote=None,
                terminated_by="api_error",
                tool_calls_made=tool_calls_made,
                tokens_consumed=tokens_in + tokens_out,
                trace_entries=trace_entries,
            )

        if not tool_use_blocks:
            # Model emitted text without a tool call — treat as abstain
            return ToolUseResult(
                final_vote=None,
                terminated_by="no_tool_call",
                tool_calls_made=tool_calls_made,
                tokens_consumed=tokens_in + tokens_out,
                trace_entries=trace_entries,
            )

        # Check for submit_vote terminator
        for block in tool_use_blocks:
            if block["name"] == "submit_vote":
                return ToolUseResult(
                    final_vote=block["input"],
                    terminated_by="submit_vote",
                    tool_calls_made=tool_calls_made,
                    tokens_consumed=tokens_in + tokens_out,
                    trace_entries=trace_entries,
                )

        # Execute non-submit_vote tools, append results
        tool_results: list[dict[str, Any]] = []
        for block in tool_use_blocks:
            tool_calls_made += 1
            if tool_calls_made > max_tool_calls:
                return ToolUseResult(
                    final_vote=None,
                    terminated_by="call_cap",
                    tool_calls_made=tool_calls_made,
                    tokens_consumed=tokens_in + tokens_out,
                    trace_entries=trace_entries,
                )

            tool_start = time.time()
            result = tool_executor(block["name"], block["input"])
            duration_ms = int((time.time() - tool_start) * 1000)

            result_str = json.dumps(result)[:5000]
            trace_entries.append({
                "tool_name": block["name"],
                "args": block["input"],
                "result_summary": result_str[:200],
                "duration_ms": duration_ms,
                "error": result.get("tool_error") or result.get("error"),
            })

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block["id"],
                "content": result_str,
            })

        # Append the assistant turn (with tool_use blocks) + user tool_results
        messages.append({"role": "assistant", "content": [
            {"type": "tool_use", "id": b["id"], "name": b["name"], "input": b["input"]}
            for b in tool_use_blocks
        ]})
        messages.append({"role": "user", "content": tool_results})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd lambdas/council && pytest tests/test_claude_client.py -v`
Expected: PASS (the `submit_vote` test; the second test is a placeholder).

Update the placeholder test for the call_cap path now that the implementation exists:

```python
@pytest.mark.asyncio
async def test_tool_use_loop_terminates_on_call_cap():
    """When tool calls hit the cap without submit_vote, loop returns terminated_by=call_cap."""
    # Build a fake stream that always emits a non-submit_vote tool call
    def make_stream_emitting_grep():
        m = AsyncMock()
        m.__aiter__.return_value = iter([
            MagicMock(type="content_block_start", content_block=MagicMock(
                type="tool_use", id="t1", name="grep", input={"pattern": "x"},
            )),
        ])
        m.get_final_message = AsyncMock(return_value=MagicMock(usage=MagicMock(input_tokens=10, output_tokens=5)))
        return m

    with patch("council.claude_client.anthropic.AsyncAnthropic") as mock_client:
        ctx = mock_client.return_value.messages.stream.return_value
        ctx.__aenter__.side_effect = lambda *a, **kw: make_stream_emitting_grep()
        result = await run_tool_use_loop(
            system_prompt="x",
            user_message="x",
            tools=[],
            max_tool_calls=3,
            wall_clock_seconds=10,
            tool_executor=lambda n, a: {"result": "ok"},
        )
    assert result.terminated_by == "call_cap"
    assert result.tool_calls_made > 3
```

Run: `cd lambdas/council && pytest tests/test_claude_client.py -v`
Expected: PASS, both tests.

- [ ] **Step 5: Commit**

```bash
git add lambdas/council/src/council/claude_client.py lambdas/council/tests/test_claude_client.py lambdas/council/src/council/_claude_client.py
git commit -m "feat(council): async streaming + tool-use loop with cap enforcement"
```

### Task 22: Advisor base + per-advisor implementations

**Files:**
- Create: `lambdas/council/src/council/advisors/__init__.py`
- Create: `lambdas/council/src/council/advisors/base.py`
- Create: `lambdas/council/src/council/advisors/security.py` (+ 5 more for each advisor)
- Create: `lambdas/council/src/council/advisors/prompts/security.md` (+ 5 more)
- Create: `lambdas/council/tests/test_advisors_base.py`

- [ ] **Step 1: Write the failing test**

```python
# lambdas/council/tests/test_advisors_base.py
import asyncio
import pytest
from unittest.mock import patch, AsyncMock

from council.advisors.base import run_advisor
from council.enums import AdvisorType, VoteType


@pytest.mark.asyncio
async def test_run_advisor_returns_vote_on_submit():
    fake_result = AsyncMock()
    fake_result.final_vote = {"vote": "approve", "confidence": 0.9, "reasoning": "good"}
    fake_result.terminated_by = "submit_vote"
    fake_result.tool_calls_made = 4
    fake_result.tokens_consumed = 1500
    fake_result.trace_entries = []

    with patch("council.advisors.base.run_tool_use_loop", return_value=fake_result):
        vote = await run_advisor(
            advisor=AdvisorType.SECURITY,
            packet={"wave_id": "w1"},
            context={"repo_path": "/r", "worktree_paths": {}, "integration_path": "/i",
                     "repo": "org/r", "github_token": "t"},
        )
    assert vote.advisor == AdvisorType.SECURITY
    assert vote.vote == VoteType.APPROVE
    assert vote.confidence == 0.9


@pytest.mark.asyncio
async def test_run_advisor_returns_abstain_on_call_cap():
    fake_result = AsyncMock()
    fake_result.final_vote = None
    fake_result.terminated_by = "call_cap"
    fake_result.tool_calls_made = 16
    fake_result.tokens_consumed = 5000
    fake_result.trace_entries = []

    with patch("council.advisors.base.run_tool_use_loop", return_value=fake_result):
        vote = await run_advisor(
            advisor=AdvisorType.ARCHITECTURE,
            packet={"wave_id": "w1"},
            context={"repo_path": "/r", "worktree_paths": {}, "integration_path": "/i",
                     "repo": "org/r", "github_token": "t"},
        )
    assert vote.vote == VoteType.ABSTAIN
    assert "15-call" in vote.reasoning or "cap" in vote.reasoning
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd lambdas/council && pytest tests/test_advisors_base.py -v`
Expected: FAIL.

- [ ] **Step 3: Write 6 minimal prompt files**

```bash
mkdir -p lambdas/council/src/council/advisors/prompts
```

```markdown
<!-- lambdas/council/src/council/advisors/prompts/security.md -->
You are the Security advisor on a Council reviewing a completed wave of changes.
You have veto power: if you vote BLOCK, the wave is rejected.

Use the tools to investigate the codebase. Look at the integration merge state,
read the PR diffs, search for tenant_id filters, auth checks, secret references.
You are not satisfied with prose summaries — check the code yourself.

When you have enough evidence, call submit_vote with your verdict.
```

(Repeat for architecture, clarity, performance, ux, cost — each with a one-paragraph role description. These can be expanded over time but must exist for M2 to compile.)

- [ ] **Step 4: Implement base.py**

```python
# lambdas/council/src/council/advisors/__init__.py
"""Advisor implementations — one per AdvisorType."""
```

```python
# lambdas/council/src/council/advisors/base.py
"""Base advisor: tool-use loop wrapper with cap-handling."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from council.claude_client import run_tool_use_loop
from council.enums import AdvisorType, VoteType
from council.models import AdvisorCost, AdvisorVote, CitedEvidence, ToolCall
from council.tools.palette import execute_tool, get_palette

CALL_CAP = 15
WALL_CLOCK_SECONDS = 180

_PROMPT_DIR = Path(__file__).parent / "prompts"


def _load_prompt(advisor: AdvisorType) -> str:
    path = _PROMPT_DIR / f"{advisor.value}.md"
    if not path.exists():
        return f"You are the {advisor.value} advisor. Investigate and submit_vote."
    return path.read_text()


def _vote_from_result(
    advisor: AdvisorType,
    result: Any,
) -> AdvisorVote:
    """Convert a ToolUseResult into an AdvisorVote."""
    # Split tokens 70/30 input/output — typical ratio for tool-use loops. The actual
    # streaming-level token split is captured in result.tokens_consumed (total). If
    # downstream cost analysis needs exact tokens_in/tokens_out separately, plumb
    # them through ToolUseResult — for Layer A the total is sufficient.
    cost = AdvisorCost(
        tokens_in=int(result.tokens_consumed * 0.7),
        tokens_out=int(result.tokens_consumed * 0.3),
        duration_ms=0,
    )
    trace = [
        ToolCall(
            tool_name=e["tool_name"],
            args=e["args"],
            result_summary=e["result_summary"],
            duration_ms=e["duration_ms"],
            error=e.get("error"),
        )
        for e in result.trace_entries
    ]

    if result.terminated_by == "submit_vote" and result.final_vote:
        v = result.final_vote
        vote_str = v.get("vote", "abstain")
        vote_type = {
            "approve": VoteType.APPROVE,
            "approve_with_condition": VoteType.APPROVE_WITH_CONDITION,
            "abstain": VoteType.ABSTAIN,
            "block": VoteType.BLOCK,
        }.get(vote_str, VoteType.ABSTAIN)
        evidence = [
            CitedEvidence(
                file_path=e.get("file_path", ""),
                line_range=tuple(e["line_range"]) if e.get("line_range") else None,
                pr_number=e.get("pr_number"),
                reason=e.get("reason", ""),
            )
            for e in v.get("cited_evidence", [])
        ]
        return AdvisorVote(
            advisor=advisor,
            vote=vote_type,
            scores={},
            reasoning=v.get("reasoning", ""),
            confidence=float(v.get("confidence", 0.5)),
            blockers=v.get("blockers", []),
            condition=v.get("condition", ""),
            cost=cost,
            investigation_trace=trace,
            cited_evidence=evidence,
        )

    # Cap-hit / error paths → abstain
    reasoning = f"investigation incomplete: terminated by {result.terminated_by} after {result.tool_calls_made} tool calls"
    return AdvisorVote(
        advisor=advisor,
        vote=VoteType.ABSTAIN,
        scores={},
        reasoning=reasoning,
        confidence=0.0,
        blockers=[reasoning] if "cap" in result.terminated_by else [],
        cost=cost,
        investigation_trace=trace,
    )


async def run_advisor(
    advisor: AdvisorType,
    packet: dict[str, Any],
    context: dict[str, Any],
) -> AdvisorVote:
    """Run a single advisor's investigation + vote."""
    system_prompt = _load_prompt(advisor)
    user_message = json.dumps(packet)
    tools = get_palette(advisor)

    def tool_executor(name: str, args: dict[str, Any]) -> dict[str, Any]:
        return execute_tool(advisor=advisor, tool_name=name, args=args, context=context)

    result = await run_tool_use_loop(
        system_prompt=system_prompt,
        user_message=user_message,
        tools=tools,
        max_tool_calls=CALL_CAP,
        wall_clock_seconds=WALL_CLOCK_SECONDS,
        tool_executor=tool_executor,
    )

    return _vote_from_result(advisor=advisor, result=result)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd lambdas/council && pytest tests/test_advisors_base.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add lambdas/council/src/council/advisors/ lambdas/council/tests/test_advisors_base.py
git commit -m "feat(council): advisor base loop + 6 prompt files + cap-to-abstain conversion"
```

### Task 23: Rewrite orchestrator with asyncio.gather

**Files:**
- Modify: `lambdas/council/src/council/orchestrator.py`
- Modify: `lambdas/council/tests/test_orchestrator.py`

- [ ] **Step 1: Write the failing async test**

```python
# lambdas/council/tests/test_orchestrator.py — add at end of file
import asyncio
import pytest
from unittest.mock import patch, AsyncMock

from council.orchestrator import run_council_session_async
from council.models import AdvisorVote
from council.enums import AdvisorType, VoteType


@pytest.mark.asyncio
async def test_run_council_session_async_calls_all_6_advisors_in_parallel():
    async def fake_advisor(advisor, packet, context):
        return AdvisorVote(
            advisor=advisor, vote=VoteType.APPROVE, scores={},
            reasoning="ok", confidence=0.8,
        )

    with patch("council.orchestrator.run_advisor", side_effect=fake_advisor):
        result = await run_council_session_async(
            packet={"wave_id": "w1"},
            context={"repo_path": "/r", "worktree_paths": {}, "integration_path": "/i",
                     "repo": "org/r", "github_token": "t"},
        )

    # All 6 advisors voted
    assert len(result.rounds[0].votes) == 6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd lambdas/council && pytest tests/test_orchestrator.py::test_run_council_session_async_calls_all_6_advisors_in_parallel -v`
Expected: FAIL — `run_council_session_async` doesn't exist.

- [ ] **Step 3: Add async runner to orchestrator.py**

Append to `lambdas/council/src/council/orchestrator.py`:

```python
import asyncio

from council.advisors.base import run_advisor
from council.enums import AdvisorType


ALL_ADVISORS = [
    AdvisorType.SECURITY,
    AdvisorType.ARCHITECTURE,
    AdvisorType.CLARITY,
    AdvisorType.PERFORMANCE,
    AdvisorType.UX,
    AdvisorType.COST,
]


async def run_council_session_async(
    packet: dict[str, Any],
    context: dict[str, Any],
    max_rounds: int = MAX_ROUNDS,
) -> CouncilSessionResult:
    """Async equivalent of run_council_session — uses asyncio.gather for 6 advisors."""
    # Round 1: all 6 in parallel
    votes = await asyncio.gather(
        *[run_advisor(advisor=a, packet=packet, context=context) for a in ALL_ADVISORS],
        return_exceptions=True,
    )

    # Convert exceptions to abstain votes
    materialized_votes = []
    for advisor, vote in zip(ALL_ADVISORS, votes):
        if isinstance(vote, Exception):
            from council.models import AdvisorCost
            materialized_votes.append(AdvisorVote(
                advisor=advisor,
                vote=VoteType.ABSTAIN,
                scores={},
                reasoning=f"advisor crashed: {type(vote).__name__}: {str(vote)[:200]}",
                confidence=0.0,
                cost=AdvisorCost.zero(),
            ))
        else:
            materialized_votes.append(vote)

    round_1 = VotingRound(round_number=1, votes=materialized_votes)
    rounds = [round_1]
    decision = synthesize_round(round_1, round_number=1, max_rounds=max_rounds)

    if decision.action in (DecisionAction.APPROVE, DecisionAction.APPROVE_WITH_CONDITIONS):
        return CouncilSessionResult(rounds=rounds, decision=decision, status=CouncilStatus.COMPLETED)

    # Debate rounds — disagreeing advisors re-vote
    for round_num in range(2, max_rounds + 1):
        disagreeing = _get_disagreeing_advisors(rounds[-1])
        if not disagreeing:
            break

        debate_packet = {**packet, "previous_rounds": [r.to_dict() for r in rounds],
                         "synthesis": decision.to_dict()}
        debate_votes = await asyncio.gather(
            *[run_advisor(advisor=a, packet=debate_packet, context=context) for a in disagreeing],
            return_exceptions=True,
        )
        materialized = []
        for advisor, v in zip(disagreeing, debate_votes):
            if isinstance(v, Exception):
                from council.models import AdvisorCost
                materialized.append(AdvisorVote(
                    advisor=advisor, vote=VoteType.ABSTAIN, scores={},
                    reasoning=f"debate crash: {type(v).__name__}", confidence=0.0,
                    cost=AdvisorCost.zero(),
                ))
            else:
                materialized.append(v)

        round_n = VotingRound(round_number=round_num, votes=materialized,
                              question=f"Round {round_num} debate")
        rounds.append(round_n)
        decision = synthesize_round(round_n, round_number=round_num, max_rounds=max_rounds)
        if decision.action in (DecisionAction.APPROVE, DecisionAction.APPROVE_WITH_CONDITIONS):
            break

    return CouncilSessionResult(rounds=rounds, decision=decision, status=CouncilStatus.COMPLETED)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd lambdas/council && pytest tests/test_orchestrator.py -v`
Expected: PASS, all tests including new async one.

- [ ] **Step 5: Commit**

```bash
git add lambdas/council/src/council/orchestrator.py lambdas/council/tests/test_orchestrator.py
git commit -m "feat(council): asyncio.gather-based parallel advisor runner with exception isolation"
```

### Task 24: Council session handler — load packet, run advisors, write decision

**Files:**
- Modify: `lambdas/council/src/council/handler.py`
- Create: `lambdas/council/tests/test_handler_fargate.py`

- [ ] **Step 1: Write the failing test**

```python
# lambdas/council/tests/test_handler_fargate.py
import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from council.handler import process_pending_session


@pytest.mark.asyncio
async def test_process_pending_session_writes_completed_status():
    blackboard = MagicMock()
    blackboard.read.side_effect = [
        # First read: session row
        {"PK": "P#p1", "SK": "COUNCIL#wr_w1_xyz", "status": "pending",
         "wave_id": "w1", "integration_sk": "INTEGRATION#w1", "auto_mode": "off"},
        # Second read: integration findings
        {"SK": "INTEGRATION#w1", "wave_id": "w1", "overall": "ready_for_council",
         "worktree_paths": {"42": "/.pr-42"}, "integration_worktree": "/.integration",
         "pr_numbers": [42], "merge_status": "ok"},
    ]
    # Mock the orchestrator to return a quick approve
    fake_result = MagicMock()
    fake_result.decision.action.value = "approve"
    fake_result.to_dict.return_value = {"decision": {"action": "approve"}}

    with patch("council.handler.run_council_session_async", AsyncMock(return_value=fake_result)):
        await process_pending_session(
            blackboard=blackboard,
            project_id="p1",
            session_sk="COUNCIL#wr_w1_xyz",
        )

    # Session status updated to completed
    update_calls = [c for c in blackboard.update_item.call_args_list if c.kwargs.get("sk") == "COUNCIL#wr_w1_xyz"]
    assert any("completed" in str(c) for c in update_calls)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd lambdas/council && pytest tests/test_handler_fargate.py -v`
Expected: FAIL.

- [ ] **Step 3: Rewrite handler.py**

Replace the Lambda-shape `handler.py` with the Fargate poll-handler:

```python
# lambdas/council/src/council/handler.py
"""Council Fargate handler: poll pending sessions, run advisors, write decisions."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import traceback
from datetime import datetime, timezone
from typing import Any

from council.enums import CouncilStatus
from council.orchestrator import run_council_session_async

logger = logging.getLogger("council.handler")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit_pipeline_error(
    blackboard: Any,
    project_id: str,
    session_id: str,
    wave_id: str,
    phase: str,
    error_class: str,
    error_message: str,
    traceback_head: str = "",
    final: bool = False,
) -> None:
    now = _now()
    blackboard.write_event(event_item={
        "PK": f"P#{project_id}",
        "SK": f"E#{now}#{session_id[-8:]}",
        "event_type": "council_pipeline_error",
        "phase": phase,
        "error_class": error_class,
        "error_message": error_message[:1000],
        "traceback_head": traceback_head[:1000],
        "wave_id": wave_id,
        "session_id": session_id,
        "final": final,
        "created_at": now,
    })
    logger.error(json.dumps({
        "event": "council_pipeline_error",
        "phase": phase,
        "wave_id": wave_id,
        "session_id": session_id,
        "error_class": error_class,
        "final": final,
    }))


async def process_pending_session(
    blackboard: Any,
    project_id: str,
    session_sk: str,
) -> None:
    """Process one pending Council session: load packet, run, write decision."""
    session = blackboard.read(f"P#{project_id}", session_sk)
    if not session or session.get("status") != "pending":
        return

    session_id = session_sk.replace("COUNCIL#", "")
    wave_id = session["wave_id"]

    # Mark running
    blackboard.update_item(
        pk=f"P#{project_id}", sk=session_sk,
        updates={"status": "running", "started_at": _now()},
    )

    # Load integration findings
    findings = blackboard.read(f"P#{project_id}", session["integration_sk"])
    if not findings:
        _emit_pipeline_error(
            blackboard=blackboard, project_id=project_id, session_id=session_id,
            wave_id=wave_id, phase="council-load-findings",
            error_class="MissingFindings",
            error_message=f"no INTEGRATION row at {session['integration_sk']}",
            final=True,
        )
        blackboard.update_item(
            pk=f"P#{project_id}", sk=session_sk,
            updates={"status": "errored", "completed_at": _now()},
        )
        return

    # Build packet + context
    packet = {
        "wave_id": wave_id,
        "project_id": project_id,
        "integration_findings": findings,
        "pr_numbers": findings.get("pr_numbers", []),
    }
    context = {
        "repo_path": os.environ.get("REPO_PATH", "/mnt/repos/T/dev-tenant/repo"),
        "repo": os.environ.get("GITHUB_REPO", ""),
        "github_token": os.environ.get("GITHUB_TOKEN", ""),
        "worktree_paths": {int(k): v for k, v in findings.get("worktree_paths", {}).items()},
        "integration_path": findings.get("integration_worktree", ""),
    }

    # Run advisors
    pipeline_errors = 0
    try:
        result = await run_council_session_async(packet=packet, context=context)
    except Exception as e:  # noqa: BLE001
        _emit_pipeline_error(
            blackboard=blackboard, project_id=project_id, session_id=session_id,
            wave_id=wave_id, phase="council-orchestrator",
            error_class=type(e).__name__, error_message=str(e),
            traceback_head=traceback.format_exc()[:1000],
            final=True,
        )
        blackboard.update_item(
            pk=f"P#{project_id}", sk=session_sk,
            updates={"status": "errored", "completed_at": _now()},
        )
        return

    # Reflection (deterministic, never fails the decision)
    try:
        from council.reflection import extract_learnings
        learnings = extract_learnings(result)
        from council.memory_store import save_learnings
        save_learnings(blackboard=blackboard, project_id=project_id, learnings=learnings)
    except Exception as e:  # noqa: BLE001
        _emit_pipeline_error(
            blackboard=blackboard, project_id=project_id, session_id=session_id,
            wave_id=wave_id, phase="council-reflection",
            error_class=type(e).__name__, error_message=str(e),
            traceback_head=traceback.format_exc()[:1000],
            final=False,
        )
        pipeline_errors += 1

    # Write the final decision
    pipeline_health = "degraded" if pipeline_errors >= 2 else "ok"
    blackboard.update_item(
        pk=f"P#{project_id}", sk=session_sk,
        updates={
            "status": "completed",
            "completed_at": _now(),
            "decision": result.decision.to_dict(),
            "rounds": [r.to_dict() for r in result.rounds],
            "cost": result.total_cost.to_dict(),
            "pipeline_health": pipeline_health,
        },
    )

    # Emit council_decision event
    blackboard.write_event(event_item={
        "PK": f"P#{project_id}",
        "SK": f"E#{_now()}#{session_id[-8:]}",
        "event_type": "council_decision",
        "wave_id": wave_id,
        "session_id": session_id,
        "decision_action": result.decision.action.value,
        "confidence": result.decision.confidence,
        "pipeline_health": pipeline_health,
        "created_at": _now(),
    })
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd lambdas/council && pytest tests/test_handler_fargate.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lambdas/council/src/council/handler.py lambdas/council/tests/test_handler_fargate.py
git commit -m "feat(council): Fargate session handler with loud-failure pipeline_error emission"
```

### Task 25: Council Fargate entrypoint shim + Dockerfile

**Files:**
- Create: `apps/council/main.py`
- Create: `apps/council/Dockerfile`
- Create: `apps/council/requirements.txt`

- [ ] **Step 1: Create the poll-loop entrypoint**

```python
# apps/council/main.py
"""ECS Fargate entrypoint — polls for pending Council sessions."""

from __future__ import annotations

import asyncio
import logging
import os
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("council-loop")

from council.handler import process_pending_session
from council._blackboard import Blackboard

POLL_INTERVAL_SECONDS = 10


async def poll_once(blackboard: Blackboard) -> int:
    """Find one pending COUNCIL# session and process it."""
    # Scan for pending sessions across all projects (small volume; refine with GSI later)
    items = blackboard.scan_pending_council_sessions()
    if not items:
        return 0
    item = items[0]
    project_id = item["PK"].replace("P#", "")
    await process_pending_session(
        blackboard=blackboard,
        project_id=project_id,
        session_sk=item["SK"],
    )
    return 1


def main() -> None:
    logger.info("Council Fargate starting continuous poll loop")
    blackboard = Blackboard(
        table_name=os.environ["TABLE_NAME"],
        events_table_name=os.environ["EVENTS_TABLE_NAME"],
    )
    while True:
        try:
            processed = asyncio.run(poll_once(blackboard))
            if processed:
                logger.info(f"Poll: processed={processed}")
        except Exception as e:
            logger.error(f"Poll error: {e}", exc_info=True)
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Add scan helper to blackboard**

In `lambdas/council/src/council/_blackboard.py`, add a method (or replace if exists):

```python
def scan_pending_council_sessions(self) -> list[dict[str, Any]]:
    """Find COUNCIL# rows with status=pending. Small scan for M2; replace with GSI later."""
    response = self.table.scan(
        FilterExpression="begins_with(SK, :sk) AND #s = :status",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":sk": "COUNCIL#", ":status": "pending"},
        Limit=10,
    )
    return response.get("Items", [])
```

- [ ] **Step 3: Create Dockerfile**

```dockerfile
# apps/council/Dockerfile
FROM --platform=linux/amd64 python:3.12-slim

WORKDIR /app

# Install git for any future repo introspection from inside the container
RUN apt-get update && apt-get install -y --no-install-recommends git curl \
    && rm -rf /var/lib/apt/lists/*

COPY apps/council/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the council package
COPY lambdas/council/src/council /app/council
COPY apps/council/main.py /app/main.py

ENV PYTHONPATH=/app

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import council" || exit 1

CMD ["python", "/app/main.py"]
```

- [ ] **Step 4: Create requirements.txt**

```
# apps/council/requirements.txt
anthropic>=0.40.0
boto3>=1.35.0
```

- [ ] **Step 5: Commit**

```bash
git add apps/council/ lambdas/council/src/council/_blackboard.py
git commit -m "feat(council): Fargate poll-loop entrypoint + Dockerfile"
```

### Task 26: CDK — add Council Fargate service (new task definition, IAM, SG)

**Files:**
- Modify: `infra/lib/cawnex-stack.ts`

- [ ] **Step 1: Sketch the CDK changes**

Open `infra/lib/cawnex-stack.ts`. Find where the existing Worker Fargate service is defined and the existing Council Lambda is defined.

Add a new section for Council Fargate after the Worker block:

```typescript
// === COUNCIL FARGATE SERVICE ===

const councilTaskRole = new iam.Role(this, "CouncilTaskRole", {
  roleName: `cawnex-council-${props.stage}`,
  assumedBy: new iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
});
mainTable.grantReadData(councilTaskRole);
eventsTable.grantReadWriteData(councilTaskRole);
councilTaskRole.addToPolicy(new iam.PolicyStatement({
  actions: ["dynamodb:UpdateItem"],
  resources: [mainTable.tableArn],
  conditions: {
    "ForAllValues:StringLike": {
      "dynamodb:LeadingKeys": ["COUNCIL#*", "MEM#*"],
    },
  },
}));
anthropicSecret.grantRead(councilTaskRole);

const councilSG = new ec2.SecurityGroup(this, "CouncilServiceSG", {
  vpc,
  description: "Council Fargate egress-only",
  allowAllOutbound: true,
});

const councilAccessPoint = repoFs.addAccessPoint("CouncilTenantAP", {
  path: "/T/dev-tenant",
  createAcl: { ownerUid: "1000", ownerGid: "1000", permissions: "0750" },
  posixUser: { uid: "1000", gid: "1000" },
});

const councilTaskDef = new ecs.FargateTaskDefinition(this, "CouncilTaskDef", {
  family: `cawnex-council-${props.stage}`,
  cpu: 512,
  memoryLimitMiB: 1024,
  taskRole: councilTaskRole,
  volumes: [{
    name: "repos",
    efsVolumeConfiguration: {
      fileSystemId: repoFs.fileSystemId,
      transitEncryption: "ENABLED",
      authorizationConfig: {
        accessPointId: councilAccessPoint.accessPointId,
        iam: "ENABLED",
      },
    },
  }],
});

const councilContainer = councilTaskDef.addContainer("council", {
  image: ecs.ContainerImage.fromAsset("../", {
    file: "apps/council/Dockerfile",
  }),
  environment: {
    TABLE_NAME: mainTable.tableName,
    EVENTS_TABLE_NAME: eventsTable.tableName,
    AWS_REGION: this.region,
  },
  secrets: {
    ANTHROPIC_AUTH_TOKEN: ecs.Secret.fromSecretsManager(anthropicSecret),
  },
  logging: ecs.LogDrivers.awsLogs({
    streamPrefix: "council",
    logRetention: logs.RetentionDays.ONE_MONTH,
  }),
});
councilContainer.addMountPoints({
  containerPath: "/mnt/repos",
  sourceVolume: "repos",
  readOnly: true,
});

const councilService = new ecs.FargateService(this, "CouncilService", {
  serviceName: `cawnex-council-${props.stage}`,
  cluster,
  taskDefinition: councilTaskDef,
  desiredCount: 0,  // scaled by reactor on COUNCIL# inserts
  assignPublicIp: props.stage !== "prod",
  securityGroups: [councilSG],
});
repoFs.connections.allowDefaultPortFrom(councilService);
```

- [ ] **Step 2: Make CDK build**

```bash
cd infra && npm run build
```

Expected: clean compile.

- [ ] **Step 3: Synth to validate**

```bash
cd infra && npx cdk synth -c stage=dev > /tmp/synth.yaml
grep -A 2 "cawnex-council-dev" /tmp/synth.yaml | head -20
```

Expected: see the new Council resources in the synthesized template.

- [ ] **Step 4: Commit**

```bash
git add infra/lib/cawnex-stack.ts
git commit -m "feat(infra): add Council Fargate service (separate task, read-only IAM, EFS RO)"
```

### Task 27: Council scaler — bump desiredCount on COUNCIL# INSERT

**Files:**
- Modify: `infra/lib/cawnex-stack.ts`
- Modify: `lambdas/worker-scaler/src/handler.py` (extend existing scaler)

Use the existing worker-scaler pattern. Modify it to also bump the Council service when pending COUNCIL# rows exist.

- [ ] **Step 1: Inspect the existing worker scaler**

```bash
cat lambdas/worker-scaler/src/handler.py 2>/dev/null || find /Users/eaugusto/cawnex -path '*worker-scaler*' -type f -name '*.py'
```

- [ ] **Step 2: Extend it to also scale council**

Adjust the scaler's polling logic to count pending COUNCIL# rows in addition to pending crow tasks. If any pending COUNCIL# rows exist, set `cawnex-council-${stage}` desiredCount to 1. If none, set to 0.

(Step 2 code depends on the existing scaler's shape; the implementer should follow the same pattern as the existing worker scale logic, just with a different service name and SK prefix.)

- [ ] **Step 3: Build + test**

```bash
cd lambdas/worker-scaler && pytest tests/ -v
```

- [ ] **Step 4: Commit**

```bash
git add lambdas/worker-scaler/ infra/lib/cawnex-stack.ts
git commit -m "feat(scaler): scale Council Fargate based on pending COUNCIL# rows"
```

### M2 wrap-up

- [ ] **Step 1: Run all tests**

```bash
pytest lambdas/council/tests/ -v
pytest lambdas/worker-scaler/tests/ -v
pytest tests/integration/ -v
```

Expected: all pass.

- [ ] **Step 2: CDK synth sanity check**

```bash
cd infra && npx cdk synth -c stage=dev 2>&1 | tail -5
```

Expected: no errors.

---

## Milestone M3 — Reactor cleanup + Lambda delete + smoke test (~1-2 days)

### Task 28: Murder reactor `_handle_council_complete`

**Files:**
- Modify: `lambdas/murder/src/murder/reactor.py`
- Modify: `lambdas/murder/src/murder/handler.py`
- Modify: `lambdas/murder/tests/test_reactor.py`

- [ ] **Step 1: Write the failing test**

```python
# lambdas/murder/tests/test_reactor.py — add class
class TestHandleCouncilComplete:
    def test_council_completed_transitions_wave_to_under_human_review(
        self, blackboard, logger
    ):
        blackboard.write_item({
            "PK": "P#p1", "SK": "S#w1", "level": "wave",
            "status": "under_council_review", "wave_id": "w1",
        })
        session = {
            "PK": "P#p1", "SK": "COUNCIL#wr_w1_xyz",
            "status": "completed", "wave_id": "w1",
            "decision": {"action": "approve"},
        }
        from murder.reactor import react_to_council_complete
        react_to_council_complete(
            blackboard=blackboard,
            session=session,
            logger=logger,
        )
        assert blackboard.read("P#p1", "S#w1")["status"] == "under_human_review"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd lambdas/murder && pytest tests/test_reactor.py::TestHandleCouncilComplete -v`
Expected: FAIL.

- [ ] **Step 3: Implement react_to_council_complete**

Append to `lambdas/murder/src/murder/reactor.py`:

```python
def react_to_council_complete(
    blackboard: Blackboard,
    session: dict[str, Any],
    logger: StructuredLogger,
) -> None:
    """When Council writes status=completed, transition wave to under_human_review."""
    pk = session["PK"]
    wave_id = session["wave_id"]
    blackboard.update_item(
        pk=pk, sk=f"S#{wave_id}",
        updates={"status": "under_human_review"},
    )
    logger.event(
        "council_complete",
        wave_id=wave_id,
        decision_action=session.get("decision", {}).get("action"),
    )
```

- [ ] **Step 4: Wire COUNCIL# MODIFY events in handler**

Open `lambdas/murder/src/murder/handler.py`. Add a branch for COUNCIL# MODIFY where the new image's status is `completed`:

```python
elif sk.startswith("COUNCIL#") and event_name == "MODIFY":
    if new_image.get("status") == "completed":
        react_to_council_complete(
            blackboard=blackboard,
            session=new_image,
            logger=logger,
        )
```

- [ ] **Step 5: Run tests + commit**

```bash
cd lambdas/murder && pytest tests/ -v
```

```bash
git add lambdas/murder/src/murder/reactor.py lambdas/murder/src/murder/handler.py lambdas/murder/tests/test_reactor.py
git commit -m "feat(murder): transition wave to under_human_review on council completed"
```

### Task 29: Delete legacy Council Lambda from CDK

**Files:**
- Modify: `infra/lib/cawnex-stack.ts`

- [ ] **Step 1: Find the Council Lambda block in CDK**

```bash
grep -n "cawnex-council\|councilFn\|CouncilLambda" infra/lib/cawnex-stack.ts | head -20
```

- [ ] **Step 2: Two-pass migration: first deploy Fargate alongside Lambda**

Verify the new Fargate Council works on a test wave in dev BEFORE deleting the Lambda. This means: in this commit do NOT delete the Lambda yet — just confirm both exist after the M2 deploy.

- [ ] **Step 3: After verification, delete the Lambda + its event source + log group**

In a separate commit, remove the Lambda block:

```typescript
// DELETE the entire `cawnex-council-${stage}` Lambda definition,
// its DDB Stream event source mapping, and its log group.
```

- [ ] **Step 4: CDK synth, deploy to dev, verify**

```bash
cd infra && npx cdk deploy -c stage=dev --require-approval never
```

Expected: deploys cleanly. Verify in AWS console that the `cawnex-council-dev` Lambda is gone and the Fargate service is present.

- [ ] **Step 5: Commit (after dev verification)**

```bash
git add infra/lib/cawnex-stack.ts
git commit -m "chore(infra): remove legacy Council Lambda (replaced by Fargate)"
```

### Task 30: M3 manual smoke test

**Files:** None — manual procedure.

- [ ] **Step 1: Prepare a controlled synthetic wave in dev**

In a dev project:
1. Create 2 trivial MVIs (e.g. add a comment to one file each, in different files to avoid conflict).
2. Manually advance the wave through executing → review by writing ready_to_ship statuses on both MVIs.

- [ ] **Step 2: Watch the Murder reactor logs**

```bash
aws logs tail /aws/lambda/cawnex-murder-dev --follow
```

Expected: see `integrator_dispatched` event.

- [ ] **Step 3: Watch the Worker Fargate logs**

```bash
aws logs tail /ecs/cawnex-worker-dev --follow
```

Expected: see the integrator handler running, worktrees being created, checks running (or skipped for missing tools), IntegratorFindings written.

- [ ] **Step 4: Watch the Council Fargate logs**

```bash
aws logs tail /ecs/cawnex-council-dev --follow
```

Expected: see 6 advisors run in parallel, each making 3-8 tool calls, all returning votes within 180s.

- [ ] **Step 5: Inspect the CouncilDecision in DDB**

```bash
aws dynamodb get-item --table-name cawnex-dev \
  --key '{"PK":{"S":"P#<projectId>"},"SK":{"S":"COUNCIL#<sessionId>"}}' \
  --query 'Item'
```

Expected: status=completed, decision present, rounds[0].votes has 6 entries each with investigation_trace.

- [ ] **Step 6: Verify no council_pipeline_error events**

```bash
aws dynamodb query --table-name cawnex-events-dev \
  --key-condition-expression "PK = :pk AND begins_with(SK, :sk)" \
  --expression-attribute-values '{":pk":{"S":"P#<projectId>"},":sk":{"S":"E#"}}' \
  --filter-expression "event_type = :et" \
  --expression-attribute-values '{":et":{"S":"council_pipeline_error"}}'
```

Expected: empty result.

- [ ] **Step 7: Verify total cost is ~$0.21 ± 25%**

Pull the CouncilSession row, sum `cost.tokens_in * $1/1M + cost.tokens_out * $5/1M` across all 6 advisor cost records. Should land between $0.16 and $0.26.

- [ ] **Step 8: Mark Layer A done**

If all of steps 1-7 pass, Layer A is shippable. Commit a final marker:

```bash
git commit --allow-empty -m "chore(stage-4): Layer A smoke test passed on dev"
```

If any step fails: do NOT mark Layer A done. Open issues for what failed and iterate.

---

## Spec coverage check

The plan covers each Layer A spec section:

| Spec section | Plan tasks |
|---|---|
| Wave state machine extension | Task 1, 12, 13, 28 |
| IntegratorFindings data model | Task 2 |
| Integrator phases A/B/C | Tasks 3, 4, 5, 6, 7, 8, 10 |
| Loud-failure rule | Task 9 (events helper), used in Tasks 10, 24 |
| Worker dispatch on integrator | Task 11 |
| Murder reactor — wave ready | Task 12 |
| Murder reactor — integration complete | Task 13 |
| Murder reactor — council complete | Task 28 |
| Advisor enum rename | Task 15 |
| AdvisorVote extension (trace + evidence) | Task 16 |
| Tool implementations | Tasks 17, 18 |
| Tool palette + scoping | Task 19 |
| Trace builder | Task 20 |
| Anthropic streaming + tool-use loop | Task 21 |
| Per-advisor implementations | Task 22 |
| asyncio.gather orchestrator | Task 23 |
| Council session handler | Task 24 |
| Council Fargate entrypoint | Task 25 |
| CDK — Council Fargate service | Task 26 |
| Council scaler | Task 27 |
| Delete legacy Council Lambda | Task 29 |
| Smoke test | Task 30 |
| M1 integration test | Task 14 |

No spec section is unimplemented.

---

Total: **30 tasks across 3 milestones, ~10-12 days estimated.**
