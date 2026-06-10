"""PwmManager: hardware PWM channel control."""
from __future__ import annotations

from typing import Any

import grpc

from api.common import types_pb2
from api.pwm_service.v26 import pwm_service_pb2 as pwm_pb2
from api.pwm_service.v26.pwm_service_pb2_grpc import PwmServiceStub

from .config import get_rpc_timeout


class PwmChannel:
    """Identifies a hardware PWM channel.

    Args:
        channel: Channel index.
        name: Optional human-readable label.
    """
    __slots__ = ("channel", "name")

    def __init__(self, channel: int = 0, name: str = "") -> None:
        self.channel = channel
        self.name = name

    def __repr__(self) -> str:
        label = self.name or f"PWM{self.channel}"
        return f"PwmChannel({label!r}, channel={self.channel})"


class PwmProperties:
    """Current state of a PWM channel."""
    __slots__ = ("channel", "enabled", "duty_cycle", "frequency_hz")

    def __init__(self, channel: PwmChannel | None = None,
                 enabled: bool = False,
                 duty_cycle: float = 0.0,
                 frequency_hz: float = 0.0) -> None:
        self.channel = channel
        self.enabled = enabled
        self.duty_cycle = duty_cycle
        self.frequency_hz = frequency_hz

    def __repr__(self) -> str:
        return (f"PwmProperties(channel={self.channel}, enabled={self.enabled}, "
                f"duty_cycle={self.duty_cycle}, freq_hz={self.frequency_hz})")


def _to_proto_channel(ch: PwmChannel) -> pwm_pb2.PwmChannel:
    return pwm_pb2.PwmChannel(channel=ch.channel, name=ch.name)


def _check_error(resp: Any, op_name: str) -> None:
    if resp.error.code != types_pb2.ERROR_CODE_NONE:
        raise RuntimeError(f"{op_name}: {resp.error.message or 'unknown error'}")


class PwmManager:
    """Control hardware PWM channels."""

    def __init__(self, channel: grpc.Channel) -> None:
        self._stub = PwmServiceStub(channel)

    def _call(self, method, *args):
        return method(*args, timeout=get_rpc_timeout())

    def list_channels(self) -> list[PwmChannel]:
        """Return all PWM channels available on the device."""
        resp = self._call(self._stub.ListPwmChannels, types_pb2.Empty())
        _check_error(resp, "list_channels")
        return [
            PwmChannel(channel=c.channel, name=c.name)
            for c in resp.channels
        ]

    def get_properties(self, ch: PwmChannel) -> PwmProperties:
        """Read the current configuration of a PWM channel."""
        resp = self._call(self._stub.GetPwmProperties, pwm_pb2.PwmChannelRequest(channel=_to_proto_channel(ch)))
        _check_error(resp, f"get_properties {ch}")
        if not resp.HasField("properties"):
            return PwmProperties(channel=ch)
        props = resp.properties
        sdk_ch = PwmChannel(
            channel=props.channel.channel,
            name=props.channel.name,
        ) if props.HasField("channel") else ch
        return PwmProperties(
            channel=sdk_ch,
            enabled=props.enabled,
            duty_cycle=props.duty_cycle,
            frequency_hz=props.frequency_hz,
        )

    def set_pwm(self, ch: PwmChannel, duty_cycle: float, frequency_hz: float) -> None:
        """Configure and start a PWM channel.

        Args:
            ch: PWM channel (use :meth:`list_channels` to enumerate).
            duty_cycle: Fraction 0.0–1.0.
            frequency_hz: Output frequency in Hertz.
        """
        req = pwm_pb2.SetPwmRequest(
            channel=_to_proto_channel(ch),
            duty_cycle=duty_cycle,
            frequency_hz=frequency_hz,
        )
        resp = self._call(self._stub.SetPwm, req)
        _check_error(resp, f"set_pwm {ch}")

    def stop_pwm(self, ch: PwmChannel) -> None:
        """Disable PWM output on a channel."""
        resp = self._call(self._stub.StopPwm, pwm_pb2.PwmChannelRequest(channel=_to_proto_channel(ch)))
        _check_error(resp, f"stop_pwm {ch}")
