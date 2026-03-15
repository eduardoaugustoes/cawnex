"""Tests for events — EVT record builders owned by Murder.

All money values are integer microdollars (1 USD = 1_000_000).
"""

from murder.config import MICROS_PER_DOLLAR
from murder.enums import CrowType, EventColor, EventType
from murder.events import (
    build_budget_exceeded_event,
    build_budget_warning_event,
    build_crow_assigned_event,
    build_mvi_ready_event,
    build_wave_delivered_event,
    build_wave_started_event,
)


class TestCrowAssignedEvent:
    def test_builds_valid_event(self) -> None:
        event = build_crow_assigned_event(
            tenant="acme",
            project="cawnex",
            wave_id="w001",
            crow_type=CrowType.PLANNER,
            task_name="Plan auth implementation",
        )
        assert event.event_type == EventType.CROW_ASSIGNED.value
        assert event.color == EventColor.PURPLE.value
        assert "planner" in event.message.lower()
        assert event.pk == "T#acme#P#cawnex"
        assert event.sk.startswith("EVT#w001#")


class TestMVIReadyEvent:
    def test_builds_valid_event(self) -> None:
        event = build_mvi_ready_event(
            tenant="acme",
            project="cawnex",
            wave_id="w001",
            mvi_name="Auth & JWT",
        )
        assert event.event_type == EventType.MVI_READY.value
        assert event.color == EventColor.GREEN.value
        assert "auth" in event.message.lower()


class TestWaveEvents:
    def test_wave_started(self) -> None:
        event = build_wave_started_event(
            tenant="acme",
            project="cawnex",
            wave_id="w001",
            directive="Ship onboarding",
        )
        assert event.event_type == EventType.WAVE_STARTED.value
        assert event.color == EventColor.BLUE.value

    def test_wave_delivered(self) -> None:
        event = build_wave_delivered_event(
            tenant="acme",
            project="cawnex",
            wave_id="w001",
            credits_spent=18_500_000,  # $18.50
        )
        assert event.event_type == EventType.WAVE_DELIVERED.value
        assert event.color == EventColor.GREEN.value
        assert "$18.50" in event.message


class TestBudgetEvents:
    def test_budget_warning(self) -> None:
        event = build_budget_warning_event(
            tenant="acme",
            project="cawnex",
            wave_id="w001",
            spent=16 * MICROS_PER_DOLLAR,
            limit=20 * MICROS_PER_DOLLAR,
        )
        assert event.event_type == EventType.BUDGET_WARNING.value
        assert event.color == EventColor.YELLOW.value
        assert "$16.00" in event.message

    def test_budget_exceeded(self) -> None:
        event = build_budget_exceeded_event(
            tenant="acme",
            project="cawnex",
            wave_id="w001",
            spent=21 * MICROS_PER_DOLLAR,
            limit=20 * MICROS_PER_DOLLAR,
        )
        assert event.event_type == EventType.BUDGET_EXCEEDED.value
        assert event.color == EventColor.RED.value
        assert "$21.00" in event.message
