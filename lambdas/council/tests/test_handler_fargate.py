"""Tests for the Fargate-side Council session processor."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from council.handler import process_pending_session


@pytest.mark.asyncio
async def test_process_pending_session_writes_completed_status() -> None:
    blackboard = MagicMock()
    blackboard.read.side_effect = [
        {
            "PK": "P#p1",
            "SK": "COUNCIL#wr_w1_xyz",
            "status": "pending",
            "wave_id": "w1",
            "integration_sk": "INTEGRATION#w1",
            "auto_mode": "off",
        },
        {
            "SK": "INTEGRATION#w1",
            "wave_id": "w1",
            "overall": "ready_for_council",
            "worktree_paths": {"42": "/.pr-42"},
            "integration_worktree": "/.integration",
            "pr_numbers": [42],
            "merge_status": "ok",
        },
    ]

    fake_result = MagicMock()
    fake_result.decision.action.value = "approve"
    fake_result.decision.to_dict.return_value = {"action": "approve"}
    fake_result.decision.confidence = 0.9
    fake_result.rounds = []
    fake_result.total_cost.to_dict.return_value = {
        "tokens_in": 100,
        "tokens_out": 50,
        "duration_ms": 0,
    }

    with patch(
        "council.handler.run_council_session_async",
        AsyncMock(return_value=fake_result),
    ), patch(
        "council.handler.extract_learnings", return_value={}
    ):
        await process_pending_session(
            blackboard=blackboard,
            project_id="p1",
            session_sk="COUNCIL#wr_w1_xyz",
        )

    update_calls = blackboard.update.call_args_list
    statuses = [c.args[2].get("status") for c in update_calls if len(c.args) >= 3]
    assert "completed" in statuses


@pytest.mark.asyncio
async def test_process_pending_session_emits_pipeline_error_when_findings_missing() -> (
    None
):
    blackboard = MagicMock()
    blackboard.read.side_effect = [
        {
            "PK": "P#p1",
            "SK": "COUNCIL#wr_w1_xyz",
            "status": "pending",
            "wave_id": "w1",
            "integration_sk": "INTEGRATION#w1",
        },
        None,
    ]

    await process_pending_session(
        blackboard=blackboard,
        project_id="p1",
        session_sk="COUNCIL#wr_w1_xyz",
    )

    blackboard.write_event.assert_called_once()
    event = blackboard.write_event.call_args.args[0]
    assert event["event_type"] == "council_pipeline_error"
    assert event["phase"] == "council-load-findings"
    assert event["final"] is True
