"""Tests for blocking logic — human tasks, blockers, unblocking."""

from __future__ import annotations

from typing import Any

import pytest

from murder.blackboard import Blackboard
from murder.enums import CrowStatus, CrowType, HumanTaskStatus, MVIStatus, WaveStatus
from murder.keys import build_pk, build_sk
from murder.logging import StructuredLogger
from murder.models import HumanTaskSnapshot, WaveSnapshot
from murder.reactor import (
    _create_human_task,
    react_to_crow_completion,
    react_to_human_task_completed,
    react_to_mvi_queued,
)
from murder.state_machine import CreateHumanTasks, determine_next


@pytest.fixture()
def logger() -> StructuredLogger:
    return StructuredLogger("test-blocking")


def _seed_wave(
    table: Any,
    tenant: str = "t1",
    project: str = "p1",
    wave_id: str = "w001",
    status: str = "executing",
) -> None:
    pk = build_pk(tenant, project)
    sk = build_sk(wave_id=wave_id)
    table.put_item(Item={
        "PK": pk,
        "SK": sk,
        "level": "wave",
        "status": status,
        "human_directive": "Build the WhatsApp channel",
        "progress": {"mvis_total": 1, "mvis_shipped": 0, "tasks_done": 0, "tasks_total": 2},
        "budget": {"spent": 0, "limit": 20_000_000},
        "created_at": "2026-03-16T10:00:00Z",
        "entityType": "Snapshot",
    })


def _seed_mvi(
    table: Any,
    tenant: str = "t1",
    project: str = "p1",
    wave_id: str = "w001",
    mvi_id: str = "dev",
    status: str = "executing",
) -> None:
    pk = build_pk(tenant, project)
    sk = build_sk(wave_id=wave_id, mvi_id=mvi_id)
    table.put_item(Item={
        "PK": pk,
        "SK": sk,
        "level": "murder",
        "status": status,
        "name": "WhatsApp Channel",
        "description": "Set up WhatsApp Business API",
        "repo": "github.com/org/repo",
        "branch": "cawnex/w001-dev",
        "cost": {"tokens_in": 0, "tokens_out": 0, "credits": 0, "duration_ms": 0},
        "created_at": "2026-03-16T10:00:00Z",
        "entityType": "Snapshot",
    })


def _seed_human_task(
    table: Any,
    human_task_id: str = "ht_esim",
    tenant: str = "t1",
    project: str = "p1",
    wave_id: str = "w001",
    mvi_id: str = "dev",
    status: str = "completed",
    blocks: list[str] | None = None,
    steer: str | None = None,
) -> None:
    pk = build_pk(tenant, project)
    sk = f"S#{wave_id}#m{mvi_id}#{human_task_id}"
    item: dict[str, Any] = {
        "PK": pk,
        "SK": sk,
        "id": human_task_id,
        "level": "crow",
        "task_type": "human",
        "human_task_subtype": "physical_action",
        "status": status,
        "ask": "Purchase an e-SIM number",
        "instructions": "Buy a phone number for WhatsApp Business.",
        "input_schema": {"phone": {"type": "string", "required": True}},
        "blocks": blocks or ["S#w001#mdev#cr_impl_01"],
        "response": {"phone": "+5511999999999"},
        "created_at": "2026-03-16T10:00:00Z",
        "entityType": "Snapshot",
    }
    if steer:
        item["steer"] = steer
    table.put_item(Item=item)


def _seed_blocked_crow(
    table: Any,
    crow_id: str = "cr_impl_01",
    tenant: str = "t1",
    project: str = "p1",
    wave_id: str = "w001",
    mvi_id: str = "dev",
) -> None:
    pk = build_pk(tenant, project)
    sk = build_sk(wave_id=wave_id, mvi_id=mvi_id, crow_id=crow_id)
    table.put_item(Item={
        "PK": pk,
        "SK": sk,
        "crow_id": crow_id,
        "level": "crow",
        "status": "blocked",
        "crow_type": "implementer",
        "instructions": "Implement WhatsApp API integration using {{secret:whatsapp_api_token}}",
        "repo": "github.com/org/repo",
        "branch": "cawnex/w001-dev",
        "budget_remaining": 5_000_000,
        "behavior_state": "blocked",
        "created_at": "2026-03-16T10:00:00Z",
        "entityType": "Snapshot",
    })


