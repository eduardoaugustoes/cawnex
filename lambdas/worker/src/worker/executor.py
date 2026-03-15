"""Core execution logic — git + context + Claude + apply + cost."""

from __future__ import annotations

import signal
from datetime import datetime, timezone
from typing import Any

from worker.claude import call_claude
from worker.config import CROW_TIMEOUT_SECONDS, ExecutionConfig
from worker.context import (
    gather_fixer_context,
    gather_implementer_context,
    gather_planner_context,
    gather_reviewer_context,
)
from worker.cost import calculate_credits
from worker.contracts import validate_crow_completion
from worker.memory import inject_memory, synthesize_memory
from worker.enums import CrowType
from worker.git_ops import (
    apply_changes,
    cleanup_worktree,
    commit_and_push,
    create_worktree,
    ensure_repo,
    run_git,
)
from worker.github import create_pr
from worker.logging import StructuredLogger
from worker.models import Cost
from worker.parsing import parse_json_output
from worker.prompts import CROW_IDENTITIES


def _build_git_diff(worktree_dir: str, base_branch: str = "main") -> tuple[str, list[str]]:
    """Build git diff and changed file list from worktree. Used by reviewer/fixer."""
    diff_content = run_git(
        f"git diff {base_branch}..HEAD", cwd=worktree_dir, check=False
    )
    changed_names = run_git(
        f"git diff --name-only {base_branch}..HEAD", cwd=worktree_dir, check=False
    )
    changed_files = [f.strip() for f in changed_names.split("\n") if f.strip()]
    return diff_content, changed_files


def _gather_context(
    crow_type: CrowType,
    worktree_dir: str,
    instructions_data: dict[str, Any],
) -> str:
    """Dispatch to the right context gatherer."""
    if crow_type == CrowType.PLANNER:
        return gather_planner_context(worktree_dir)
    if crow_type == CrowType.IMPLEMENTER:
        return gather_implementer_context(
            worktree_dir,
            files_to_read=instructions_data.get("context_files", []),
            files_to_modify=instructions_data.get("files_to_modify", []),
        )
    # Reviewer and fixer need the git diff as an artifact
    git_diff, changed_files = _build_git_diff(worktree_dir)
    if crow_type == CrowType.REVIEWER:
        return gather_reviewer_context(worktree_dir, git_diff, changed_files)
    if crow_type == CrowType.FIXER:
        return gather_fixer_context(
            worktree_dir,
            issues=instructions_data.get("issues", []),
            suggestions=instructions_data.get("suggestions", []),
            git_diff=git_diff,
            changed_files=changed_files,
        )
    return gather_planner_context(worktree_dir)


