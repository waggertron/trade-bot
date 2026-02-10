import asyncio
import pytest

from src.core.event_bus import EventBus, Event


class SampleEvent(Event):
    def __init__(self, data: str):
        super().__init__(event_type="sample")
        self.data = data


@pytest.fixture
def bus():
    return EventBus()


async def test_subscribe_and_publish(bus):
    received = []

    async def handler(event: SampleEvent):
        received.append(event.data)

    bus.subscribe("sample", handler)
    await bus.publish(SampleEvent("hello"))
    assert received == ["hello"]


async def test_multiple_subscribers(bus):
    received_a = []
    received_b = []

    async def handler_a(event):
        received_a.append(event.data)

    async def handler_b(event):
        received_b.append(event.data)

    bus.subscribe("sample", handler_a)
    bus.subscribe("sample", handler_b)
    await bus.publish(SampleEvent("test"))
    assert received_a == ["test"]
    assert received_b == ["test"]


async def test_unsubscribe(bus):
    received = []

    async def handler(event):
        received.append(event.data)

    bus.subscribe("sample", handler)
    bus.unsubscribe("sample", handler)
    await bus.publish(SampleEvent("ignored"))
    assert received == []


async def test_publish_no_subscribers(bus):
    # Should not raise
    await bus.publish(SampleEvent("nobody listening"))


async def test_event_history(bus):
    bus.enable_history()
    await bus.publish(SampleEvent("first"))
    await bus.publish(SampleEvent("second"))
    history = bus.get_history()
    assert len(history) == 2
    assert history[0].data == "first"
