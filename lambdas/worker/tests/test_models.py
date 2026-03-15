"""Tests for Worker models — CrowSnapshot, EventRecord, Cost.

All money values are integer microdollars (1 USD = 1_000_000).
"""

import pytest

from worker.config import ExecutionConfig, MICROS_PER_DOLLAR
from worker.enums import CrowStatus, CrowType
from worker.keys import build_pk, build_sk, parse_item_keys, parse_pk, parse_sk
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


class TestKeyParsers:
    def test_parse_pk(self) -> None:
        result = parse_pk("T#acme#P#cawnex")
        assert result == {"tenant": "acme", "project": "cawnex"}

    def test_parse_pk_invalid(self) -> None:
        assert parse_pk("invalid") is None
        assert parse_pk("") is None

    def test_parse_sk_crow(self) -> None:
        result = parse_sk("S#w001#mauth#cr_impl")
        assert result == {"wave_id": "w001", "mvi_id": "auth", "crow_id": "cr_impl"}

    def test_parse_sk_mvi(self) -> None:
        result = parse_sk("S#w001#mauth")
        assert result == {"wave_id": "w001", "mvi_id": "auth"}

    def test_parse_sk_wave(self) -> None:
        result = parse_sk("S#w001")
        assert result == {"wave_id": "w001"}

    def test_parse_sk_event(self) -> None:
        result = parse_sk("EVT#w001#2026-03-14T10:00:00Z")
        assert result == {"wave_id": "w001", "event_ts": "2026-03-14T10:00:00Z"}

    def test_parse_sk_invalid(self) -> None:
        assert parse_sk("invalid") is None
        assert parse_sk("") is None

    def test_parse_item_keys_crow(self) -> None:
        item = {"PK": "T#acme#P#cawnex", "SK": "S#w001#mauth#cr_impl"}
        result = parse_item_keys(item)
        assert result == {
            "tenant": "acme",
            "project": "cawnex",
            "wave_id": "w001",
            "mvi_id": "auth",
            "crow_id": "cr_impl",
        }

    def test_parse_item_keys_returns_none_for_bad_pk(self) -> None:
        assert parse_item_keys({"PK": "bad", "SK": "S#w001#mauth#cr"}) is None

    def test_parse_item_keys_returns_none_for_bad_sk(self) -> None:
        assert parse_item_keys({"PK": "T#a#P#b", "SK": "bad"}) is None

    def test_roundtrip_pk(self) -> None:
        pk = build_pk("acme", "proj-1")
        parsed = parse_pk(pk)
        assert parsed is not None
        assert parsed["tenant"] == "acme"
        assert parsed["project"] == "proj-1"

    def test_roundtrip_sk_crow(self) -> None:
        sk = build_sk(wave_id="w001", mvi_id="auth", crow_id="cr_impl_01")
        parsed = parse_sk(sk)
        assert parsed is not None
        assert parsed["wave_id"] == "w001"
        assert parsed["mvi_id"] == "auth"
        assert parsed["crow_id"] == "cr_impl_01"


class TestExecutionConfig:
    def test_creation(self) -> None:
        config = ExecutionConfig(efs_mount="/mnt/repos", github_token="tok")
        assert config.efs_mount == "/mnt/repos"
        assert config.github_token == "tok"

    def test_frozen(self) -> None:
        config = ExecutionConfig(efs_mount="/mnt", github_token="tok")
        with pytest.raises(AttributeError):
            config.efs_mount = "/other"  # type: ignore[misc]

    def test_from_env(self) -> None:
        config = ExecutionConfig.from_env()
        assert isinstance(config.efs_mount, str)
        assert isinstance(config.github_token, str)


class TestCost:
    def test_creation(self) -> None:
        cost = Cost(tokens_in=5000, tokens_out=2000, credits=120_000, duration_ms=30000)
        assert cost.tokens_in == 5000

    def test_zero_cost(self) -> None:
        cost = Cost.zero()
        assert cost.tokens_in == 0
        assert cost.credits == 0

    def test_add(self) -> None:
        a = Cost(tokens_in=1000, tokens_out=500, credits=50_000, duration_ms=10000)
        b = Cost(tokens_in=2000, tokens_out=1000, credits=100_000, duration_ms=20000)
        result = a + b
        assert result.tokens_in == 3000
        assert result.credits == 150_000

    def test_to_dict(self) -> None:
        cost = Cost(tokens_in=5000, tokens_out=2000, credits=120_000, duration_ms=30000)
        d = cost.to_dict()
        assert d == {
            "tokens_in": 5000,
            "tokens_out": 2000,
            "credits": 120_000,
            "duration_ms": 30000,
        }

    def test_from_dict(self) -> None:
        d = {
            "tokens_in": 5000,
            "tokens_out": 2000,
            "credits": 120_000,
            "duration_ms": 30000,
        }
        cost = Cost.from_dict(d)
        assert cost.tokens_in == 5000

    def test_to_dollars(self) -> None:
        cost = Cost(tokens_in=0, tokens_out=0, credits=3_500_000, duration_ms=0)
        assert cost.to_dollars() == 3.5


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
            budget_remaining=5_000_000,
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
            budget_remaining=5_000_000,
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
            budget_remaining=5_000_000,
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
            budget_remaining=5_000_000,
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
            budget_remaining=5_000_000,
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
