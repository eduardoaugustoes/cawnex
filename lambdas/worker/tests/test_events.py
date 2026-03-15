"""Tests for Worker event builders."""

from worker.enums import CrowType
from worker.events import (
    EventColor,
    EventType,
    build_crow_completed_event,
    build_crow_failed_event,
)
from worker.models import Cost


class TestBuildCrowCompletedEvent:
    def test_returns_event_record(self) -> None:
        cost = Cost(tokens_in=5000, tokens_out=2000, credits=0.12, duration_ms=30000)
        event = build_crow_completed_event(
            tenant="acme",
            project="cawnex",
            wave_id="w001",
            crow_type=CrowType.IMPLEMENTER,
            task_name="OAuth middleware",
            cost=cost,
        )
        assert event.event_type == EventType.CROW_COMPLETED
        assert event.color == EventColor.GREEN
        assert event.pk == "T#acme#P#cawnex"
        assert event.sk.startswith("EVT#w001#")

    def test_message_contains_task_name(self) -> None:
        cost = Cost.zero()
        event = build_crow_completed_event(
            tenant="acme",
            project="cawnex",
            wave_id="w001",
            crow_type=CrowType.PLANNER,
            task_name="Design auth flow",
            cost=cost,
        )
        assert "Design auth flow" in event.message
        assert "Planner" in event.message

    def test_extra_contains_cost(self) -> None:
        cost = Cost(tokens_in=1000, tokens_out=500, credits=0.05, duration_ms=10000)
        event = build_crow_completed_event(
            tenant="acme",
            project="cawnex",
            wave_id="w001",
            crow_type=CrowType.REVIEWER,
            task_name="Review PR",
            cost=cost,
        )
        assert "cost" in event.extra
        assert event.extra["crow_type"] == "reviewer"
        assert event.extra["task_name"] == "Review PR"

    def test_to_item_structure(self) -> None:
        cost = Cost.zero()
        event = build_crow_completed_event(
            tenant="acme",
            project="cawnex",
            wave_id="w001",
            crow_type=CrowType.FIXER,
            task_name="Fix lint errors",
            cost=cost,
        )
        item = event.to_item()
        assert item["type"] == EventType.CROW_COMPLETED
        assert item["color"] == EventColor.GREEN
        assert item["entityType"] == "Event"


class TestBuildCrowFailedEvent:
    def test_returns_event_record(self) -> None:
        event = build_crow_failed_event(
            tenant="acme",
            project="cawnex",
            wave_id="w001",
            crow_type=CrowType.IMPLEMENTER,
            task_name="OAuth middleware",
            error="timeout after 600s",
        )
        assert event.event_type == EventType.CROW_FAILED
        assert event.color == EventColor.RED
        assert event.pk == "T#acme#P#cawnex"

    def test_message_contains_error(self) -> None:
        event = build_crow_failed_event(
            tenant="acme",
            project="cawnex",
            wave_id="w001",
            crow_type=CrowType.PLANNER,
            task_name="Design flow",
            error="budget exceeded",
        )
        assert "budget exceeded" in event.message
        assert "Design flow" in event.message

    def test_extra_contains_error(self) -> None:
        event = build_crow_failed_event(
            tenant="acme",
            project="cawnex",
            wave_id="w001",
            crow_type=CrowType.FIXER,
            task_name="Fix tests",
            error="compilation failed",
        )
        assert event.extra["error"] == "compilation failed"
        assert event.extra["crow_type"] == "fixer"

    def test_to_item_structure(self) -> None:
        event = build_crow_failed_event(
            tenant="acme",
            project="cawnex",
            wave_id="w001",
            crow_type=CrowType.REVIEWER,
            task_name="Review PR",
            error="network error",
        )
        item = event.to_item()
        assert item["type"] == EventType.CROW_FAILED
        assert item["color"] == EventColor.RED
        assert item["entityType"] == "Event"
