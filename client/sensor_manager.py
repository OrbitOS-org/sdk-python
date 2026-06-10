"""SensorManager: sensor capability discovery and event streaming."""
from __future__ import annotations

from typing import List

import grpc

from api.common import types_pb2
from api.sensor_service.v26 import sensor_service_pb2 as sensor_pb2
from api.sensor_service.v26.sensor_service_pb2_grpc import SensorServiceStub

from .config import get_rpc_timeout


class SensorManager:
    """Query available sensor types and subscribe to sensor events."""

    def __init__(self, channel: grpc.Channel) -> None:
        self._stub = SensorServiceStub(channel)

    def get_capabilities(self) -> List[str]:
        """Return the list of sensor type strings supported by this device."""
        resp = self._stub.GetCapabilities(types_pb2.Empty(), timeout=get_rpc_timeout())
        return list(resp.sensor_types)

    def subscribe_sensor_events(self, sensor_types: List[str], timeout: float = 30.0):
        """Open a server-side streaming call that yields ``SensorEventResponse`` messages.

        Args:
            sensor_types: Filter to specific sensor types (from :meth:`get_capabilities`).
            timeout: Stream read timeout in seconds.
        """
        req = sensor_pb2.SensorEventsRequest(sensor_types=sensor_types or [])
        return self._stub.SubscribeSensorEvents(req, timeout=timeout)