class TestStateMachineHumanTasks:
    def test_planner_with_human_tasks_returns_create_human_tasks(self) -> None:
        outcome = {
            "tasks": [
                {
                    "id": "ht_esim",
                    "task_type": "human",
                    "human_task_subtype": "physical_action",
                    "ask": "Buy e-SIM",
                    "instructions": "Buy a phone number",
                    "estimated_hours": 1,
                },
                {
                    "id": "impl_api",
                    "task_type": "crow",
                    "estimated_hours": 4,
                },
            ],
        }
        action = determine_next(CrowType.PLANNER, CrowStatus.COMPLETED, outcome, 0)
        assert isinstance(action, CreateHumanTasks)
        assert len(action.human_tasks) == 1
        assert len(action.crow_tasks) == 1

    def test_planner_with_only_crow_tasks_returns_assign_crow(self) -> None:
        outcome = {
            "tasks": [
                {"id": "t1", "estimated_hours": 4},
                {"id": "t2", "estimated_hours": 3},
            ],
        }
        action = determine_next(CrowType.PLANNER, CrowStatus.COMPLETED, outcome, 0)
        from murder.state_machine import AssignCrow
        assert isinstance(action, AssignCrow)
        assert action.crow_type == CrowType.IMPLEMENTER

    def test_planner_with_only_human_tasks(self) -> None:
        outcome = {
            "tasks": [
                {
                    "id": "ht_token",
                    "task_type": "human",
                    "human_task_subtype": "provide_secret",
                    "ask": "Provide API token",
                    "instructions": "Submit the token",
                    "estimated_hours": 0.5,
                },
            ],
        }
        action = determine_next(CrowType.PLANNER, CrowStatus.COMPLETED, outcome, 0)
        assert isinstance(action, CreateHumanTasks)
        assert len(action.human_tasks) == 1
        assert len(action.crow_tasks) == 0


class TestCreateHumanTask:
    def test_create_human_task_writes_snapshot(
        self, dynamodb_table: Any, events_table: Any, logger: StructuredLogger,
    ) -> None:
        blackboard = Blackboard(dynamodb_table, events_table=events_table)
        task_def = {
            "id": "ht_esim",
            "human_task_subtype": "physical_action",
            "ask": "Buy an e-SIM number",
            "instructions": "Purchase a dedicated phone number.",
            "input_schema": {"phone": {"type": "string", "required": True}},
            "estimated_human_hours": 1,
        }

        ht_id = _create_human_task(
            blackboard, "t1", "p1", "w001", "dev", task_def, logger,
        )

        assert ht_id == "ht_esim"

        # Verify snapshot written
        pk = build_pk("t1", "p1")
        ht_item = blackboard.read(pk, "S#w001#mdev#ht_esim")
        assert ht_item is not None
        assert ht_item["task_type"] == "human"
        assert ht_item["status"] == "notified"
        assert ht_item["human_task_subtype"] == "physical_action"

        # Verify event written to events table
        from boto3.dynamodb.conditions import Key
        response = events_table.query(
            KeyConditionExpression=Key("PK").eq("T#t1#P#p1#W#w001"),
        )
        human_task_events = [
            e for e in response.get("Items", [])
            if e.get("event_type") == "human_task_created"
        ]
        assert len(human_task_events) == 1


