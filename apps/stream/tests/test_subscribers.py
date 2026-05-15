"""Tests for the subscriber registry + fanout."""

from __future__ import annotations

import asyncio

import pytest

from stream.subscribers import (
    BackpressureDrop,
    Subscriber,
    SubscriberRegistry,
)


@pytest.fixture
def registry() -> SubscriberRegistry:
    return SubscriberRegistry(max_queue_depth=4)


async def test_subscriber_receives_published_event(registry: SubscriberRegistry) -> None:
    sub = Subscriber(wave_id="w1")
    registry.register(sub)
    await registry.publish("w1", "frame-1")
    assert await asyncio.wait_for(sub.queue.get(), timeout=0.1) == "frame-1"


async def test_publish_to_unsubscribed_wave_is_noop(registry: SubscriberRegistry) -> None:
    await registry.publish("w-nonexistent", "frame-x")


async def test_fanout_delivers_to_multiple_subscribers(registry: SubscriberRegistry) -> None:
    a = Subscriber(wave_id="w1")
    b = Subscriber(wave_id="w1")
    registry.register(a)
    registry.register(b)
    await registry.publish("w1", "frame-1")
    assert await a.queue.get() == "frame-1"
    assert await b.queue.get() == "frame-1"


async def test_other_waves_do_not_receive(registry: SubscriberRegistry) -> None:
    a = Subscriber(wave_id="w1")
    b = Subscriber(wave_id="w2")
    registry.register(a)
    registry.register(b)
    await registry.publish("w1", "frame-1")
    assert await a.queue.get() == "frame-1"
    assert b.queue.qsize() == 0


async def test_unregister_stops_delivery(registry: SubscriberRegistry) -> None:
    sub = Subscriber(wave_id="w1")
    registry.register(sub)
    registry.unregister(sub)
    await registry.publish("w1", "frame-x")
    assert sub.queue.qsize() == 0


async def test_backpressure_drops_slow_subscriber(registry: SubscriberRegistry) -> None:
    sub = Subscriber(wave_id="w1")
    registry.register(sub)
    for i in range(4):
        await registry.publish("w1", f"frame-{i}")
    sub.raise_if_dropped()  # still healthy
    await registry.publish("w1", "frame-overflow")
    with pytest.raises(BackpressureDrop):
        sub.raise_if_dropped()
    assert sub not in registry._by_wave.get("w1", set())  # type: ignore[attr-defined]


async def test_register_is_idempotent(registry: SubscriberRegistry) -> None:
    sub = Subscriber(wave_id="w1")
    registry.register(sub)
    registry.register(sub)
    await registry.publish("w1", "frame-1")
    assert await sub.queue.get() == "frame-1"
    assert sub.queue.qsize() == 0
