"""
POC 6 -- Worker Lambda (Docker + EFS + Worktrees)

Triggered by DynamoDB Stream when a TASK record is written.
Clones repo to EFS (once), creates worktree per execution,
runs Claude SDK to analyze/modify code, commits, pushes, creates PR.

Logs structured JSON to CloudWatch for centralized observability.
"""

import json
import logging
import os
import shutil
import subprocess
import time
from typing import Any

import anthropic
import boto3
from boto3.dynamodb.conditions import Key as DKey

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────
TABLE_NAME = os.environ.get("BLACKBOARD_TABLE", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
EFS_MOUNT = os.environ.get("EFS_MOUNT", "/mnt/repos")

dynamodb = boto3.resource("dynamodb")


# ─────────────────────────────────────────────
# Structured Logging
# ─────────────────────────────────────────────

def log_event(execution_id: str, event: str, **kwargs):
    """Emit structured JSON log for CloudWatch filtering."""
    logger.info(json.dumps({
        "execution_id": execution_id,
        "component": "worker",
        "event": event,
        **kwargs,
    }))


# ─────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────

def _get_claude_client() -> anthropic.Anthropic:
    """Get Anthropic client with OAuth token."""
    token = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
    if not token:
        raise RuntimeError("No auth: set ANTHROPIC_AUTH_TOKEN")

    return anthropic.Anthropic(
        api_key=None,
        auth_token=token,
        default_headers={"anthropic-beta": "oauth-2025-04-20"},
    )


# ─────────────────────────────────────────────
# Git helpers
# ─────────────────────────────────────────────

def run_git(cmd: str, cwd: str = None, check: bool = True) -> str:
    """Run a shell command, return stdout."""
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "safe.directory"
    env["GIT_CONFIG_VALUE_0"] = "*"
    if GITHUB_TOKEN:
        env["GH_TOKEN"] = GITHUB_TOKEN

    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True,
        cwd=cwd, env=env, timeout=120,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed: {cmd}\nstderr: {result.stderr}")
    return result.stdout.strip()


def ensure_repo(repo: str) -> str:
    """Clone repo to EFS if not present, otherwise fetch. Returns repo path."""
    repo_dir = os.path.join(EFS_MOUNT, repo.replace("/", "_"))
    clone_url = f"https://x-access-token:{GITHUB_TOKEN}@github.com/{repo}.git"

    # Check if we should force re-clone (e.g. after fixing shallow clone issue)
    force_reclone = os.environ.get("FORCE_RECLONE", "")

    if os.path.exists(os.path.join(repo_dir, ".git")):
        # Validate clone is healthy — also detect shallow clones
        health = run_git("git status --porcelain", cwd=repo_dir, check=False)
        is_shallow = os.path.exists(os.path.join(repo_dir, ".git", "shallow"))
        if "fatal" in health or is_shallow or force_reclone:
            reason = "corrupted" if "fatal" in health else "shallow" if is_shallow else "force_reclone"
            logger.warning("Removing repo at %s (reason=%s), will re-clone", repo_dir, reason)
            shutil.rmtree(repo_dir)
        else:
            start = time.time()
            run_git("git fetch origin", cwd=repo_dir)
            fetch_ms = int((time.time() - start) * 1000)
            file_count = run_git("git ls-tree --name-only -r HEAD | wc -l", cwd=repo_dir, check=False).strip()
            logger.info(json.dumps({
                "event": "ensure_repo_fetched", "repo": repo,
                "fetch_ms": fetch_ms, "head_files": file_count,
            }))
            return repo_dir

    # Full clone (no --depth), repo base serves as object cache for worktrees
    logger.info(json.dumps({"event": "ensure_repo_cloning", "repo": repo, "dest": repo_dir}))
    start = time.time()
    run_git(f"git clone {clone_url} {repo_dir}")
    clone_ms = int((time.time() - start) * 1000)

    # Configure git identity
    run_git('git config user.email "cawnex-worker@cawnex.ai"', cwd=repo_dir)
    run_git('git config user.name "Cawnex Worker"', cwd=repo_dir)

    file_count = run_git("git ls-tree --name-only -r HEAD | wc -l", cwd=repo_dir, check=False).strip()
    logger.info(json.dumps({
        "event": "ensure_repo_cloned", "repo": repo,
        "clone_ms": clone_ms, "head_files": file_count,
    }))
    return repo_dir


def create_worktree(repo_dir: str, execution_id: str, branch: str) -> str:
    """Create an isolated worktree for this execution."""
    worktree_dir = os.path.join(EFS_MOUNT, "worktrees", execution_id)

    # Clean up if leftover from a previous failed run
    if os.path.exists(worktree_dir):
        run_git(f"git worktree remove {worktree_dir} --force", cwd=repo_dir, check=False)
        if os.path.exists(worktree_dir):
            shutil.rmtree(worktree_dir)

    # Prune stale worktrees
    run_git("git worktree prune", cwd=repo_dir)

    # Fetch latest refs and prune stale remote-tracking branches
    run_git("git fetch --prune origin", cwd=repo_dir)

    # Clean up any local branch with same name
    run_git(f"git branch -D {branch}", cwd=repo_dir, check=False)

    # Check if branch exists remotely (previous crow already pushed)
    remote_ref = run_git(
        f"git rev-parse --verify origin/{branch}", cwd=repo_dir, check=False
    ).strip()

    if remote_ref and "fatal" not in remote_ref:
        start_ref = f"origin/{branch}"
    else:
        start_ref = "origin/main"

    wt_cmd = f"git worktree add {worktree_dir} -b {branch} {start_ref}"
    wt_output = run_git(wt_cmd, cwd=repo_dir)

    # Mark worktree as safe directory
    run_git(f"git config --global --add safe.directory {worktree_dir}", check=False)

    # Debug: verify worktree health
    wt_exists = os.path.exists(worktree_dir)
    wt_git = os.path.exists(os.path.join(worktree_dir, ".git"))
    wt_ls = os.listdir(worktree_dir) if wt_exists else []
    wt_file_count = run_git("find . -maxdepth 1 -type f | wc -l", cwd=worktree_dir, check=False).strip()
    wt_dir_count = run_git("find . -maxdepth 1 -type d | wc -l", cwd=worktree_dir, check=False).strip()
    wt_total = run_git("find . -not -path './.git/*' -type f | wc -l", cwd=worktree_dir, check=False).strip()
    wt_head = run_git("git rev-parse HEAD", cwd=worktree_dir, check=False).strip()
    logger.info(json.dumps({
        "event": "worktree_health",
        "execution_id": execution_id,
        "worktree_dir": worktree_dir,
        "start_ref": start_ref,
        "wt_cmd_output": wt_output[:200],
        "dir_exists": wt_exists,
        "git_exists": wt_git,
        "ls_top": wt_ls[:20],
        "files_depth1": wt_file_count,
        "dirs_depth1": wt_dir_count,
        "total_files": wt_total,
        "head_sha": wt_head[:12],
    }))

    # Copy git config to worktree
    run_git('git config user.email "cawnex-worker@cawnex.ai"', cwd=worktree_dir)
    run_git('git config user.name "Cawnex Worker"', cwd=worktree_dir)

    return worktree_dir


def cleanup_worktree(repo_dir: str, worktree_dir: str):
    """Remove worktree after execution."""
    try:
        run_git(f"git worktree remove {worktree_dir} --force", cwd=repo_dir, check=False)
        if os.path.exists(worktree_dir):
            shutil.rmtree(worktree_dir)
        run_git("git worktree prune", cwd=repo_dir)
    except Exception as e:
        logger.warning(f"Worktree cleanup failed: {e}")


def gather_code_context(worktree_dir: str, max_files: int = 30) -> str:
    """Read key source files from worktree for Claude context."""
    context_parts = []

    # Walk the directory tree using os.walk (not shell find — avoids EFS/NFS issues)
    SKIP_DIRS = {".git", "node_modules", ".venv", "_archive", "__pycache__", ".mypy_cache"}
    SKIP_EXTS = {".pyc", ".png", ".jpg", ".jpeg", ".gif", ".zip", ".lock", ".map", ".woff", ".ttf"}

    all_files = []
    for root, dirs, files in os.walk(worktree_dir):
        # Prune directories we don't want to traverse
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if os.path.splitext(f)[1] in SKIP_EXTS:
                continue
            rel = os.path.relpath(os.path.join(root, f), worktree_dir)
            all_files.append(rel)

    all_files.sort()
    tree = "\n".join(all_files[:200])
    context_parts.append(f"## File Tree ({len(all_files)} files)\n```\n{tree}\n```\n")

    logger.info(json.dumps({
        "event": "gather_context_walk",
        "worktree_dir": worktree_dir,
        "total_files": len(all_files),
        "sample": all_files[:10],
    }))

    # Read important files
    files_read = 0
    for filepath in all_files:
        if files_read >= max_files:
            break

        fullpath = os.path.join(worktree_dir, filepath)
        try:
            size = os.path.getsize(fullpath)
            if size > 50_000:  # Skip files > 50KB
                continue
            with open(fullpath, "r", errors="ignore") as f:
                content = f.read()
            context_parts.append(f"## {filepath}\n```\n{content}\n```\n")
            files_read += 1
        except (OSError, UnicodeDecodeError):
            continue

    return "\n".join(context_parts)


# ─────────────────────────────────────────────
# Claude execution
# ─────────────────────────────────────────────

CROW_PROMPTS = {
    "planner": """You are a planner crow. Analyze the codebase and create a detailed implementation plan.
Output a JSON object:
{
  "plan": "Detailed step-by-step plan",
  "files_to_create": ["path/to/new/file.py"],
  "files_to_modify": ["path/to/existing/file.py"],
  "summary": "One-line summary"
}""",

    "implementer": """You are an implementer crow. Write the actual code changes based on the instructions.
Output a JSON object:
{
  "changes": [
    {
      "path": "path/to/file.py",
      "action": "create" | "modify",
      "content": "Full file content"
    }
  ],
  "commit_message": "feat: description of changes",
  "summary": "What was implemented"
}""",

    "reviewer": """You are a reviewer crow. Review the code changes and provide feedback.
Output a JSON object:
{
  "approved": true | false,
  "issues": ["Issue 1", "Issue 2"],
  "suggestions": ["Suggestion 1"],
  "summary": "Review summary"
}""",
}


def execute_with_claude(crow: str, instructions: str, code_context: str) -> dict:
    """Call Claude SDK to analyze/generate code."""
    client = _get_claude_client()

    system_prompt = CROW_PROMPTS.get(crow, CROW_PROMPTS["implementer"])

    prompt = f"""## Instructions
{instructions}

## Codebase
{code_context}

Respond with ONLY the JSON object, no markdown fences."""

    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=8192,
        system=system_prompt,
        messages=[{"role": "user", "content": prompt}],
    )

    text = "\n".join(b.text for b in response.content if b.type == "text")

    return {
        "raw_output": text,
        "tokens_in": response.usage.input_tokens,
        "tokens_out": response.usage.output_tokens,
        "cost": (response.usage.input_tokens * 3 + response.usage.output_tokens * 15) / 1_000_000,
    }


