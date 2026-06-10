"""I2CManager: I2C bus configuration and data transfer."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import grpc

from api.common import types_pb2
from api.i2c_service.v26 import i2c_service_pb2 as i2c_pb2
from api.i2c_service.v26.i2c_service_pb2_grpc import I2CServiceStub

from .config import get_rpc_timeout


@dataclass
class I2CConfig:
    """I2C bus configuration."""
    bus: int
    clock_hz: int
    ten_bit_addr: bool = False
    clock_stretching: bool = True


def _check_error(resp: Any, op_name: str) -> None:
    if resp.error.code != types_pb2.ERROR_CODE_NONE:
        raise RuntimeError(f"{op_name}: {resp.error.message or 'unknown error'}")


class I2CManager:
    """Read from and write to I2C devices.

    Use :meth:`open` to configure a bus and obtain an :class:`I2CBus` handle
    for subsequent operations without repeating the bus number.
    The flat methods (:meth:`scan_bus`, :meth:`read`, etc.) are still available
    for one-off calls.
    """

    def __init__(self, channel: grpc.Channel) -> None:
        self._stub = I2CServiceStub(channel)

    def _call(self, method, *args):
        return method(*args, timeout=get_rpc_timeout())

    def open(self, bus: int, clock_hz: int, ten_bit_addr: bool = False,
             clock_stretching: bool = True) -> I2CBus:
        """Configure a bus and return a handle for all subsequent operations."""
        self.set_config(I2CConfig(bus=bus, clock_hz=clock_hz,
                                  ten_bit_addr=ten_bit_addr,
                                  clock_stretching=clock_stretching))
        return I2CBus(self._stub, bus)

    def list_buses(self) -> list[int]:
        """Return available I2C bus numbers."""
        resp = self._call(self._stub.ListI2CBuses, types_pb2.Void())
        _check_error(resp, "list_buses")
        return list(resp.buses)

    def scan_bus(self, bus: int) -> list[int]:
        """Probe all 7-bit addresses on a bus. Returns responding addresses."""
        resp = self._call(self._stub.ScanI2CBus, i2c_pb2.I2CBusRequest(bus=bus))
        _check_error(resp, f"scan_bus {bus}")
        return list(resp.addresses)

    def get_config(self, bus: int) -> I2CConfig:
        """Return the current clock and addressing configuration for a bus."""
        resp = self._call(self._stub.GetI2CConfig, i2c_pb2.I2CBusRequest(bus=bus))
        _check_error(resp, f"get_config bus {bus}")
        return I2CConfig(
            bus=resp.bus,
            clock_hz=resp.clock_hz,
            ten_bit_addr=resp.ten_bit_addr,
            clock_stretching=resp.clock_stretching,
        )

    def set_config(self, cfg: I2CConfig) -> None:
        """Apply a bus configuration."""
        req = i2c_pb2.I2CConfigRequest(
            bus=cfg.bus,
            clock_hz=cfg.clock_hz,
            ten_bit_addr=cfg.ten_bit_addr,
            clock_stretching=cfg.clock_stretching,
        )
        resp = self._call(self._stub.SetI2CConfig, req)
        _check_error(resp, f"set_config bus {cfg.bus}")

    def transfer(self, bus: int, address: int, data: bytes = b"",
                 read_length: int = 0, flags: int = 0) -> bytes:
        """Perform a raw I2C transaction.

        Operation is inferred from the arguments:

        * ``data`` only → write
        * ``read_length`` only → read
        * both → write then read (combined transaction)
        """
        resp = self._call(
            self._stub.I2CTransfer,
            i2c_pb2.I2CTransferRequest(bus=bus, address=address,
                                       data=data, read_length=read_length,
                                       flags=flags),
        )
        _check_error(resp, f"transfer bus {bus} addr 0x{address:02X}")
        return resp.data

    def write(self, bus: int, addr: int, data: bytes) -> None:
        """Write bytes to an I2C device."""
        self.transfer(bus, addr, data=data)

    def read(self, bus: int, addr: int, n: int) -> bytes:
        """Read ``n`` bytes from an I2C device."""
        return self.transfer(bus, addr, read_length=n)

    def write_read(self, bus: int, addr: int, write_data: bytes,
                   read_len: int) -> bytes:
        """Write bytes then read back a response (combined transaction)."""
        return self.transfer(bus, addr, data=write_data, read_length=read_len)


class I2CBus:
    """Handle to a configured I2C bus returned by :meth:`I2CManager.open`."""

    def __init__(self, stub: I2CServiceStub, bus: int) -> None:
        self._stub = stub
        self._bus = bus

    def _call(self, method, *args):
        return method(*args, timeout=get_rpc_timeout())

    def scan(self) -> list[int]:
        """Probe all 7-bit addresses on the bus. Returns responding addresses."""
        resp = self._call(self._stub.ScanI2CBus, i2c_pb2.I2CBusRequest(bus=self._bus))
        _check_error(resp, f"scan bus {self._bus}")
        return list(resp.addresses)

    def get_config(self) -> I2CConfig:
        """Return the current clock and addressing configuration for the bus."""
        resp = self._call(self._stub.GetI2CConfig, i2c_pb2.I2CBusRequest(bus=self._bus))
        _check_error(resp, f"get_config bus {self._bus}")
        return I2CConfig(
            bus=resp.bus,
            clock_hz=resp.clock_hz,
            ten_bit_addr=resp.ten_bit_addr,
            clock_stretching=resp.clock_stretching,
        )

    def transfer(self, address: int, data: bytes = b"",
                 read_length: int = 0, flags: int = 0) -> bytes:
        """Perform a raw I2C transaction.

        * ``data`` only → write
        * ``read_length`` only → read
        * both → write then read (combined transaction)
        """
        resp = self._call(
            self._stub.I2CTransfer,
            i2c_pb2.I2CTransferRequest(bus=self._bus, address=address,
                                       data=data, read_length=read_length,
                                       flags=flags),
        )
        _check_error(resp, f"transfer bus {self._bus} addr 0x{address:02X}")
        return resp.data

    def write(self, addr: int, data: bytes) -> None:
        """Write bytes to an I2C device."""
        self.transfer(addr, data=data)

    def read(self, addr: int, n: int) -> bytes:
        """Read ``n`` bytes from an I2C device."""
        return self.transfer(addr, read_length=n)

    def write_read(self, addr: int, write_data: bytes, read_len: int) -> bytes:
        """Write bytes then read back a response (combined transaction)."""
        return self.transfer(addr, data=write_data, read_length=read_len)
