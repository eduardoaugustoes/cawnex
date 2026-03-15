"""Tests for Worker structured logger."""

import json
import logging

from worker.logging import StructuredLogger


class TestStructuredLogger:
    def test_event_emits_json(self, caplog: logging.LogCaptureFixture) -> None:
        logger = StructuredLogger(component="worker", tenant="acme", project="cawnex")
        with caplog.at_level(logging.INFO, logger="cawnex.worker"):
            logger.event("crow_started", crow_id="cr01")
        assert len(caplog.records) == 1
        payload = json.loads(caplog.records[0].message)
        assert payload["component"] == "worker"
        assert payload["event"] == "crow_started"
        assert payload["tenant"] == "acme"
        assert payload["crow_id"] == "cr01"

    def test_error_emits_json(self, caplog: logging.LogCaptureFixture) -> None:
        logger = StructuredLogger(component="worker")
        with caplog.at_level(logging.ERROR, logger="cawnex.worker"):
            logger.error("crow_failed", reason="timeout")
        assert len(caplog.records) == 1
        payload = json.loads(caplog.records[0].message)
        assert payload["event"] == "crow_failed"
        assert payload["reason"] == "timeout"

    def test_warning_emits_json(self, caplog: logging.LogCaptureFixture) -> None:
        logger = StructuredLogger(component="worker")
        with caplog.at_level(logging.WARNING, logger="cawnex.worker"):
            logger.warning("retry_scheduled", attempt=2)
        assert len(caplog.records) == 1
        payload = json.loads(caplog.records[0].message)
        assert payload["event"] == "retry_scheduled"
        assert payload["attempt"] == 2

    def test_context_excluded_when_empty(self, caplog: logging.LogCaptureFixture) -> None:
        logger = StructuredLogger(component="worker")
        with caplog.at_level(logging.INFO, logger="cawnex.worker"):
            logger.event("test_event")
        payload = json.loads(caplog.records[0].message)
        assert "tenant" not in payload
        assert "project" not in payload

    def test_execution_id_in_context(self, caplog: logging.LogCaptureFixture) -> None:
        logger = StructuredLogger(
            component="worker",
            tenant="acme",
            project="cawnex",
            execution_id="exec-abc",
        )
        with caplog.at_level(logging.INFO, logger="cawnex.worker"):
            logger.event("started")
        payload = json.loads(caplog.records[0].message)
        assert payload["execution_id"] == "exec-abc"
