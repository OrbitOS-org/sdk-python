"""EventManager: system-wide event subscription."""
from __future__ import annotations

from typing import Generator

import grpc

from api.event_service.v26 import event_service_pb2 as event_pb2
from api.event_service.v26.event_service_pb2_grpc import EventServiceStub

from .config import get_rpc_timeout

# Re-export EventType enum class and all constants for convenience
EventType = event_pb2.EventType

EVENT_TYPE_UNKNOWN = event_pb2.EVENT_TYPE_UNKNOWN
EVENT_APP_INSTALLED = event_pb2.EVENT_APP_INSTALLED
EVENT_APP_REMOVED = event_pb2.EVENT_APP_REMOVED
EVENT_APP_UPDATED = event_pb2.EVENT_APP_UPDATED
EVENT_APP_STARTED = event_pb2.EVENT_APP_STARTED
EVENT_APP_STOPPED = event_pb2.EVENT_APP_STOPPED
EVENT_APP_CRASHED = event_pb2.EVENT_APP_CRASHED
EVENT_APP_REJECTED = event_pb2.EVENT_APP_REJECTED
EVENT_SYSTEM_REBOOT = event_pb2.EVENT_SYSTEM_REBOOT
EVENT_SYSTEM_FACTORY_RESET = event_pb2.EVENT_SYSTEM_FACTORY_RESET
EVENT_SYSTEM_UPDATE = event_pb2.EVENT_SYSTEM_UPDATE
EVENT_NET_UP = event_pb2.EVENT_NET_UP
EVENT_NET_DOWN = event_pb2.EVENT_NET_DOWN


class EventManager:
    """Subscribe to system events emitted by the Gravity runtime."""

    def __init__(self, channel: grpc.Channel) -> None:
        self._stub = EventServiceStub(channel)

    def subscribe(self, *event_types: "event_pb2.EventType.ValueType", timeout: float | None = None) -> Generator:
        """Open a server-side event stream and yield ``Event`` proto messages.

        Args:
            *event_types: Filter to specific ``EVENT_*`` constants.
                Pass no arguments to receive all event types.
            timeout: Stream idle timeout in seconds (``None`` = no timeout).

        Example::

            # All events
            for event in client.event_manager.subscribe():
                print(event.type, event.payload)
                if done:
                    break

            # Filtered
            for event in client.event_manager.subscribe(EVENT_APP_CRASHED, EVENT_NET_DOWN):
                alert(event)
        """
        req = event_pb2.SubscribeRequest(types=list(event_types))
        stream = self._stub.Subscribe(req, timeout=timeout)
        try:
            for event in stream:
                yield event
        finally:
            stream.cancel()
