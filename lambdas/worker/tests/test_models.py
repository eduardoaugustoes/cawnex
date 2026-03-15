"""Tests for Worker models — CrowSnapshot, EventRecord, Cost."""

import pytest

from worker.enums import CrowStatus, CrowType
from worker.keys import build_pk, build_sk
from worker.models import Cost, CrowSnapshot, EventRecord


class TestKeyBuilders:
    def test_build_pk(self) -> None:
        assert build_pk("acme", "cawnex") == "T#acme#P#cawnex"

    def test_build_sk_crow(self) -> None:
        result = build_sk(wave_id="w001", mvi_id="auth", crow_id="cr_impl")
        assert result == "S#w001#mauth#cr_impl"

    def test_build_sk_event(self) -> None:
        result = build_sk(wave_id="w001", event_ts="2026-03-14T10:00:00Z")
        assert result == "EVT#w001#2026-03-14T10:00:00Z"

    def test_build_sk_no_args_raises(self) -> None:
        with pytest.raises(ValueError):
            build_sk()


class TestCost:
    def test_creation(self) -> None:
        cost = Cost(tokens_in=5000, tokens_out=2000, credits=0.12, duration_ms=30000)
        assert cost.tokens_in == 5000

    def test_zero_cost(self) -> None:
        cost = Cost.zero()
        assert cost.tokens_in == 0
        assert cost.credits == 0.0

    def test_add(self) -> None:
        a = Cost(tokens_in=1000, tokens_out=500, credits=0.05, duration_ms=10000)
        b = Cost(tokens_in=2000, tokens_out=1000, credits=0.10, duration_ms=20000)
        result = a + b
        assert result.tokens_in == 3000
        assert result.credits == pytest.approx(0.15)

    def test_to_dict(self) -> None:
        cost = Cost(tokens_in=5000, tokens_out=2000, credits=0.12, duration_ms=30000)
        d = cost.to_dict()
        assert d == {
            "tokens_in": 5000,
            "tokens_out": 2000,
            "credits": 0.12,
            "duration_ms": 30000,
        }

    def test_from_dict(self) -> None:
        d = {
            "tokens_in": 5000,
            "tokens_out": 2000,
            "credits": 0.12,
            "duration_ms": 30000,
        }
        cost = Cost.from_dict(d)
        assert cost.tokens_in == 5000


class TestCrowSnapshot:
    def test_creation(self) -> None:
        crow = CrowSnapshot(
            tenant="acme",
            project="cawnex",
            wave_id="w001",
            mvi_id="auth",
            crow_id="cr_impl",
            crow_type=CrowType.IMPLEMENTER,
            status=CrowStatus.PENDING,
            instructions="Implement OAuth middleware",
            repo="owner/repo",
            branch="cawnex/w001-auth",
            budget_remaining=5.0,
        )
        assert crow.pk == "T#acme#P#cawnex"
        assert crow.sk == "S#w001#mauth#cr_impl"

    def test_to_item(self) -> None:
        crow = CrowSnapshot(
            tenant="acme",
            project="cawnex",
            wave_id="w001",
            mvi_id="auth",
            crow_id="cr_impl",
            crow_type=CrowType.IMPLEMENTER,
            status=CrowStatus.PENDING,
            instructions="Implement OAuth middleware",
            repo="owner/repo",
            branch="cawnex/w001-auth",
            budget_remaining=5.0,
        )
        item = crow.to_item()
        assert item["status"] == "pending"
        assert item["crow_type"] == "implementer"
        assert item["level"] == "crow"

    def test_gsi1_keys(self) -> None:
        crow = CrowSnapshot(
            tenant="acme",
            project="cawnex",
            wave_id="w001",
            mvi_id="auth",
            crow_id="cr_impl",
            crow_type=CrowType.IMPLEMENTER,
            status=CrowStatus.PENDING,
            instructions="Implement OAuth middleware",
            repo="owner/repo",
            branch="cawnex/w001-auth",
            budget_remaining=5.0,
        )
        item = crow.to_item()
        assert item["GSI1PK"] == "DISPATCH#pending"
        assert "GSI1SK" in item

    def test_completed_crow_has_no_gsi1(self) -> None:
        crow = CrowSnapshot(
            tenant="acme",
            project="cawnex",
            wave_id="w001",
            mvi_id="auth",
            crow_id="cr_impl",
            crow_type=CrowType.IMPLEMENTER,
            status=CrowStatus.COMPLETED,
            instructions="Implement OAuth middleware",
            repo="owner/repo",
            branch="cawnex/w001-auth",
            budget_remaining=5.0,
        )
        item = crow.to_item()
        assert "GSI1PK" not in item

    def test_optional_fields_written_when_set(self) -> None:
        crow = CrowSnapshot(
            tenant="acme",
            project="cawnex",
            wave_id="w001",
            mvi_id="auth",
            crow_id="cr_impl",
            crow_type=CrowType.IMPLEMENTER,
            status=CrowStatus.COMPLETED,
            instructions="Implement OAuth middleware",
            repo="owner/repo",
            branch="cawnex/w001-auth",
            budget_remaining=5.0,
            outcome={"summary": "Done"},
            git_commit="abc123",
            pr={"url": "https://github.com/owner/repo/pull/1"},
            completed_at="2026-03-15T10:00:00Z",
        )
        item = crow.to_item()
        assert item["outcome"] == {"summary": "Done"}
        assert item["git_commit"] == "abc123"
        assert item["pr"] == {"url": "https://github.com/owner/repo/pull/1"}
        assert item["completed_at"] == "2026-03-15T10:00:00Z"


class TestEventRecord:
    def test_creation(self) -> None:
        event = EventRecord(
            tenant="acme",
            project="cawnex",
            wave_id="w001",
            event_type="crow_completed",
            message="Implementer completed OAuth middleware",
            color="green",
        )
        assert event.pk == "T#acme#P#cawnex"
        assert event.sk.startswith("EVT#w001#")

    def test_to_item(self) -> None:
        event = EventRecord(
            tenant="acme",
            project="cawnex",
            wave_id="w001",
            event_type="crow_completed",
            message="Implementer completed OAuth middleware",
            color="green",
        )
        item = event.to_item()
        assert item["type"] == "crow_completed"
        assert item["entityType"] == "Event"
