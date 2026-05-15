"""Server-Sent Events frame encoder.

SSE wire format: https://html.spec.whatwg.org/multipage/server-sent-events.html
We emit `id:`, `event:`, and `data:` fields. Each event ends with a blank
line. Keepalive lines start with `:` (comment) and are ignored by clients.
"""

from __future__ import annotations

import json
from typing import Any


KEEPALIVE_COMMENT = ": keepalive\n\n"


def encode_event(
    *,
    event_id: str | None,
    event_name: str,
    data: dict[str, Any],
) -> str:
    """Encode a single SSE frame.

    JSON-encodes `data` so no raw newlines leak into the SSE line stream.
    """
    lines: list[str] = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event_name}")
    lines.append(f"data: {json.dumps(data, default=str)}")
    return "\n".join(lines) + "\n\n"
