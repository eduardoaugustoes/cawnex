"""IntegratorFindings dataclass + DDB write."""

from __future__ import annotations

from dataclasses import dataclass
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
