"""Tests for secret and context resolution in executor."""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock, patch

from worker.executor import _resolve_templates
from worker.logging import StructuredLogger


def _make_logger() -> StructuredLogger:
    return StructuredLogger("test-secrets")


class TestResolveSecrets:
    @patch("worker.executor.boto3")
    @patch.dict("os.environ", {"TABLE_NAME": "test-table", "VAULT_KMS_KEY_ID": ""})
    def test_resolves_single_secret(self, mock_boto3: Mock) -> None:
        """{{secret:name}} is replaced with env var reference."""
        mock_table = Mock()
        mock_boto3.resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {
            "Item": {
                "PK": "T#t1#VAULT",
                "SK": "P#p1#S#api_token",
                "encrypted_value": "sk-secret-123",
            }
        }

        instructions = "Use {{secret:api_token}} to call the API"
        snapshot = {"PK": "T#t1#P#p1"}
        logger = _make_logger()

        resolved, env_vars = _resolve_templates(instructions, snapshot, logger)

        assert "${SECRET_API_TOKEN}" in resolved
        assert "{{secret:api_token}}" not in resolved
        assert env_vars["SECRET_API_TOKEN"] == "sk-secret-123"

    @patch("worker.executor.boto3")
    @patch.dict("os.environ", {"TABLE_NAME": "test-table", "VAULT_KMS_KEY_ID": ""})
    def test_resolves_multiple_secrets(self, mock_boto3: Mock) -> None:
        """Multiple secrets are all resolved."""
        mock_table = Mock()
        mock_boto3.resource.return_value.Table.return_value = mock_table

        def get_item_side_effect(**kwargs: Any) -> dict[str, Any]:
            key = kwargs["Key"]
            if "token_a" in key["SK"]:
                return {"Item": {"encrypted_value": "value-a"}}
            if "token_b" in key["SK"]:
                return {"Item": {"encrypted_value": "value-b"}}
            return {}

        mock_table.get_item.side_effect = get_item_side_effect

        instructions = "Use {{secret:token_a}} and {{secret:token_b}}"
        snapshot = {"PK": "T#t1#P#p1"}
        logger = _make_logger()

        resolved, env_vars = _resolve_templates(instructions, snapshot, logger)

        assert "SECRET_TOKEN_A" in env_vars
        assert "SECRET_TOKEN_B" in env_vars
        assert env_vars["SECRET_TOKEN_A"] == "value-a"
        assert env_vars["SECRET_TOKEN_B"] == "value-b"

    @patch("worker.executor.boto3")
    @patch.dict("os.environ", {"TABLE_NAME": "test-table", "VAULT_KMS_KEY_ID": ""})
    def test_missing_secret_warns(self, mock_boto3: Mock) -> None:
        """Missing secret logs warning and keeps template."""
        mock_table = Mock()
        mock_boto3.resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {}

        instructions = "Use {{secret:missing_key}}"
        snapshot = {"PK": "T#t1#P#p1"}
        logger = _make_logger()

        resolved, env_vars = _resolve_templates(instructions, snapshot, logger)

        assert len(env_vars) == 0


class TestResolveContext:
    @patch("worker.executor.boto3")
    @patch.dict("os.environ", {"TABLE_NAME": "test-table"})
    def test_resolves_context(self, mock_boto3: Mock) -> None:
        """{{context:key}} is replaced with content inline."""
        mock_table = Mock()
        mock_boto3.resource.return_value.Table.return_value = mock_table

        def get_item_side_effect(**kwargs: Any) -> dict[str, Any]:
            key = kwargs["Key"]
            if key["SK"] == "CTX#formula":
                return {"Item": {"content": "The secret formula is H2O"}}
            return {}

        mock_table.get_item.side_effect = get_item_side_effect

        instructions = "Follow the formula: {{context:formula}}"
        snapshot = {"PK": "T#t1#P#p1"}
        logger = _make_logger()

        resolved, env_vars = _resolve_templates(instructions, snapshot, logger)

        assert "The secret formula is H2O" in resolved
        assert "{{context:formula}}" not in resolved
        assert len(env_vars) == 0

    @patch("worker.executor.boto3")
    @patch.dict("os.environ", {"TABLE_NAME": "test-table"})
    def test_missing_context_warns(self, mock_boto3: Mock) -> None:
        """Missing context key logs warning."""
        mock_table = Mock()
        mock_boto3.resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {}

        instructions = "Use {{context:unknown}}"
        snapshot = {"PK": "T#t1#P#p1"}
        logger = _make_logger()

        resolved, env_vars = _resolve_templates(instructions, snapshot, logger)

        assert "{{context:unknown}}" in resolved


class TestNoTemplates:
    def test_no_templates_returns_unchanged(self) -> None:
        """Instructions without templates are returned unchanged."""
        instructions = "Just implement the feature normally."
        snapshot = {"PK": "T#t1#P#p1"}
        logger = _make_logger()

        resolved, env_vars = _resolve_templates(instructions, snapshot, logger)

        assert resolved == instructions
        assert env_vars == {}
