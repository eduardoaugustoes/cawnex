"""Lambda entry point — GSI poll, claim, execute, write."""

from __future__ import annotations

from typing import Any

import boto3

from worker.blackboard import Blackboard
from worker.config import MEMORY_INJECTION_ENABLED, TABLE_NAME, ExecutionConfig
from worker.enums import CrowStatus, CrowType
from worker.keys import build_pk, build_sk
from worker.events import build_crow_completed_event, build_crow_failed_event
from worker.executor import execute
from worker.keys import parse_item_keys
from worker.logging import StructuredLogger
from worker.models import Cost, CrowSnapshot


def _memory_entries(crows: list[dict[str, Any]]) -> list[dict]:
    """Extract lightweight summaries from completed crows for memory injection."""
    entries: list[dict] = []
    for crow in crows:
        if crow.get("status") != "completed":
            continue
        outcome = crow.get("outcome", {})
        if not isinstance(outcome, dict):
            continue
        entry: dict[str, Any] = {"crow_type": crow.get("crow_type", "unknown")}
        entry["summary"] = outcome.get("summary", "")

        crow_type = entry["crow_type"]
        if crow_type == "planner":
            entry["tasks"] = outcome.get("tasks", [])
            entry["context_files"] = outcome.get("context_files", [])
        elif crow_type == "implementer":
            entry["files_changed"] = outcome.get("files_changed", [])
            entry["commit_message"] = outcome.get("commit_message", "")
        elif crow_type == "reviewer":
            entry["approved"] = outcome.get("approved", False)
            entry["issues"] = outcome.get("issues", [])
            entry["suggestions"] = outcome.get("suggestions", [])
        elif crow_type == "fixer":
            entry["files_changed"] = outcome.get("files_changed", [])
            entry["issues_addressed"] = outcome.get("issues_addressed", [])

        entries.append(entry)
    return entries


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Poll GSI for pending crows, claim and execute each."""
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(TABLE_NAME)
    blackboard = Blackboard(table)
    logger = StructuredLogger(component="worker")
    config = ExecutionConfig.from_env()

    pending = blackboard.query_gsi(index_name="GSI1", pk="DISPATCH#pending")
    logger.event("poll_complete", pending_count=len(pending))

    processed = 0
    errors = 0

    for item in pending:
        pk = item["PK"]
        sk = item["SK"]
        keys = parse_item_keys(item)
        if not keys:
            logger.warning("unparseable_keys", pk=pk, sk=sk)
            errors += 1
            continue

        crow_id = keys["crow_id"]
        crow_logger = StructuredLogger(
            component="worker",
            tenant=keys["tenant"],
            project=keys["project"],
            execution_id=crow_id,
        )

        # Claim: pending → running
        claimed = blackboard.conditional_status_update(pk, sk, "pending", "running")
        if not claimed:
            crow_logger.event("crow_skipped", reason="already claimed")
            continue

        crow_logger.event("crow_claimed", crow_id=crow_id)

        # Build snapshot dict for executor
        snapshot: dict[str, Any] = {
            "crow_type": item.get("crow_type", "implementer"),
            "crow_id": crow_id,
            "repo": item.get("repo", ""),
            "branch": item.get("branch", ""),
            "instructions": item.get("instructions", ""),
            "budget_remaining": int(item.get("budget_remaining", 0)),
        }

        # Inject memory from completed crows in this MVI (same-MVI scope)
        if config.memory_injection_enabled:
            crow_prefix = f"S#{keys['wave_id']}#m{keys['mvi_id']}#cr_"
            all_crows = blackboard.query(pk, crow_prefix)
            snapshot["memory"] = _memory_entries(all_crows)

        # Execute
        completion = execute(snapshot, logger=crow_logger, config=config)

        # Rebuild full snapshot for DynamoDB write
        crow_type = CrowType(snapshot["crow_type"])
        status = (
            CrowStatus.COMPLETED
            if completion["status"] == "completed"
            else CrowStatus.FAILED
        )
        cost = Cost.from_dict(completion["cost"])

        crow = CrowSnapshot(
            tenant=keys["tenant"],
            project=keys["project"],
            wave_id=keys["wave_id"],
            mvi_id=keys["mvi_id"],
            crow_id=crow_id,
            crow_type=crow_type,
            status=status,
            instructions=item.get("instructions", ""),
            repo=item.get("repo", ""),
            branch=item.get("branch", ""),
            budget_remaining=int(item.get("budget_remaining", 0)) - cost.credits,
            retry_count=int(item.get("retry_count", 0)),
            outcome=completion.get("outcome"),
            cost=cost,
            git_commit=completion.get("git_commit", ""),
            pr=completion.get("pr"),
            completed_at=completion["completed_at"],
        )

        # Write completed snapshot (PutItem overwrites, no GSI1 keys)
        blackboard.write_item(crow.to_item())

        # Write event record
        task_name = item.get("instructions", "")[:50]
        if status == CrowStatus.COMPLETED:
            evt = build_crow_completed_event(
                keys["tenant"],
                keys["project"],
                keys["wave_id"],
                crow_type,
                task_name,
                cost,
            )
        else:
            evt = build_crow_failed_event(
                keys["tenant"],
                keys["project"],
                keys["wave_id"],
                crow_type,
                task_name,
                completion.get("outcome", {}).get("error", "unknown"),
            )
        blackboard.write_item(evt.to_item())

        if status == CrowStatus.COMPLETED:
            processed += 1
        else:
            errors += 1

        crow_logger.event(
            "crow_written",
            crow_id=crow_id,
            status=status.value,
        )

    logger.event("batch_complete", processed=processed, errors=errors)
    return {"processed": processed, "errors": errors}
