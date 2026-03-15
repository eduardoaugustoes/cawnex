"""Structured JSON logger with tenant/project/execution context."""

from __future__ import annotations

import json
import logging
from typing import Any


class StructuredLogger:
    """Emits structured JSON logs for CloudWatch filtering."""

    def __init__(
        self,
        component: str,
        tenant: str = "",
        project: str = "",
        execution_id: str = "",
    ) -> None:
        self.component = component
        self._context: dict[str, str] = {}
        if tenant:
            self._context["tenant"] = tenant
        if project:
            self._context["project"] = project
        if execution_id:
            self._context["execution_id"] = execution_id

        self._logger = logging.getLogger(f"cawnex.{component}")

    def _build_payload(self, event_name: str, **kwargs: Any) -> str:
        payload: dict[str, Any] = {
            "component": self.component,
            "event": event_name,
            **self._context,
            **kwargs,
        }
        return json.dumps(payload, default=str)

    def event(self, event_name: str, **kwargs: Any) -> None:
        self._logger.info(self._build_payload(event_name, **kwargs))

    def error(self, event_name: str, **kwargs: Any) -> None:
        self._logger.error(self._build_payload(event_name, **kwargs))

    def warning(self, event_name: str, **kwargs: Any) -> None:
        self._logger.warning(self._build_payload(event_name, **kwargs))
