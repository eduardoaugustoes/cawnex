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
from worker.tools import (
    IMPLEMENTER_SUBMIT_RESULT_SCHEMA,
    PLANNER_SUBMIT_RESULT_SCHEMA,
    REVIEWER_SUBMIT_RESULT_SCHEMA,
    WORKTREE_TOOL_SCHEMAS,
    WorktreeTools,
)


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


def _build_git_diff(
    worktree_dir: str, base_branch: str = "origin/main"
) -> tuple[str, list[str]]:
    """Build git diff and changed file list from worktree. Used by reviewer/fixer.

    Always diff against `origin/main` rather than the worker's local `main`
    ref — the local ref can be days/weeks behind origin (we only `git fetch`,
    never check out main) and produces phantom diffs of unrelated commits
    when the wave branch has no commits of its own.
    """
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
) -> tuple[str, dict[str, Any]]:
    """Dispatch to the right context gatherer. Returns (context, audit)."""
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

        context, context_audit = _gather_context(
            crow_type, worktree_dir, instructions_data
        )
        logger.event(
            "context_gathered",
            crow_id=crow_id,
            chars=len(context),
            files_read=context_audit.get("files_read", []),
            files_failed=context_audit.get("files_failed", []),
            failure_reasons=context_audit.get("failure_reasons", {}),
        )

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

        # Every crow now uses the `submit_result` terminator tool so the
        # final output is server-validated structured JSON. Implementer and
        # fixer additionally get worktree read tools because they iterate
        # over files before producing the output; planner and reviewer go
        # single-call. force_terminator_tool tells the API the model MUST
        # call a tool every turn — combined with the terminator, that makes
        # the "model returned prose instead of JSON" failure mode impossible.
        worktree_tools: WorktreeTools | None = None
        tool_schemas: list[dict[str, Any]] | None = None
        force_terminator: str | None = None
        if crow_type in (CrowType.IMPLEMENTER, CrowType.FIXER):
            worktree_tools = WorktreeTools(worktree_dir=worktree_dir, logger=logger)
            tool_schemas = [*WORKTREE_TOOL_SCHEMAS, IMPLEMENTER_SUBMIT_RESULT_SCHEMA]
            force_terminator = "submit_result"
        elif crow_type == CrowType.PLANNER:
            tool_schemas = [PLANNER_SUBMIT_RESULT_SCHEMA]
            force_terminator = "submit_result"
        elif crow_type == CrowType.REVIEWER:
            tool_schemas = [REVIEWER_SUBMIT_RESULT_SCHEMA]
            force_terminator = "submit_result"

        # max_tokens is the per-response output ceiling. Planner/reviewer emit
        # short JSON (tasks list, review verdict) and 8K is plenty. Implementer
        # and fixer serialize entire file contents into JSON, so they need a
        # higher ceiling. call_claude further caps this to the model's actual
        # max_output_tokens and remaining context headroom, so the caller's
        # intent is the upper bound, not a hard requirement.
        max_tokens = 32_768 if crow_type in (CrowType.IMPLEMENTER, CrowType.FIXER) else 8192

        # Call Claude
        claude_result = call_claude(
            system_prompt,
            user_prompt,
            max_tokens=max_tokens,
            tools=tool_schemas,
            tool_executor=worktree_tools,
            force_terminator_tool=force_terminator,
        )
        logger.event(
            "claude_completed",
            crow_id=crow_id,
            tokens_in=claude_result.tokens_in,
            tokens_out=claude_result.tokens_out,
            cache_creation=claude_result.cache_creation,
            cache_read=claude_result.cache_read,
            duration_ms=claude_result.duration_ms,
            turns=claude_result.turns,
            tool_calls=len(claude_result.tool_calls),
        )
        if worktree_tools is not None:
            logger.event(
                "crow_files_read",
                crow_id=crow_id,
                files=sorted(worktree_tools.files_read),
                count=len(worktree_tools.files_read),
            )

        # Parse output. Prefer `structured_output` (set when Claude called the
        # submit_result terminator tool — server-validated JSON, guaranteed to
        # match the schema) over text-parsing the raw_output. Falls back to
        # text parsing for crow types that don't use the terminator tool.
        if claude_result.structured_output is not None:
            parsed = claude_result.structured_output
            parse_source = "structured_output"
        else:
            parsed = parse_json_output(claude_result.raw_output)
            if not isinstance(parsed, dict):
                parsed = {}
            parse_source = "raw_text"

        # Always log the raw output (truncated) so future diagnostics can see what
        # Claude actually wrote. Without this we have no way to investigate
        # silent JSON parse failures or missing schema keys.
        raw_preview = claude_result.raw_output[:2000] if claude_result.raw_output else ""
        logger.event(
            "raw_output_preview",
            crow_id=crow_id,
            raw_chars=len(claude_result.raw_output),
            parse_source=parse_source,
            parsed_keys=sorted(parsed.keys()),
            preview=raw_preview,
        )

        # Calculate cost
        credits = calculate_credits(claude_result.tokens_in, claude_result.tokens_out)
        cost = Cost(
            tokens_in=claude_result.tokens_in,
            tokens_out=claude_result.tokens_out,
            credits=credits,
            duration_ms=claude_result.duration_ms,
        )

        # Guard: implementer/fixer that produced no `changes` must fail the
        # crow. Otherwise Murder will advance to reviewer and the reviewer
        # will diff against a stale `main` ref, producing phantom approvals.
        if crow_type in (CrowType.IMPLEMENTER, CrowType.FIXER):
            changes_list = parsed.get("changes")
            if not isinstance(changes_list, list) or len(changes_list) == 0:
                # Distinguish "ran out of tokens mid-JSON" (max_tokens stop_reason)
                # from "model wrote prose instead of JSON" — the operator needs
                # to know whether to raise the cap or tighten the prompt.
                if claude_result.truncated:
                    reason = (
                        f"{crow_type.value} output truncated at max_tokens "
                        f"({claude_result.tokens_out} tokens generated) — raise "
                        f"max_tokens or split the MVI into smaller tasks"
                    )
                    failure_event_reason = "truncated"
                else:
                    reason = (
                        f"{crow_type.value} produced no file changes — output had "
                        f"keys {sorted(parsed.keys())} but no `changes` array"
                    )
                    failure_event_reason = "empty_changes"
                logger.event(
                    "crow_empty_changes",
                    crow_id=crow_id,
                    crow_type=crow_type.value,
                    parsed_keys=sorted(parsed.keys()),
                    truncated=claude_result.truncated,
                    tokens_out=claude_result.tokens_out,
                )
                now_fail = datetime.now(timezone.utc).isoformat()
                fail_outcome = _build_failed(crow_type, reason)
                fail_result: dict[str, Any] = {
                    **fail_outcome,
                    "cost": cost.to_dict(),
                    "completed_at": now_fail,
                }
                validate_crow_completion(fail_result)
                logger.event("crow_failed", crow_id=crow_id, reason=failure_event_reason)
                return fail_result

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
        outcome_dict = _build_outcome(crow_type, parsed)
        # Stash PR info inside outcome too — the reactor reads outcome.pr_number
        # to propagate it onto the parent MVI row so the integrator dispatch +
        # iOS PR card don't have to fall back to scanning implementer crows.
        if pr_data and crow_type == CrowType.IMPLEMENTER:
            pr_number = pr_data.get("number")
            if pr_number is not None:
                outcome_dict["pr_number"] = pr_number
                outcome_dict["pr_url"] = pr_data.get("url", "")
        result: dict[str, Any] = {
            "status": "completed",
            "outcome": outcome_dict,
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