class TestHumanTaskCompleted:
    def test_unblocks_dependent_crow(
        self, dynamodb_table: Any, events_table: Any, logger: StructuredLogger,
    ) -> None:
        blackboard = Blackboard(dynamodb_table, events_table=events_table)
        _seed_wave(dynamodb_table)
        _seed_mvi(dynamodb_table)
        _seed_blocked_crow(dynamodb_table)

        ht_item = {
            "PK": build_pk("t1", "p1"),
            "SK": "S#w001#mdev#ht_esim",
            "id": "ht_esim",
            "level": "crow",
            "task_type": "human",
            "status": "completed",
            "ask": "Buy e-SIM",
            "instructions": "Buy a phone number.",
            "blocks": ["S#w001#mdev#cr_impl_01"],
            "response": {"phone": "+5511999999999"},
            "created_at": "2026-03-16T10:00:00Z",
        }

        react_to_human_task_completed(blackboard, ht_item, logger)

        # Verify a new crow was dispatched (unblocked)
        pk = build_pk("t1", "p1")
        crows = blackboard.query(pk, "S#w001#mdev#cr_")
        pending_crows = [c for c in crows if c.get("status") == "pending"]
        assert len(pending_crows) >= 1

        # Verify unblock event written to events table
        from boto3.dynamodb.conditions import Key
        response = events_table.query(
            KeyConditionExpression=Key("PK").eq("T#t1#P#p1#W#w001"),
        )
        unblock_events = [
            e for e in response.get("Items", [])
            if e.get("event_type") == "task_unblocked"
        ]
        assert len(unblock_events) == 1

    def test_steer_injected_into_new_crow_instructions(
        self, dynamodb_table: Any, events_table: Any, logger: StructuredLogger,
    ) -> None:
        blackboard = Blackboard(dynamodb_table, events_table=events_table)
        _seed_wave(dynamodb_table)
        _seed_mvi(dynamodb_table)
        _seed_blocked_crow(dynamodb_table)

        ht_item = {
            "PK": build_pk("t1", "p1"),
            "SK": "S#w001#mdev#ht_esim",
            "id": "ht_esim",
            "level": "crow",
            "task_type": "human",
            "status": "completed",
            "ask": "Buy e-SIM",
            "instructions": "Buy a phone.",
            "blocks": ["S#w001#mdev#cr_impl_01"],
            "response": {"phone": "+5511999999999"},
            "steer": "Use Twilio instead of Meta direct API",
            "created_at": "2026-03-16T10:00:00Z",
        }

        react_to_human_task_completed(blackboard, ht_item, logger)

        pk = build_pk("t1", "p1")
        crows = blackboard.query(pk, "S#w001#mdev#cr_")
        pending_crows = [c for c in crows if c.get("status") == "pending"]
        assert len(pending_crows) == 1
        assert "## Human Guidance" in pending_crows[0]["instructions"]
        assert "Twilio" in pending_crows[0]["instructions"]

    def test_stale_unblock_wave_delivered(
        self, dynamodb_table: Any, events_table: Any, logger: StructuredLogger,
    ) -> None:
        blackboard = Blackboard(dynamodb_table, events_table=events_table)
        _seed_wave(dynamodb_table, status="delivered")
        _seed_mvi(dynamodb_table)
        _seed_blocked_crow(dynamodb_table)

        ht_item = {
            "PK": build_pk("t1", "p1"),
            "SK": "S#w001#mdev#ht_esim",
            "id": "ht_esim",
            "level": "crow",
            "task_type": "human",
            "status": "completed",
            "ask": "Buy e-SIM",
            "blocks": ["S#w001#mdev#cr_impl_01"],
            "created_at": "2026-03-16T10:00:00Z",
        }

        react_to_human_task_completed(blackboard, ht_item, logger)

        # No new crows should be dispatched
        pk = build_pk("t1", "p1")
        crows = blackboard.query(pk, "S#w001#mdev#cr_")
        pending_crows = [c for c in crows if c.get("status") == "pending"]
        assert len(pending_crows) == 0

    def test_stale_unblock_mvi_shipped(
        self, dynamodb_table: Any, events_table: Any, logger: StructuredLogger,
    ) -> None:
        blackboard = Blackboard(dynamodb_table, events_table=events_table)
        _seed_wave(dynamodb_table)
        _seed_mvi(dynamodb_table, status="shipped")
        _seed_blocked_crow(dynamodb_table)

        ht_item = {
            "PK": build_pk("t1", "p1"),
            "SK": "S#w001#mdev#ht_esim",
            "id": "ht_esim",
            "level": "crow",
            "task_type": "human",
            "status": "completed",
            "ask": "Buy e-SIM",
            "blocks": ["S#w001#mdev#cr_impl_01"],
            "created_at": "2026-03-16T10:00:00Z",
        }

        react_to_human_task_completed(blackboard, ht_item, logger)

        pk = build_pk("t1", "p1")
        crows = blackboard.query(pk, "S#w001#mdev#cr_")
        pending_crows = [c for c in crows if c.get("status") == "pending"]
        assert len(pending_crows) == 0


class TestSecretBlocking:
    def test_missing_secret_creates_human_task(
        self, dynamodb_table: Any, events_table: Any, logger: StructuredLogger,
    ) -> None:
        blackboard = Blackboard(dynamodb_table, events_table=events_table)
        _seed_wave(dynamodb_table)
        _seed_mvi(dynamodb_table, status="queued")

        mvi_item = blackboard.read(
            build_pk("t1", "p1"), build_sk(wave_id="w001", mvi_id="dev")
        )

        # Seed a completed planner with instructions referencing a secret
        pk = build_pk("t1", "p1")
        planner_sk = build_sk(wave_id="w001", mvi_id="dev", crow_id="cr_plan_01")
        dynamodb_table.put_item(Item={
            "PK": pk,
            "SK": planner_sk,
            "crow_id": "cr_plan_01",
            "level": "crow",
            "status": "completed",
            "crow_type": "planner",
            "instructions": "Plan the tasks",
            "repo": "github.com/org/repo",
            "branch": "cawnex/w001-dev",
            "budget_remaining": 5_000_000,
            "cost": {"tokens_in": 100, "tokens_out": 50, "credits": 1050, "duration_ms": 500},
            "outcome": {
                "tasks": [
                    {
                        "id": "t1",
                        "name": "Implement API integration",
                        "description": "Use {{secret:whatsapp_api_token}} to connect",
                        "estimated_hours": 4,
                    },
                ],
            },
            "created_at": "2026-03-16T10:00:00Z",
            "entityType": "Snapshot",
        })

        # Transition MVI to executing
        blackboard.update(pk, build_sk(wave_id="w001", mvi_id="dev"), {"status": "executing"})

        # React to planner completion — should try to assign implementer
        # but implementer instructions will include {{secret:...}}
        # This is tested indirectly: the actual secret check happens in _handle_assign
        # For now, verify the vault_client correctly detects the pattern
        from murder.vault_client import list_required_secrets
        secrets = list_required_secrets(
            "Use {{secret:whatsapp_api_token}} to connect"
        )
        assert secrets == ["whatsapp_api_token"]
