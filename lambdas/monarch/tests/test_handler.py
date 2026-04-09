"""Tests for Monarch handler mode routing."""

from unittest.mock import MagicMock, patch


class TestModeRouting:
    @patch("monarch.handler.run_monarch")
    def test_default_mode_calls_run_monarch(self, mock_run: MagicMock) -> None:
        from monarch.handler import lambda_handler

        event = {
            "Records": [
                {
                    "eventName": "INSERT",
                    "dynamodb": {
                        "NewImage": {
                            "PK": {"S": "T#t1#P#p1"},
                            "SK": {"S": "MONARCH#setup_abc"},
                            "status": {"S": "pending"},
                        }
                    },
                }
            ]
        }
        lambda_handler(event, None)
        mock_run.assert_called_once()

    @patch("monarch.handler.run_monarch_continuation")
    def test_continuation_mode(self, mock_run: MagicMock) -> None:
        from monarch.handler import lambda_handler

        event = {
            "Records": [
                {
                    "eventName": "INSERT",
                    "dynamodb": {
                        "NewImage": {
                            "PK": {"S": "T#t1#P#p1"},
                            "SK": {"S": "MONARCH#continuation_abc"},
                            "status": {"S": "pending"},
                            "mode": {"S": "continuation"},
                        }
                    },
                }
            ]
        }
        lambda_handler(event, None)
        mock_run.assert_called_once()

    @patch("monarch.handler.run_monarch_wave_launch")
    def test_wave_launch_mode(self, mock_run: MagicMock) -> None:
        from monarch.handler import lambda_handler

        event = {
            "Records": [
                {
                    "eventName": "INSERT",
                    "dynamodb": {
                        "NewImage": {
                            "PK": {"S": "T#t1#P#p1"},
                            "SK": {"S": "MONARCH#wave_launch_abc"},
                            "status": {"S": "pending"},
                            "mode": {"S": "wave_launch"},
                        }
                    },
                }
            ]
        }
        lambda_handler(event, None)
        mock_run.assert_called_once()

    def test_skips_non_insert(self) -> None:
        from monarch.handler import lambda_handler

        event = {
            "Records": [
                {
                    "eventName": "MODIFY",
                    "dynamodb": {
                        "NewImage": {
                            "PK": {"S": "T#t1#P#p1"},
                            "SK": {"S": "MONARCH#abc"},
                        }
                    },
                }
            ]
        }
        result = lambda_handler(event, None)
        assert result["skipped"] == 1
        assert result["processed"] == 0
