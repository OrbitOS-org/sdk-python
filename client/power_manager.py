"""PowerManager: device reboot and shutdown."""
from __future__ import annotations

from dataclasses import dataclass

import grpc

from api.power_service.v26 import power_service_pb2 as power_pb2
from api.power_service.v26.power_service_pb2_grpc import PowerServiceStub

from .config import get_rpc_timeout


@dataclass
class PowerResult:
    success: bool
    message: str = ""


class PowerManager:
    """Trigger a device reboot or power-off."""

    def __init__(self, channel: grpc.Channel) -> None:
        self._stub = PowerServiceStub(channel)

    def reboot(self, force: bool = False, reason: str = "") -> PowerResult:
        """Reboot the device.

        Args:
            force: Skip graceful app shutdown.
            reason: Human-readable reason logged before reboot.
        """
        resp = self._stub.Reboot(power_pb2.RebootRequest(force=force, reason=reason or ""), timeout=get_rpc_timeout())
        return PowerResult(success=resp.value, message=resp.error.message)

    def shutdown(self, force: bool = False, reason: str = "") -> PowerResult:
        """Power off the device.

        Args:
            force: Skip graceful app shutdown.
            reason: Human-readable reason logged before shutdown.
        """
        resp = self._stub.Shutdown(power_pb2.ShutdownRequest(force=force, reason=reason or ""), timeout=get_rpc_timeout())
        return PowerResult(success=resp.value, message=resp.error.message)