def execute(
    snapshot: dict[str, Any],
    logger: StructuredLogger,
    config: ExecutionConfig | None = None,
) -> dict[str, Any]:
    """Execute a crow. Returns completion dict (handler writes to DynamoDB).

    Does NOT write to DynamoDB. Pure logic + side effects (git, Claude).
    """
    if config is None:
        config = ExecutionConfig.from_env()

    crow_type = CrowType(snapshot["crow_type"])
    crow_id = snapshot["crow_id"]
    repo = snapshot["repo"]
    branch = snapshot["branch"]
    instructions = snapshot["instructions"]
    budget_remaining = int(snapshot.get("budget_remaining", 0))

    logger.event(
        "crow_started",
        crow_id=crow_id,
        crow_type=crow_type.value,
        repo=repo,
        branch=branch,
    )

    # Budget check
    if budget_remaining <= 0:
        logger.warning("crow_budget_exhausted", crow_id=crow_id)
        result = _build_failed(crow_type, "Budget exhausted")
        validate_crow_completion(result)
        return result

    repo_dir: str | None = None
    worktree_dir: str | None = None

    timeout = int(snapshot.get("timeout_seconds", CROW_TIMEOUT_SECONDS))

    def _timeout_handler(signum: int, frame: Any) -> None:
        raise TimeoutError(f"Crow execution exceeded {timeout}s timeout")

    prev_handler = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(timeout)

    try:
        # Git setup
        repo_dir = ensure_repo(
            repo, efs_mount=config.efs_mount, github_token=config.github_token
        )
        worktree_dir = create_worktree(
            repo_dir, crow_id, branch, efs_mount=config.efs_mount
        )
        logger.event("worktree_created", crow_id=crow_id, path=worktree_dir)

        # Gather context
        instructions_data: dict[str, Any] = {}
        if isinstance(instructions, str):
            parsed_instructions = parse_json_output(instructions)
            if isinstance(parsed_instructions, dict):
                instructions_data = parsed_instructions
        elif isinstance(instructions, dict):
            instructions_data = instructions

        context = _gather_context(crow_type, worktree_dir, instructions_data)
        logger.event("context_gathered", crow_id=crow_id, chars=len(context))

        # Build prompt
        system_prompt = CROW_IDENTITIES.get(
            crow_type.value, CROW_IDENTITIES["implementer"]
        )

        # Conditionally inject memory from previous crows in this MVI
        if config.memory_injection_enabled:
            memory_entries = snapshot.get("memory", [])
            if memory_entries:
                memory_block = synthesize_memory(memory_entries)
                system_prompt = inject_memory(system_prompt, memory_block)
                logger.event(
                    "memory_injected", crow_id=crow_id, entries=len(memory_entries)
                )

        user_prompt = f"## Instructions\n{instructions}\n\n## Codebase\n{context}"

        # Call Claude
        claude_result = call_claude(system_prompt, user_prompt)
        logger.event(
            "claude_completed",
            crow_id=crow_id,
            tokens_in=claude_result.tokens_in,
            tokens_out=claude_result.tokens_out,
            duration_ms=claude_result.duration_ms,
        )

        # Parse output
        parsed = parse_json_output(claude_result.raw_output)
        if not isinstance(parsed, dict):
            parsed = {}

        # Calculate cost
        credits = calculate_credits(claude_result.tokens_in, claude_result.tokens_out)
        cost = Cost(
            tokens_in=claude_result.tokens_in,
            tokens_out=claude_result.tokens_out,
            credits=credits,
            duration_ms=claude_result.duration_ms,
        )

        # Apply changes for implementer/fixer
        git_commit = ""
        pr_data: dict[str, Any] | None = None

        if crow_type in (CrowType.IMPLEMENTER, CrowType.FIXER):
            changes = parsed.get("changes", [])
            if changes:
                apply_changes(worktree_dir, changes)
                commit_msg = parsed.get(
                    "commit_message", f"feat: {crow_type.value} changes"
                )
                git_commit = commit_and_push(
                    worktree_dir, commit_msg, repo, branch, config.github_token
                )
                logger.event(
                    "git_pushed",
                    crow_id=crow_id,
                    branch=branch,
                    files=len(changes),
                    commit=git_commit[:12] if git_commit else "",
                )

                # Create PR for implementer only (fixer reuses existing branch)
                if crow_type == CrowType.IMPLEMENTER and git_commit:
                    try:
                        pr_title = parsed.get("summary", f"Cawnex: {crow_id}")[:256]
                        pr_body = (
                            f"Automated by Cawnex Worker\n\nCrow: {crow_id}"
                        )
                        pr_resp = create_pr(
                            repo,
                            pr_title,
                            pr_body,
                            branch,
                            token=config.github_token,
                        )
                        pr_data = {
                            "number": pr_resp.get("number"),
                            "url": pr_resp.get("html_url", ""),
                        }
                        logger.event("pr_created", crow_id=crow_id, pr=pr_data)
                    except Exception as e:
                        logger.warning("pr_failed", crow_id=crow_id, error=str(e))

        # Build completion
        now = datetime.now(timezone.utc).isoformat()
        result: dict[str, Any] = {
            "status": "completed",
            "outcome": _build_outcome(crow_type, parsed),
            "cost": cost.to_dict(),
            "completed_at": now,
        }
        if git_commit:
            result["git_commit"] = git_commit
        if pr_data:
            result["pr"] = pr_data

        validate_crow_completion(result)
        logger.event("crow_completed", crow_id=crow_id, cost=cost.to_dict())
        return result

    except Exception as e:
        logger.error("crow_failed", crow_id=crow_id, error=str(e))
        result = _build_failed(crow_type, str(e))
        validate_crow_completion(result)
        return result

    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, prev_handler)
        if repo_dir and worktree_dir:
            cleanup_worktree(repo_dir, worktree_dir)


def _build_outcome(crow_type: CrowType, parsed: dict[str, Any]) -> dict[str, Any]:
    """Build type-specific outcome from parsed Claude output."""
    if crow_type == CrowType.PLANNER:
        return {
            "tasks": parsed.get("tasks", []),
            "context_files": parsed.get("context_files", []),
            "summary": parsed.get("summary", ""),
        }
    if crow_type == CrowType.IMPLEMENTER:
        return {
            "files_changed": [c["path"] for c in parsed.get("changes", [])],
            "commit_message": parsed.get("commit_message", ""),
            "summary": parsed.get("summary", ""),
        }
    if crow_type == CrowType.REVIEWER:
        return {
            "approved": parsed.get("approved", False),
            "issues": parsed.get("issues", []),
            "suggestions": parsed.get("suggestions", []),
            "summary": parsed.get("summary", ""),
        }
    if crow_type == CrowType.FIXER:
        return {
            "files_changed": [c["path"] for c in parsed.get("changes", [])],
            "commit_message": parsed.get("commit_message", ""),
            "summary": parsed.get("summary", ""),
            "issues_addressed": parsed.get("issues_addressed", []),
        }
    return {"summary": parsed.get("summary", "")}


def _build_failed(crow_type: CrowType, error: str) -> dict[str, Any]:
    """Build a failed completion dict."""
    return {
        "status": "failed",
        "outcome": {"error": error, "crow_type": crow_type.value},
        "cost": Cost.zero().to_dict(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
