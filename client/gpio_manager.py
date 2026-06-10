"""GpioManager: GPIO digital I/O."""
from __future__ import annotations

from enum import IntEnum
from typing import Any

import grpc

from api.common import types_pb2
from api.gpio_service.v26 import gpio_service_pb2 as gpio_pb2
from api.gpio_service.v26.gpio_service_pb2_grpc import GpioServiceStub

from .config import get_rpc_timeout


class GpioLevel(IntEnum):
    LOW  = 0
    HIGH = 1


class GpioDirection(IntEnum):
    OUT = 0
    IN  = 1


GPIO_LEVEL_LOW  = GpioLevel.LOW
GPIO_LEVEL_HIGH = GpioLevel.HIGH
GPIO_DIR_OUT    = GpioDirection.OUT
GPIO_DIR_IN     = GpioDirection.IN


class GpioPin:
    """Identifies a GPIO line by chip index and line offset.

    Args:
        name: Optional human-readable label (e.g. ``"LED0"``).
        number: Line offset within the gpiochip (maps to ``GpioPin.line`` in the proto).
        chip_number: gpiochip index — 0 for ``/dev/gpiochip0`` (maps to ``GpioPin.gpiochip``).
    """
    __slots__ = ("name", "number", "chip_number")

    def __init__(self, name: str = "", number: int = 0, chip_number: int = 0) -> None:
        self.name = name
        self.number = number
        self.chip_number = chip_number

    def __repr__(self) -> str:
        label = self.name or f"GPIO{self.number}"
        return f"GpioPin({label!r}, number={self.number}, chip={self.chip_number})"


def _to_proto_pin(pin: GpioPin) -> gpio_pb2.GpioPin:
    return gpio_pb2.GpioPin(gpiochip=pin.chip_number, line=pin.number, name=pin.name)


def _check_error(resp: Any, op_name: str) -> None:
    if resp.error.code != types_pb2.ERROR_CODE_NONE:
        raise RuntimeError(f"{op_name}: {resp.error.message or 'unknown error'}")


class GpioManager:
    """Control GPIO lines."""

    def __init__(self, channel: grpc.Channel) -> None:
        self._gpio = GpioServiceStub(channel)

    def _call(self, method, *args):
        return method(*args, timeout=get_rpc_timeout())

    def list_pins(self) -> list[GpioPin]:
        """Return all GPIO lines exported by the device."""
        resp = self._call(self._gpio.ListGPIOPins, types_pb2.Void())
        _check_error(resp, "list_pins")
        return [
            GpioPin(name=p.name, number=p.line, chip_number=p.gpiochip)
            for p in resp.pins
        ]

    def get_level(self, pin: GpioPin) -> GpioLevel:
        """Read the logical level of a GPIO line."""
        resp = self._call(self._gpio.GetGPIOLevel, gpio_pb2.GpioLevelRequest(pin=_to_proto_pin(pin)))
        _check_error(resp, f"get_level {pin}")
        return GpioLevel(resp.level)

    def set_level(self, pin: GpioPin, level: GpioLevel) -> None:
        """Drive a GPIO output HIGH or LOW."""
        resp = self._call(self._gpio.SetGPIOLevel, gpio_pb2.GpioLevelRequest(pin=_to_proto_pin(pin), level=level.value))
        _check_error(resp, f"set_level {pin}")

    def get_direction(self, pin: GpioPin) -> GpioDirection:
        """Read the line direction."""
        resp = self._call(self._gpio.GetGPIODirection, gpio_pb2.GpioDirectionRequest(pin=_to_proto_pin(pin)))
        _check_error(resp, f"get_direction {pin}")
        return GpioDirection(resp.direction)

    def set_direction(self, pin: GpioPin, direction: GpioDirection) -> None:
        """Set the line direction: ``GpioDirection.OUT`` for output, ``GpioDirection.IN`` for input."""
        resp = self._call(self._gpio.SetGPIODirection, gpio_pb2.GpioDirectionRequest(pin=_to_proto_pin(pin), direction=direction.value))
        _check_error(resp, f"set_direction {pin}")
