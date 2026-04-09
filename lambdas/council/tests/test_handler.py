"""Tests for council handler — stream event entry point."""

from unittest.mock import MagicMock, patch

from council.handler import lambda_handler


class TestLambdaHandler:
    @patch("council.handler._process_council_task")
    def test_routes_insert_event(self, mock_process: MagicMock) -> None:
        event = {
            "Records": [
                {
                    "eventName": "INSERT",
                    "dynamodb": {
                        "NewImage": {
                            "PK": {"S": "T#t1#P#p1"},
                            "SK": {"S": "COUNCIL#wr_w01_abc"},
                            "status": {"S": "pending"},
                            "type": {"S": "wave_review"},
                            "wave_id": {"S": "w01"},
                            "auto_mode": {"S": "auto"},
                            "context": {"M": {}},
                        }
                    },
                }
            ]
        }

        lambda_handler(event, None)

        mock_process.assert_called_once()

    def test_skips_non_insert_events(self) -> None:
        event = {
            "Records": [
                {
                    "eventName": "MODIFY",
                    "dynamodb": {
                        "NewImage": {
                            "PK": {"S": "T#t1#P#p1"},
                            "SK": {"S": "COUNCIL#wr_w01_abc"},
                            "status": {"S": "completed"},
                        }
                    },
                }
            ]
        }

        result = lambda_handler(event, None)
        assert result["processed"] == 0
        assert result["skipped"] == 1

    def test_skips_non_pending_status(self) -> None:
        event = {
            "Records": [
                {
                    "eventName": "INSERT",
                    "dynamodb": {
                        "NewImage": {
                            "PK": {"S": "T#t1#P#p1"},
                            "SK": {"S": "COUNCIL#wr_w01_abc"},
                            "status": {"S": "completed"},
                        }
                    },
                }
            ]
        }

        result = lambda_handler(event, None)
        assert result["processed"] == 0
