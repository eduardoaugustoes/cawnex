"""Tests for models — dataclasses, serialization, key generation."""

from datetime import datetime, timezone

import pytest

from murder.enums import (
    CrowStatus,
    CrowType,
    MVIStatus,
    SnapshotLevel,
    WaveStatus,
)
from murder.keys import build_pk, build_sk
from murder.models import (
    Cost,
    CrowSnapshot,
    EventRecord,
    MVISnapshot,
    Progress,
    WaveBudget,
    WaveSnapshot,
)


class TestKeyBuilders:
    def test_build_pk(self) -> None:
        assert build_pk("acme", "cawnex") == "T#acme#P#cawnex"

    def test_build_sk_wave(self) -> None:
        assert build_sk(wave_id="w001") == "S#w001"

    def test_build_sk_mvi(self) -> None:
        assert build_sk(wave_id="w001", mvi_id="auth") == "S#w001#mauth"

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
        assert cost.tokens_out == 2000
        assert cost.credits == 0.12
        assert cost.duration_ms == 30000

    def test_zero_cost(self) -> None:
        cost = Cost.zero()
        assert cost.tokens_in == 0
        assert cost.tokens_out == 0
        assert cost.credits == 0.0
        assert cost.duration_ms == 0

    def test_add(self) -> None:
        a = Cost(tokens_in=1000, tokens_out=500, credits=0.05, duration_ms=10000)
        b = Cost(tokens_in=2000, tokens_out=1000, credits=0.10, duration_ms=20000)
        result = a + b
        assert result.tokens_in == 3000
        assert result.tokens_out == 1500
        assert result.credits == pytest.approx(0.15)
        assert result.duration_ms == 30000

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
        assert cost.credits == 0.12


class TestProgress:
    def test_creation(self) -> None:
        progress = Progress(mvis_total=3, mvis_shipped=1, tasks_done=8, tasks_total=15)
        assert progress.mvis_total == 3
        assert progress.mvis_shipped == 1

    def test_to_dict(self) -> None:
        progress = Progress(mvis_total=3, mvis_shipped=1, tasks_done=8, tasks_total=15)
        d = progress.to_dict()
        assert d["mvis_total"] == 3


class TestWaveBudget:
    def test_creation(self) -> None:
        budget = WaveBudget(spent=18.50, limit=50.00)
        assert budget.spent == 18.50
        assert budget.limit == 50.00

    def test_remaining(self) -> None:
        budget = WaveBudget(spent=18.50, limit=50.00)
        assert budget.remaining == pytest.approx(31.50)

    def test_is_exceeded(self) -> None:
        assert WaveBudget(spent=51.0, limit=50.0).is_exceeded
        assert not WaveBudget(spent=49.0, limit=50.0).is_exceeded

    def test_is_warning(self) -> None:
        assert WaveBudget(spent=41.0, limit=50.0).is_warning
        assert not WaveBudget(spent=39.0, limit=50.0).is_warning


class TestWaveSnapshot:
    def test_creation(self) -> None:
        wave = WaveSnapshot(
            tenant="acme",
            project="cawnex",
            wave_id="w001",
            status=WaveStatus.PLANNING,
            human_directive="Ship onboarding in 2 weeks",
        )
        assert wave.pk == "T#acme#P#cawnex"
        assert wave.sk == "S#w001"
        assert wave.level == SnapshotLevel.WAVE
        assert wave.status == WaveStatus.PLANNING

    def test_to_item(self) -> None:
        wave = WaveSnapshot(
            tenant="acme",
            project="cawnex",
            wave_id="w001",
            status=WaveStatus.PLANNING,
            human_directive="Ship onboarding",
        )
        item = wave.to_item()
        assert item["PK"] == "T#acme#P#cawnex"
        assert item["SK"] == "S#w001"
        assert item["level"] == "wave"
        assert item["status"] == "planning"
        assert item["human_directive"] == "Ship onboarding"
        assert item["entityType"] == "Snapshot"

    def test_from_item(self) -> None:
        item = {
            "PK": "T#acme#P#cawnex",
            "SK": "S#w001",
            "level": "wave",
            "status": "planning",
            "human_directive": "Ship onboarding",
            "entityType": "Snapshot",
            "progress": {
                "mvis_total": 3,
                "mvis_shipped": 0,
                "tasks_done": 0,
                "tasks_total": 0,
            },
            "budget": {"spent": 0, "limit": 20.0},
            "created_at": "2026-03-14T10:00:00+00:00",
        }
        wave = WaveSnapshot.from_item(item)
        assert wave.tenant == "acme"
        assert wave.project == "cawnex"
        assert wave.wave_id == "w001"
        assert wave.status == WaveStatus.PLANNING


class TestMVISnapshot:
    def test_creation(self) -> None:
        mvi = MVISnapshot(
            tenant="acme",
            project="cawnex",
            wave_id="w001",
            mvi_id="auth",
            name="Auth & JWT",
            status=MVIStatus.QUEUED,
            repo="owner/repo",
            branch="cawnex/w001-auth",
        )
        assert mvi.pk == "T#acme#P#cawnex"
        assert mvi.sk == "S#w001#mauth"
        assert mvi.level == SnapshotLevel.MURDER

    def test_to_item(self) -> None:
        mvi = MVISnapshot(
            tenant="acme",
            project="cawnex",
            wave_id="w001",
            mvi_id="auth",
            name="Auth & JWT",
            status=MVIStatus.QUEUED,
            repo="owner/repo",
            branch="cawnex/w001-auth",
        )
        item = mvi.to_item()
        assert item["PK"] == "T#acme#P#cawnex"
        assert item["level"] == "murder"
        assert item["status"] == "queued"
        assert item["name"] == "Auth & JWT"


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
        assert crow.level == SnapshotLevel.CROW
        assert crow.crow_type == CrowType.IMPLEMENTER

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
        assert item["instructions"] == "Implement OAuth middleware"
        assert item["budget_remaining"] == 5.0

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


class TestEventRecord:
    def test_creation(self) -> None:
        event = EventRecord(
            tenant="acme",
            project="cawnex",
            wave_id="w001",
            event_type="crow_assigned",
            message="Murder assigned planner for MVI 1.1",
            color="purple",
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
        assert item["message"] == "Implementer completed OAuth middleware"
        assert item["color"] == "green"
