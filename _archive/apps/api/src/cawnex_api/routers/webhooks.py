"""GitHub webhook receiver — triggers task creation from labeled issues."""

import hashlib
import hmac
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from cawnex_core.models import Repository, Task, Workflow
from cawnex_core.enums import TaskSource, TaskStatus
from cawnex_core.schemas.webhook import GitHubIssuePayload
from cawnex_api.config import settings
from cawnex_api.deps import get_db, get_redis

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

TRIGGER_LABEL = "cawnex"


def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify GitHub webhook HMAC-SHA256 signature."""
    if not secret:
        return True  # Skip verification in dev
    expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/github")
async def github_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    # Verify signature
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verify_signature(body, signature, settings.github_webhook_secret):
        raise HTTPException(401, "Invalid signature")

    event_type = request.headers.get("X-GitHub-Event", "")
    if event_type != "issues":
        return {"status": "ignored", "event": event_type}

    payload = GitHubIssuePayload.model_validate_json(body)

    # Only react to labeled events with our trigger label
    if payload.action != "labeled":
        return {"status": "ignored", "action": payload.action}

    label_names = [l.name for l in payload.issue.labels]
    if TRIGGER_LABEL not in label_names:
        return {"status": "ignored", "reason": f"no '{TRIGGER_LABEL}' label"}

    # Find the repo → tenant
    repo = (await db.execute(
        select(Repository).where(
            Repository.github_full_name == payload.repository.full_name,
            Repository.is_active.is_(True),
        )
    )).scalar_one_or_none()

    if not repo:
        return {"status": "ignored", "reason": "repo not connected"}

    # Check for duplicate
    existing = (await db.execute(
        select(Task).where(
            Task.tenant_id == repo.tenant_id,
            Task.source == TaskSource.GITHUB,
            Task.source_ref == str(payload.issue.number),
        )
    )).scalar_one_or_none()

    if existing:
        return {"status": "duplicate", "task_id": existing.id}

    # Find the workflow triggered by this event
    workflow = (await db.execute(
        select(Workflow).where(
            Workflow.tenant_id == repo.tenant_id,
            Workflow.is_active.is_(True),
        )
    )).scalar_one_or_none()

    # Create task
    task = Task(
        tenant_id=repo.tenant_id,
        workflow_id=workflow.id if workflow else None,
        source=TaskSource.GITHUB,
        source_ref=str(payload.issue.number),
        source_url=payload.issue.html_url,
        title=payload.issue.title,
        description=payload.issue.body,
        labels=json.dumps(label_names),
        status=TaskStatus.PENDING,
        context={
            "repository": payload.repository.full_name,
            "branch": payload.repository.default_branch,
            "issue_number": payload.issue.number,
        },
    )
    db.add(task)
    await db.flush()

    # Publish to Redis Stream for worker to pick up
    await redis.xadd(
        "cawnex:tasks",
        {"task_id": str(task.id), "tenant_id": str(repo.tenant_id)},
    )

    return {"status": "created", "task_id": task.id}
