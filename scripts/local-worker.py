#!/usr/bin/env python3
"""
POC 5 -- Local Crow Worker

Polls DynamoDB blackboard for pending TASK records.
Executes them locally using Claude Code CLI (subscription, $0 cost).
Writes REPORT back to blackboard, triggering Murder via Stream.

Usage:
    python scripts/local-worker.py --table cawnex-blackboard-dev --region us-east-1

Requirements:
    - AWS credentials configured (aws configure)
    - Claude Code CLI installed (npx @anthropic-ai/claude-code)
    - GitHub token in GITHUB_TOKEN env var
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time

import boto3
from boto3.dynamodb.conditions import Key as DKey, Attr

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("worker")

POLL_INTERVAL = 5  # seconds


def find_pending_tasks(table) -> list:
    """Scan for TASK records with status=pending."""
    # Note: scan is fine for POC. Production would use a GSI.
    resp = table.scan(
        FilterExpression=Attr("SK").contains("#TASK") & Attr("status").eq("pending"),
    )
    return resp.get("Items", [])


def mark_task_running(table, pk: str, sk: str):
    """Mark a task as running (prevents double pickup)."""
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
        logger.info("Task already picked up by another worker")
        return False


def execute_task(task: dict, use_cli: bool = True) -> dict:
    """Execute a task using Claude Code CLI or Anthropic SDK."""
    crow = task.get("crow", "worker")
    instructions = task.get("instructions", "")
    repo = task.get("repo", "")
    branch = task.get("branch", "")
    issue_title = task.get("issue_title", "")
    issue_number = task.get("issue_number", 0)

    logger.info("Executing: crow=%s repo=%s branch=%s", crow, repo, branch)
    logger.info("Instructions: %s", instructions[:200])

    # Build the prompt for Claude
    prompt = f"""You are a {crow} crow (AI agent) working on a software project.

## Task
{instructions}

## Context
- Repository: {repo}
- Branch: {branch}
- Issue: #{issue_number} -- {issue_title}

## Available Tools
You have access to: read files, write files, run shell commands, and git operations.