def parse_changes(raw_output: str) -> dict | None:
    """Try to parse JSON from Claude's output."""
    # Strip markdown fences if present
    text = raw_output.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON in the output
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                return None
    return None


def apply_changes(worktree_dir: str, changes: list[dict]):
    """Apply file changes to the worktree."""
    for change in changes:
        filepath = os.path.join(worktree_dir, change["path"])
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        if change.get("action") == "delete":
            if os.path.exists(filepath):
                os.remove(filepath)
        else:
            with open(filepath, "w") as f:
                f.write(change["content"])


# ─────────────────────────────────────────────
# Blackboard helpers
# ─────────────────────────────────────────────

def mark_task_running(pk: str, sk: str) -> bool:
    """Conditional update: pending → running."""
    table = dynamodb.Table(TABLE_NAME)
    try:
        table.update_item(
            Key={"PK": pk, "SK": sk},
            UpdateExpression="SET #s = :r",
            ConditionExpression="#s = :p",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":r": "running", ":p": "pending"},
        )
        return True
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return False


def write_report(pk: str, sk: str, data: dict):
    """Write REPORT to blackboard (triggers Murder via Stream)."""
    table = dynamodb.Table(TABLE_NAME)
    table.put_item(Item={
        "PK": pk,
        "SK": sk,
        "ts": int(time.time()),
        **data,
    })


