"""AI chat proxy — forwards Claude calls, tracks cost per project.

The iOS app owns conversation state and system prompts.
This endpoint is a thin proxy that:
1. Adds the Anthropic auth token (kept server-side)
2. Tracks token usage and cost per project
3. Returns Claude's response

No conversation persistence — the app manages that.
"""

from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.auth.dependencies import get_tenant
from src.auth.tenant import TenantContext
from src.claude.client import DEFAULT_MODEL, ChatResult, chat
from src.db.client import TenantDB

router = APIRouter(prefix="/ai", tags=["ai"])


class ChatMessageRequest(BaseModel):
    """A single message in the conversation."""

    role: Literal["user", "assistant"]
    content: str


class AIChatRequest(BaseModel):
    """Request body for the AI chat proxy."""

    system: str
    messages: List[ChatMessageRequest]
    model: str = DEFAULT_MODEL
    max_tokens: int = 2048
    project_id: Optional[str] = None


class AIChatResponse(BaseModel):
    """Response from the AI chat proxy."""

    content: str
    tokens_in: int
    tokens_out: int
    cost_usd: str
    model: str
    duration_ms: int


@router.post("/chat", response_model=AIChatResponse)
async def ai_chat(
    body: AIChatRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Dict[str, Any]:
    """Proxy a Claude API call. Tracks cost per project if project_id provided."""
    try:
        result = chat(
            system=body.system,
            messages=[{"role": m.role, "content": m.content} for m in body.messages],
            model=body.model,
            max_tokens=body.max_tokens,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Claude API error: {str(e)}")

    # Track cost on project if provided
    if body.project_id:
        _track_cost(tenant, body.project_id, result)

    return {
        "content": result.content,
        "tokens_in": result.tokens_in,
        "tokens_out": result.tokens_out,
        "cost_usd": str(result.cost_usd),
        "model": result.model,
        "duration_ms": result.duration_ms,
    }


def _track_cost(tenant: TenantContext, project_id: str, result: ChatResult) -> None:
    """Increment AI cost tracking on the project root snapshot."""
    try:
        db = TenantDB(tenant)
        now = datetime.now(timezone.utc).isoformat()

        # Atomic increment of cost fields on project snapshot
        table = db._table
        pk = db.project_pk(project_id)
        table.update_item(
            Key={"PK": pk, "SK": "S#"},
            UpdateExpression=(
                "ADD ai_tokens_in :tin, ai_tokens_out :tout, ai_cost_usd :cost, "
                "ai_call_count :one SET updated_at = :now"
            ),
            ExpressionAttributeValues={
                ":tin": result.tokens_in,
                ":tout": result.tokens_out,
                ":cost": result.cost_usd,
                ":one": 1,
                ":now": now,
            },
        )
    except Exception:
        pass  # Cost tracking failure should never block the response