## Output Format
When done, output a JSON summary as the LAST line:
```json
{{"outcome": "completed", "summary": "what you did", "files_changed": ["file1", "file2"]}}
```
If you encounter an error you can't resolve:
```json
{{"outcome": "failed", "summary": "what went wrong"}}
```
"""

    if use_cli:
        return execute_with_cli(prompt, repo, branch)
    else:
        return execute_with_sdk(prompt)


def execute_with_cli(prompt: str, repo: str, branch: str) -> dict:
    """Run task using Claude Code CLI (uses subscription, $0 cost)."""
    # Clone/checkout the repo
    work_dir = f"/tmp/cawnex-worker/{repo.replace('/', '-')}"
    os.makedirs(work_dir, exist_ok=True)

    # Clone if needed
    if not os.path.exists(os.path.join(work_dir, ".git")):
        logger.info("Cloning %s...", repo)
        subprocess.run(
            ["git", "clone", f"https://github.com/{repo}.git", work_dir],
            capture_output=True, text=True, check=True,
        )

    # Checkout branch
    subprocess.run(["git", "fetch", "origin"], cwd=work_dir, capture_output=True)
    subprocess.run(["git", "checkout", branch], cwd=work_dir, capture_output=True)
    subprocess.run(["git", "pull", "origin", branch], cwd=work_dir, capture_output=True)

    # Run Claude Code CLI
    logger.info("Running Claude Code CLI...")
    try:
        result = subprocess.run(
            [
                "npx", "@anthropic-ai/claude-code", "--print",
                "--output-format", "text",
                prompt,
            ],
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=600,  # 10 min max
        )
        output = result.stdout
        logger.info("CLI output (%d chars): %s", len(output), output[:500])

        # Push any changes
        subprocess.run(["git", "add", "-A"], cwd=work_dir, capture_output=True)
        diff = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=work_dir, capture_output=True, text=True,
        )
        files_changed = [f for f in diff.stdout.strip().split("\n") if f]

        if files_changed:
            subprocess.run(
                ["git", "commit", "-m", f"feat: crow execution"],
                cwd=work_dir, capture_output=True,
            )
            subprocess.run(
                ["git", "push", "origin", branch],
                cwd=work_dir, capture_output=True, check=True,
            )
            logger.info("Pushed %d files: %s", len(files_changed), files_changed)

        # Try to parse JSON from output
        report = try_parse_report(output)
        if report:
            report["files_changed"] = files_changed or report.get("files_changed", [])
            return report

        return {
            "outcome": "completed" if result.returncode == 0 else "failed",
            "summary": output[:2000],
            "files_changed": files_changed,
        }

    except subprocess.TimeoutExpired:
        return {"outcome": "failed", "summary": "Task timed out after 10 minutes"}
    except Exception as e:
        return {"outcome": "failed", "summary": str(e)}


def execute_with_sdk(prompt: str) -> dict:
    """Fallback: run task using Anthropic SDK (API key, costs money)."""
    try:
        import anthropic
    except ImportError:
        return {"outcome": "failed", "summary": "anthropic package not installed. Use --cli mode or pip install anthropic"}

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "\n".join(b.text for b in response.content if b.type == "text")
    report = try_parse_report(text)
    return report or {"outcome": "completed", "summary": text[:2000]}


def try_parse_report(text: str) -> dict | None:
    """Try to extract JSON report from output."""
    # Look for last JSON block
    lines = text.strip().split("\n")
    for line in reversed(lines):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    # Try code fences
    if "```json" in text:
        parts = text.split("```json")
        for part in parts[1:]:
            if "```" in part:
                json_str = part.split("```")[0].strip()
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    continue
    return None


def write_report(table, pk: str, task_sk: str, report: dict):
    """Write REPORT to blackboard (triggers Murder via Stream)."""
    # Derive report SK from task SK: STEP#01#TASK → STEP#01#REPORT
    report_sk = task_sk.replace("#TASK", "#REPORT")

    table.put_item(Item={
        "PK": pk,
        "SK": report_sk,
        "ts": int(time.time()),
        **report,
    })

    # Update task status
    table.update_item(
        Key={"PK": pk, "SK": task_sk},
        UpdateExpression="SET #s = :s",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": "completed"},
    )

    logger.info("Report written: %s / %s → %s", pk, report_sk, report.get("outcome"))


def main():
    parser = argparse.ArgumentParser(description="Cawnex Local Crow Worker")
    parser.add_argument("--table", required=True, help="DynamoDB table name")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--once", action="store_true", help="Run once then exit (don't poll)")
    parser.add_argument("--sdk", action="store_true", help="Use Anthropic SDK instead of Claude CLI")
    args = parser.parse_args()

    dynamodb_res = boto3.resource("dynamodb", region_name=args.region)
    table = dynamodb_res.Table(args.table)

    logger.info("🐦‍⬛ Cawnex Local Worker started")
    logger.info("Table: %s | Region: %s | Mode: %s", args.table, args.region, "SDK" if args.sdk else "CLI")

    while True:
        tasks = find_pending_tasks(table)

        if tasks:
            logger.info("Found %d pending task(s)", len(tasks))
            for task in tasks:
                pk = task["PK"]
                sk = task["SK"]

                # Try to claim it
                if not mark_task_running(table, pk, sk):
                    continue

                logger.info("═" * 60)
                logger.info("Picked up: %s / %s", pk, sk)
                logger.info("Crow: %s", task.get("crow", "?"))
                logger.info("═" * 60)

                # Execute
                report = execute_task(task, use_cli=not args.sdk)

                # Write report
                write_report(table, pk, sk, report)

                logger.info("═" * 60)
                logger.info("Done: %s → %s", sk, report.get("outcome"))
                logger.info("═" * 60)
        else:
            if args.once:
                logger.info("No tasks found. Exiting (--once mode).")
                break
            # Quiet polling
            pass

        if args.once:
            break

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
