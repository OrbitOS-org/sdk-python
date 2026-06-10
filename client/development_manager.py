"""DevelopmentManager: remote log streaming from the device."""
from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from enum import IntEnum

import grpc

from api.development_service.v26 import development_service_pb2 as dev_pb2
from api.development_service.v26.development_service_pb2_grpc import DevelopmentServiceStub

from .config import get_rpc_timeout


class LogLevel(IntEnum):
    DEBUG   = 0
    INFO    = 1
    WARNING = 2
    ERROR   = 3
    FATAL   = 4


LOG_LEVEL_DEBUG   = LogLevel.DEBUG
LOG_LEVEL_INFO    = LogLevel.INFO
LOG_LEVEL_WARNING = LogLevel.WARNING
LOG_LEVEL_ERROR   = LogLevel.ERROR
LOG_LEVEL_FATAL   = LogLevel.FATAL

_LEVEL_STRINGS = {0: "T", 1: "D", 2: "I", 3: "W", 4: "E", 5: "F"}


@dataclass
class LogEntry:
    """A single log line received from the device."""
    timestamp_ms: int
    app: str
    tag: str
    level: LogLevel
    level_str: str
    message: str


class DevelopmentManager:
    """Stream live log output from the device's log daemon."""

    def __init__(self, channel: grpc.Channel) -> None:
        self._stub = DevelopmentServiceStub(channel)

    def subscribe_logs(self, app: str = "", tag: str = "", level: LogLevel = LogLevel.DEBUG, timeout: float = 60.0):
        """Open a server-side log stream and yield typed :class:`LogEntry` objects.

        Args:
            app: Filter to a specific app name (empty = all apps).
            tag: Filter to a specific tag (empty = all tags).
            level: Minimum log level: 0=TRACE 1=DEBUG 2=INFO 3=WARN 4=ERROR 5=FATAL.
            timeout: Stream idle timeout in seconds.

        Example::

            for entry in client.development_manager.subscribe_logs(app="myapp", level=2):
                print(entry.timestamp_ms, entry.level_str, entry.message)
        """
        req = dev_pb2.LogSubscribeRequest(app=app or "", tag=tag or "", level=level)
        for msg in self._stub.SubscribeLogs(req, timeout=timeout):
            lvl = msg.level
            yield LogEntry(
                timestamp_ms=msg.timestamp_ms,
                app=msg.app,
                tag=msg.tag,
                level=LogLevel(lvl),
                level_str=_LEVEL_STRINGS.get(lvl, "?"),
                message=msg.message,
            )

    def subscribe_logs_async(self, app: str = "", tag: str = "", level: LogLevel = LogLevel.DEBUG,
                             max_queue: int = 1000) -> queue.Queue:
        """Start a background thread that pushes :class:`LogEntry` objects into a queue.

        The thread reconnects automatically if the stream drops. Put ``None`` into the
        queue to signal shutdown (read the sentinel to detect it).

        Args:
            app: App name filter.
            tag: Tag filter.
            level: Minimum log level.
            max_queue: Maximum number of entries buffered before dropping.

        Returns:
            A :class:`queue.Queue` that receives :class:`LogEntry` items.
        """
        q: queue.Queue = queue.Queue(maxsize=max_queue)
        stop_event = threading.Event()

        def _worker():
            while not stop_event.is_set():
                try:
                    for entry in self.subscribe_logs(app=app, tag=tag, level=level, timeout=None):
                        if stop_event.is_set():
                            break
                        try:
                            q.put_nowait(entry)
                        except queue.Full:
                            pass
                except Exception:
                    if stop_event.is_set():
                        break
            q.put(None)

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        q._stop_event = stop_event  # type: ignore[attr-defined]
        return q
