"""Core execution logic — git + context + Claude + apply + cost."""

from __future__ import annotations

import signal
from datetime import datetime, timezone
from typing import Any

import os
import re

import boto3
from boto3.dynamodb.conditions import Key as DKey

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


_SECRET_RE = re.compile(r"\{\{secret:([a-zA-Z0-9_\-]+)\}\}")
_CONTEXT_RE = re.compile(r"\{\{context:([a-zA-Z0-9_\-]+)\}\}")


def _resolve_templates(
    instructions: str,
    snapshot: dict[str, Any],
    logger: StructuredLogger,
) -> tuple[str, dict[str, str]]:
    """Resolve {{secret:...}} and {{context:...}} templates in instructions.

    Returns (resolved_instructions, env_vars_dict).
    Secrets are NOT injected into the prompt — they are set as env vars.
    Context references are resolved inline.
    """
    table_name = os.environ.get("TABLE_NAME", "cawnex")
    pk = snapshot.get("PK", "")
    env_vars: dict[str, str] = {}

    # Resolve secrets
    secret_names = _SECRET_RE.findall(instructions)
    if secret_names:
        # Extract tenant from PK
        pk_parts = pk.split("#")
        tenant = pk_parts[1] if len(pk_parts) > 1 else ""
        project = pk_parts[3] if len(pk_parts) > 3 else ""
        vault_pk = f"T#{tenant}#VAULT"

        table = boto3.resource("dynamodb").Table(table_name)
        for name in secret_names:
            vault_sk = f"P#{project}#S#{name}"
            resp = table.get_item(Key={"PK": vault_pk, "SK": vault_sk})
            item = resp.get("Item")
            if item:
                encrypted_value = item.get("encrypted_value", "")
                # Decrypt with KMS if needed
                kms_key_id = os.environ.get("VAULT_KMS_KEY_ID", "")
                if kms_key_id and isinstance(encrypted_value, bytes):
                    try:
                        kms = boto3.client("kms")
                        result = kms.decrypt(CiphertextBlob=encrypted_value)
                        decrypted = result["Plaintext"].decode("utf-8")
                    except Exception:
                        logger.warning("secret_decrypt_failed", name=name)
                        decrypted = ""
                else:
                    decrypted = str(encrypted_value)
                env_vars[f"SECRET_{name.upper()}"] = decrypted
                # Replace template with env var reference (not the actual secret)
                instructions = instructions.replace(
                    f"{{{{secret:{name}}}}}",
                    f"${{SECRET_{name.upper()}}}",
                )
            else:
                logger.warning("secret_not_found", name=name)

    # Resolve context
    context_keys = _CONTEXT_RE.findall(instructions)
    if context_keys:
        table = boto3.resource("dynamodb").Table(table_name)
        for key in context_keys:
            ctx_sk = f"CTX#{key}"
            resp = table.get_item(Key={"PK": pk, "SK": ctx_sk})
            item = resp.get("Item")
            if item:
                content = item.get("content", "")
                instructions = instructions.replace(
                    f"{{{{context:{key}}}}}",
                    content,
                )
            else:
                logger.warning("context_not_found", key=key)

    return instructions, env_vars


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

        # Resolve {{secret:...}} and {{context:...}} templates
        resolved_instructions, secret_env_vars = _resolve_templates(
            instructions, snapshot, logger,
        )
        if secret_env_vars:
            for env_key, env_val in secret_env_vars.items():
                os.environ[env_key] = env_val
            logger.event(
                "secrets_resolved", crow_id=crow_id, count=len(secret_env_vars)
            )

        user_prompt = f"## Instructions\n{resolved_instructions}\n\n## Codebase\n{context}"

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

                # Create PR or reuse existing one
                existing_pr = snapshot.get("existing_pr")
                if existing_pr:
                    # Reuse existing PR — just push commits, no new PR
                    pr_data = existing_pr
                    logger.event(
                        "pr_reused", crow_id=crow_id, pr_number=existing_pr.get("number")
                    )
                elif crow_type == CrowType.IMPLEMENTER and git_commit:
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
        # Clean up secret env vars
        for env_key in list(os.environ.keys()):
            if env_key.startswith("SECRET_"):
                del os.environ[env_key]
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
            "blocking_issues": parsed.get("blocking_issues", []),
            "non_blocking_issues": parsed.get("non_blocking_issues", []),
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
