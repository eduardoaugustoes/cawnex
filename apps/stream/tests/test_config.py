"""Tests for stream service config loading."""

from __future__ import annotations

import pytest

from stream.config import Config, load_config


def test_load_config_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TABLE_NAME", "main")
    monkeypatch.setenv("EVENTS_TABLE_NAME", "events")
    monkeypatch.setenv("USER_POOL_ID", "us-east-1_X")
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setenv("PIPE_SECRET", "s3cr3t")

    cfg = load_config()

    assert cfg.table_name == "main"
    assert cfg.events_table_name == "events"
    assert cfg.user_pool_id == "us-east-1_X"
    assert cfg.region == "us-west-2"
    assert cfg.pipe_secret == "s3cr3t"


def test_load_config_raises_when_required_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EVENTS_TABLE_NAME", raising=False)
    with pytest.raises(RuntimeError, match="EVENTS_TABLE_NAME"):
        load_config()


def test_config_is_immutable() -> None:
    cfg = Config(
        table_name="a",
        events_table_name="b",
        user_pool_id="c",
        region="d",
        pipe_secret="e",
    )
    with pytest.raises(AttributeError):
        cfg.table_name = "mutated"  # type: ignore[misc]
