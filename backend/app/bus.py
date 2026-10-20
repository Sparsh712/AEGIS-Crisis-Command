"""Small asyncio pub/sub bus used by the trace stream."""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncContextManager, AsyncIterator

from .models import TraceStep


class TraceBus:
    """Fan out each trace step to every active subscriber."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[TraceStep]] = set()
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue[TraceStep]]:
        queue: asyncio.Queue[TraceStep] = asyncio.Queue()
        async with self._lock:
            self._subscribers.add(queue)
        try:
            yield queue
        finally:
            async with self._lock:
                self._subscribers.discard(queue)

    async def publish(self, step: TraceStep) -> None:
        """Publish a step to all current subscribers without blocking them."""

        async with self._lock:
            subscribers = tuple(self._subscribers)
        for queue in subscribers:
            queue.put_nowait(step)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


trace_bus = TraceBus()


async def publish(step: TraceStep) -> None:
    """Publish on the process-wide trace bus."""

    await trace_bus.publish(step)


def subscribe() -> AsyncContextManager[asyncio.Queue[TraceStep]]:
    """Subscribe to the process-wide trace bus."""

    return trace_bus.subscribe()
