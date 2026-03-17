"""Tests for vault_client — secret pattern detection and vault queries."""

from __future__ import annotations

from unittest.mock import Mock

from murder.vault_client import has_secret, list_required_secrets


class TestListRequiredSecrets:
    def test_finds_single_secret(self) -> None:
        instructions = "Use {{secret:whatsapp_api_token}} to call the API"
        assert list_required_secrets(instructions) == ["whatsapp_api_token"]

    def test_finds_multiple_secrets(self) -> None:
        instructions = (
            "Use {{secret:api_token}} and {{secret:webhook_verify}} "
            "to configure the webhook."
        )
        result = list_required_secrets(instructions)
        assert result == ["api_token", "webhook_verify"]

    def test_no_secrets(self) -> None:
        instructions = "Just implement the feature without any credentials."
        assert list_required_secrets(instructions) == []

    def test_ignores_context_templates(self) -> None:
        instructions = "Read {{context:formula}} but use {{secret:key}}"
        assert list_required_secrets(instructions) == ["key"]

    def test_handles_hyphens_and_underscores(self) -> None:
        instructions = "Use {{secret:my-api-key}} and {{secret:other_key}}"
        assert list_required_secrets(instructions) == ["my-api-key", "other_key"]

    def test_empty_string(self) -> None:
        assert list_required_secrets("") == []


class TestHasSecret:
    def test_secret_exists(self) -> None:
        blackboard = Mock()
        blackboard.read.return_value = {
            "PK": "T#t1#VAULT",
            "SK": "P#p1#S#api_token",
            "name": "api_token",
        }
        assert has_secret(blackboard, "t1", "p1", "api_token") is True
        blackboard.read.assert_called_once_with("T#t1#VAULT", "P#p1#S#api_token")

    def test_secret_missing(self) -> None:
        blackboard = Mock()
        blackboard.read.return_value = None
        assert has_secret(blackboard, "t1", "p1", "missing_key") is False

    def test_correct_vault_pk_pattern(self) -> None:
        blackboard = Mock()
        blackboard.read.return_value = None
        has_secret(blackboard, "tenant-abc", "proj-001", "token")
        blackboard.read.assert_called_once_with(
            "T#tenant-abc#VAULT", "P#proj-001#S#token"
        )
