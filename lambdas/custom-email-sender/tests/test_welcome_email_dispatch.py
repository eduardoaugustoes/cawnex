"""
Contract test: post-confirmation's async-invoke payload must reach SES.

Reproduces the Critical finding on Task 0.4 — auth-post-confirmation invokes
this Lambda with {"action": "send_welcome_email", ...} but handler() only
dispatched on triggerSource, so the welcome email silently no-op'd.
"""

from unittest.mock import MagicMock, patch

import handler


def _post_confirmation_payload(
    user_email: str = "founder@example.com",
    user_name: str = "Ada Founder",
    tenant_id: str = "t_18f2b3c1a2b_deadbeef",
) -> dict:
    """Mirrors the exact payload built in
    lambdas/auth-post-confirmation/handler.py:95-100."""
    return {
        "action": "send_welcome_email",
        "user_email": user_email,
        "user_name": user_name,
        "tenant_id": tenant_id,
    }


class TestWelcomeEmailDispatch:
    @patch.object(handler, "ses_client")
    def test_action_send_welcome_email_sends_via_ses(self, ses_client: MagicMock) -> None:
        ses_client.send_email.return_value = {"MessageId": "test-message-id"}

        event = _post_confirmation_payload(
            user_email="founder@example.com",
            user_name="Ada Founder",
        )

        result = handler.handler(event, None)

        assert result is True
        ses_client.send_email.assert_called_once()
        kwargs = ses_client.send_email.call_args.kwargs
        assert kwargs["Destination"] == {"ToAddresses": ["founder@example.com"]}
        assert "Welcome to Cawnex" in kwargs["Message"]["Subject"]["Data"]
        assert "Ada Founder" in kwargs["Message"]["Body"]["Html"]["Data"]

    @patch.object(handler, "ses_client")
    def test_action_send_welcome_email_defaults_missing_optional_fields(
        self, ses_client: MagicMock
    ) -> None:
        ses_client.send_email.return_value = {"MessageId": "test-message-id"}

        event = {"action": "send_welcome_email", "user_email": "noname@example.com"}

        result = handler.handler(event, None)

        assert result is True
        ses_client.send_email.assert_called_once()

    @patch.object(handler, "ses_client")
    def test_event_without_action_or_trigger_source_does_not_send(
        self, ses_client: MagicMock
    ) -> None:
        event = {"some": "unrelated-payload"}

        result = handler.handler(event, None)

        ses_client.send_email.assert_not_called()
        assert result == event