def mark_task_completed(pk: str, sk: str):
    """Mark task as completed."""
    table = dynamodb.Table(TABLE_NAME)
    table.update_item(
        Key={"PK": pk, "SK": sk},
        UpdateExpression="SET #s = :c",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":c": "completed"},
    )


# ─────────────────────────────────────────────
# DynamoDB Stream deserializer
# ─────────────────────────────────────────────

def deserialize_dynamodb(item: dict) -> dict:
    """Convert DynamoDB Stream format to plain dict."""
    result = {}
    for key, val in item.items():
        if "S" in val:
            result[key] = val["S"]
        elif "N" in val:
            result[key] = val["N"]
        elif "BOOL" in val:
            result[key] = val["BOOL"]
        elif "NULL" in val:
            result[key] = None
        elif "M" in val:
            result[key] = deserialize_dynamodb(val["M"])
        elif "L" in val:
            result[key] = [deserialize_dynamodb({"_": v})["_"] if isinstance(v, dict) else v for v in val["L"]]
    return result


# ─────────────────────────────────────────────
# Main handler
# ─────────────────────────────────────────────

def lambda_handler(event: dict, context: Any):
    """DynamoDB Stream trigger — picks up TASK records."""
    for record in event.get("Records", []):
        if record["eventName"] not in ("INSERT", "MODIFY"):
            continue

        new_image = deserialize_dynamodb(record["dynamodb"]["NewImage"])
        sk = new_image.get("SK", "")

        # Only react to TASK records with status=pending
        if "#TASK" not in sk or new_image.get("status") != "pending":
            continue

        pk = new_image["PK"]
        execution_id = pk.replace("EXEC#", "")

        log_event(execution_id, "task_received", crow=new_image.get("crow", ""))

        # Conditional update: pending → running
        if not mark_task_running(pk, sk):
            log_event(execution_id, "task_skipped", reason="already picked up")
            continue

        repo = new_image.get("repo", "")
        branch = new_image.get("branch", "")
        instructions = new_image.get("instructions", "")
        crow = new_image.get("crow", "worker")
        issue_number = new_image.get("issue_number", "")

        log_event(execution_id, "task_started", crow=crow, repo=repo, branch=branch)
        start_time = time.time()

        try:
            # 1. Ensure repo on EFS
            repo_dir = ensure_repo(repo)
            log_event(execution_id, "repo_ready", repo=repo)

            # 2. Create worktree
            worktree_dir = create_worktree(repo_dir, execution_id, branch)
            log_event(execution_id, "worktree_created", path=worktree_dir)

            try:
                # 3. Gather code context
                # Debug: log worktree contents
                wt_files = run_git("find . -maxdepth 3 -type f -not -path './.git/*' | head -20", cwd=worktree_dir, check=False)
                wt_branch = run_git("git rev-parse --abbrev-ref HEAD", cwd=worktree_dir, check=False).strip()
                wt_log = run_git("git log --oneline -3", cwd=worktree_dir, check=False).strip()
                log_event(execution_id, "worktree_debug",
                          crow=crow, branch=wt_branch,
                          files_sample=wt_files[:500],
                          recent_commits=wt_log[:300])

                code_context = gather_code_context(worktree_dir)
                log_event(execution_id, "code_context_gathered",
                          chars=len(code_context))

                # 4. Call Claude
                claude_start = time.time()
                result = execute_with_claude(crow, instructions, code_context)
                claude_duration = int((time.time() - claude_start) * 1000)

                log_event(execution_id, "claude_completed",
                          crow=crow,
                          tokens_in=result["tokens_in"],
                          tokens_out=result["tokens_out"],
                          cost=result["cost"],
                          duration_ms=claude_duration)

                # 5. Parse and apply changes (implementer only)
                parsed = parse_changes(result["raw_output"])
                pr_url = None
                files_changed = []

                if parsed and crow in ("implementer", "worker", "fixer"):
                    changes = parsed.get("changes", [])
                    if changes:
                        apply_changes(worktree_dir, changes)
                        files_changed = [c["path"] for c in changes]

                        # Commit and push
                        commit_msg = parsed.get("commit_message", f"feat: {crow} changes for #{issue_number}")
                        run_git("git add -A", cwd=worktree_dir)

                        # Check if there are changes to commit
                        diff = run_git("git diff --cached --name-only", cwd=worktree_dir, check=False)
                        if diff:
                            run_git(f'git commit -m "{commit_msg}"', cwd=worktree_dir)
                            push_url = f"https://x-access-token:{GITHUB_TOKEN}@github.com/{repo}.git"
                            run_git(f"git push --force {push_url} {branch}", cwd=worktree_dir)
                            log_event(execution_id, "git_pushed",
                                      branch=branch, files=len(files_changed))

                            # Create PR on final implementer step
                            try:
                                pr_title = parsed.get("summary", f"Cawnex: {crow} for #{issue_number}")
                                pr_body = f"Automated by Cawnex Worker (execution: {execution_id})\n\nCloses #{issue_number}"
                                pr_result = run_git(
                                    f'gh pr create --repo {repo} --head {branch} --base main '
                                    f'--title "{pr_title}" --body "{pr_body}"',
                                    cwd=worktree_dir, check=False
                                )
                                if "github.com" in pr_result:
                                    pr_url = pr_result.strip()
                                    log_event(execution_id, "pr_created", url=pr_url)
                            except Exception as e:
                                log_event(execution_id, "pr_failed", error=str(e))

                # 6. Write report
                report = {
                    "outcome": "completed",
                    "crow": crow,
                    "summary": (parsed or {}).get("summary", result["raw_output"][:500]),
                    "raw_output": result["raw_output"][:5000],
                    "tokens_in": result["tokens_in"],
                    "tokens_out": result["tokens_out"],
                    "cost": str(result["cost"]),
                    "files_changed": files_changed,
                    "duration_ms": int((time.time() - start_time) * 1000),
                }
                if pr_url:
                    report["pr_url"] = pr_url
                if parsed:
                    # Include structured data for planner/reviewer
                    if crow == "planner":
                        report["plan"] = (parsed or {}).get("plan", "")
                    elif crow == "reviewer":
                        report["approved"] = (parsed or {}).get("approved", False)
                        report["issues"] = (parsed or {}).get("issues", [])

                report_sk = sk.replace("#TASK", "#REPORT")
                write_report(pk, report_sk, report)
                mark_task_completed(pk, sk)

                total_duration = int((time.time() - start_time) * 1000)
                log_event(execution_id, "task_completed",
                          crow=crow, duration_ms=total_duration,
                          files_changed=len(files_changed),
                          pr_url=pr_url)

            finally:
                # 7. Cleanup worktree
                cleanup_worktree(repo_dir, worktree_dir)
                log_event(execution_id, "worktree_cleaned")

        except Exception as e:
            error_msg = str(e)
            log_event(execution_id, "task_failed", crow=crow, error=error_msg)

            # Write error report
            report_sk = sk.replace("#TASK", "#REPORT")
            write_report(pk, report_sk, {
                "outcome": "error",
                "crow": crow,
                "summary": error_msg,
                "duration_ms": int((time.time() - start_time) * 1000),
            })
            mark_task_completed(pk, sk)
