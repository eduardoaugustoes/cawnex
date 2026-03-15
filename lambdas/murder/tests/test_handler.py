"""Tests for the Lambda handler — stream filtering and routing."""

from unittest.mock import MagicMock, patch

from murder.handler import _should_skip, lambda_handler


class TestShouldSkip:
    def test_no_old_item_does_not_skip(self) -> None:
        assert _should_skip({"status": "completed"}, {}) is False

    def test_same_status_skips(self) -> None:
        assert _should_skip(
            {"status": "completed"}, {"status": "completed"}
        ) is True

    def test_different_status_does_not_skip(self) -> None:
        assert _should_skip(
            {"status": "completed"}, {"status": "running"}
        ) is False


class TestLambdaHandler:
    def test_skips_remove_events(self) -> None:
        event = {
            "Records": [
                {"eventName": "REMOVE", "dynamodb": {}},
            ]
        }
        with patch("murder.handler.boto3"):
            result = lambda_handler(event, None)
        assert result["skipped"] == 1
        assert result["processed"] == 0

    def test_skips_non_matching_level(self) -> None:
        event = {
            "Records": [
                {
                    "eventName": "INSERT",
                    "dynamodb": {
                        "NewImage": {
                            "level": {"S": "wave"},
                            "status": {"S": "executing"},
                            "PK": {"S": "T#t1#P#p1"},
                            "SK": {"S": "S#w01"},
                        }
                    },
                }
            ]
        }
        with patch("murder.handler.boto3"):
            result = lambda_handler(event, None)
        assert result["skipped"] == 1

    @patch("murder.handler.react_to_crow_completion")
    @patch("murder.handler.boto3")
    def test_routes_crow_completed(
        self, boto3_mock: MagicMock, reactor_mock: MagicMock
    ) -> None:
        event = {
            "Records": [
                {
                    "eventName": "MODIFY",
                    "dynamodb": {
                        "NewImage": {
                            "level": {"S": "crow"},
                            "status": {"S": "completed"},
                            "PK": {"S": "T#t1#P#p1"},
                            "SK": {"S": "S#w01#m01#cr_plan_01"},
                        },
                        "OldImage": {
                            "level": {"S": "crow"},
                            "status": {"S": "running"},
                            "PK": {"S": "T#t1#P#p1"},
                            "SK": {"S": "S#w01#m01#cr_plan_01"},
                        },
                    },
                }
            ]
        }
        result = lambda_handler(event, None)
        assert result["processed"] == 1
        reactor_mock.assert_called_once()

    @patch("murder.handler.react_to_mvi_queued")
    @patch("murder.handler.boto3")
    def test_routes_mvi_queued(
        self, boto3_mock: MagicMock, reactor_mock: MagicMock
    ) -> None:
        event = {
            "Records": [
                {
                    "eventName": "INSERT",
                    "dynamodb": {
                        "NewImage": {
                            "level": {"S": "murder"},
                            "status": {"S": "queued"},
                            "PK": {"S": "T#t1#P#p1"},
                            "SK": {"S": "S#w01#m01"},
                        },
                    },
                }
            ]
        }
        result = lambda_handler(event, None)
        assert result["processed"] == 1
        reactor_mock.assert_called_once()

    @patch("murder.handler.boto3")
    def test_skips_duplicate_status(self, boto3_mock: MagicMock) -> None:
        event = {
            "Records": [
                {
                    "eventName": "MODIFY",
                    "dynamodb": {
                        "NewImage": {
                            "level": {"S": "crow"},
                            "status": {"S": "completed"},
                            "PK": {"S": "T#t1#P#p1"},
                            "SK": {"S": "S#w01#m01#cr_plan_01"},
                        },
                        "OldImage": {
                            "level": {"S": "crow"},
                            "status": {"S": "completed"},
                            "PK": {"S": "T#t1#P#p1"},
                            "SK": {"S": "S#w01#m01#cr_plan_01"},
                        },
                    },
                }
            ]
        }
        result = lambda_handler(event, None)
        assert result["skipped"] == 1
        assert result["processed"] == 0
