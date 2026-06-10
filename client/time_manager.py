"""TimeManager: system clock and NTP configuration."""
from __future__ import annotations

import grpc

from api.common import types_pb2
from api.time_service.v26 import time_service_pb2 as time_pb2
from api.time_service.v26.time_service_pb2_grpc import TimeServiceStub

from .config import get_rpc_timeout


class TimeManager:
    """Read and configure the system clock and NTP synchronisation."""

    def __init__(self, channel: grpc.Channel) -> None:
        self._stub = TimeServiceStub(channel)

    def _call(self, method, *args):
        return method(*args, timeout=get_rpc_timeout())

    def get_ntp_config(self):
        """Return the current NTP server configuration."""
        return self._call(self._stub.GetNTPConfig, types_pb2.Empty())

    def set_ntp_config(self, request):
        """Apply a new NTP configuration."""
        return self._call(self._stub.SetNTPConfig, request)

    def is_ntp_sync_enabled(self) -> bool:
        resp = self._call(self._stub.IsNTPSyncEnabled, types_pb2.Empty())
        return resp.value

    def enable_ntp_sync(self) -> bool:
        resp = self._call(self._stub.EnableNTPSync, types_pb2.Empty())
        return resp.value

    def disable_ntp_sync(self) -> bool:
        resp = self._call(self._stub.DisableNTPSync, types_pb2.Empty())
        return resp.value

    def get_time_seconds(self) -> int:
        """Return current Unix time in whole seconds."""
        resp = self._call(self._stub.GetTimeSeconds, types_pb2.Empty())
        return resp.time

    def set_time_seconds(self, time_sec: int) -> bool:
        """Set the system clock (Unix seconds). Only effective when NTP is disabled."""
        resp = self._call(self._stub.SetTimeSeconds, time_pb2.SetTimeRequest(time=time_sec))
        return resp.value

    def get_time_millis(self) -> int:
        """Return current Unix time in milliseconds."""
        resp = self._call(self._stub.GetTimeMillis, types_pb2.Empty())
        return resp.time

    def set_time_millis(self, time_ms: int) -> bool:
        """Set the system clock (Unix milliseconds). Only effective when NTP is disabled."""
        resp = self._call(self._stub.SetTimeMillis, time_pb2.SetTimeRequest(time=time_ms))
        return resp.value

    def get_uptime(self):
        """Return the device uptime as a proto ``UptimeResponse``."""
        return self._call(self._stub.GetUptime, types_pb2.Empty())
