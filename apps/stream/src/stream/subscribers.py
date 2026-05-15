"""In-memory subscriber registry with per-subscriber bounded queues.

Publishers do non-blocking put_nowait; if a queue is full, the subscriber
is evicted with a BackpressureDrop marker so the connection coroutine can
clean up and let the client reconnect.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


class BackpressureDrop(Exception):
    """Raised when a subscriber's queue overflowed and they were evicted."""


@dataclass(eq=False)
class Subscriber:
    wave_id: str
    queue: asyncio.Queue[str] = field(default_factory=lambda: asyncio.Queue(maxsize=100))
    _dropped: bool = field(default=False, init=False)

    def mark_dropped(self) -> None:
        self._dropped = True

    def raise_if_dropped(self) -> None:
        if self._dropped:
            raise BackpressureDrop("subscriber queue overflowed")


class SubscriberRegistry:
    """Keyed by wave_id → set of Subscribers. Single-event-loop only (not thread-safe)."""

    def __init__(self, max_queue_depth: int = 100) -> None:
        self._by_wave: dict[str, set[Subscriber]] = {}
        self._max_queue_depth = max_queue_depth

    def register(self, sub: Subscriber) -> None:
        if sub.queue.maxsize != self._max_queue_depth:
            sub.queue = asyncio.Queue(maxsize=self._max_queue_depth)
        self._by_wave.setdefault(sub.wave_id, set()).add(sub)

    def unregister(self, sub: Subscriber) -> None:
        bucket = self._by_wave.get(sub.wave_id)
        if bucket is None:
            return
        bucket.discard(sub)
        if not bucket:
            del self._by_wave[sub.wave_id]

    async def publish(self, wave_id: str, frame: str) -> None:
        """Fan out a frame to all subscribers of wave_id. Evicts slow consumers."""
        bucket = self._by_wave.get(wave_id)
        if not bucket:
            return
        for sub in list(bucket):
            try:
                sub.queue.put_nowait(frame)
            except asyncio.QueueFull:
                sub.mark_dropped()
                self.unregister(sub)
