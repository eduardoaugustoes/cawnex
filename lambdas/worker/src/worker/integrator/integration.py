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

    add_result = subprocess.run(
        [
            "git",
            "-C",
            repo_path,
            "worktree",
            "add",
            "-B",
            integration_branch,
            integration_path,
            "origin/main",
        ],
        capture_output=True,
    )
    if add_result.returncode != 0:
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
            [
                "git",
                "-C",
                integration_path,
                "merge",
                "--no-ff",
                "-m",
                f"Integrate PR #{pr_number}",
                f"origin/pr-{pr_number}",
            ],
            capture_output=True,
        )
        if merge_result.returncode != 0:
            files_result = subprocess.run(
                [
                    "git",
                    "-C",
                    integration_path,
                    "diff",
                    "--name-only",
                    "--diff-filter=U",
                ],
                capture_output=True,
            )
            files = [f for f in files_result.stdout.decode().splitlines() if f]

            hunks: list[str] = []
            if files:
                hunk_result = subprocess.run(
                    ["git", "-C", integration_path, "diff", files[0]],
                    capture_output=True,
                )
                hunk_text = hunk_result.stdout.decode()[:500]
                if hunk_text:
                    hunks.append(hunk_text)

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
