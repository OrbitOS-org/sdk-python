"""SpiManager: SPI device configuration and data transfer."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import grpc

from api.common import types_pb2
from api.spi_service.v26 import spi_service_pb2 as spi_pb2
from api.spi_service.v26.spi_service_pb2_grpc import SpiServiceStub

from .config import get_rpc_timeout


@dataclass
class SpiConfig:
    """SPI bus and device configuration."""
    bus: int
    chip_select: int
    max_speed_hz: int
    bits_per_word: int
    mode: int = 0        # SPI_MODE_0 (CPOL=0 CPHA=0)
    lsb_first: bool = False


def _check_error(resp: Any, op_name: str) -> None:
    if resp.error.code != types_pb2.ERROR_CODE_NONE:
        raise RuntimeError(f"{op_name}: {resp.error.message or 'unknown error'}")


class SpiManager:
    """Configure SPI buses and perform full-duplex transfers.

    Use :meth:`open` to configure a device and obtain a :class:`SpiDevice`
    handle for subsequent operations without repeating bus/chip-select.
    The flat methods (:meth:`transfer`, :meth:`write`, etc.) are still
    available for one-off calls.
    """

    def __init__(self, channel: grpc.Channel) -> None:
        self._stub = SpiServiceStub(channel)

    def _call(self, method, *args):
        return method(*args, timeout=get_rpc_timeout())

    def open(self, bus: int, chip_select: int, max_speed_hz: int,
             bits_per_word: int, mode: int = 0,
             lsb_first: bool = False) -> SpiDevice:
        """Configure a SPI device and return a handle for all subsequent operations."""
        self.set_config(SpiConfig(bus=bus, chip_select=chip_select,
                                  max_speed_hz=max_speed_hz,
                                  bits_per_word=bits_per_word,
                                  mode=mode, lsb_first=lsb_first))
        return SpiDevice(self._stub, bus, chip_select)

    def list_devices(self) -> list[str]:
        """Return device paths for all available SPI devices."""
        resp = self._call(self._stub.ListSpiBuses, types_pb2.Void())
        _check_error(resp, "list_devices")
        return list(resp.devices)

    def get_config(self, bus: int, chip_select: int) -> SpiConfig:
        """Return the current configuration for a bus/CS combination."""
        resp = self._call(self._stub.GetSpiConfig,
                          spi_pb2.SpiBusRequest(bus=bus, chip_select=chip_select))
        _check_error(resp, f"get_config bus {bus} cs {chip_select}")
        return SpiConfig(
            bus=resp.bus,
            chip_select=resp.chip_select,
            max_speed_hz=resp.max_speed_hz,
            bits_per_word=resp.bits_per_word,
            mode=resp.mode,
            lsb_first=resp.lsb_first,
        )

    def set_config(self, cfg: SpiConfig) -> None:
        """Apply a SPI bus configuration."""
        req = spi_pb2.SpiConfigRequest(
            bus=cfg.bus,
            chip_select=cfg.chip_select,
            max_speed_hz=cfg.max_speed_hz,
            bits_per_word=cfg.bits_per_word,
            lsb_first=cfg.lsb_first,
            mode=cfg.mode,
        )
        resp = self._call(self._stub.SetSpiConfig, req)
        _check_error(resp, f"set_config bus {cfg.bus} cs {cfg.chip_select}")

    def transfer(self, bus: int, chip_select: int, data_out: bytes,
                 read_length: int) -> bytes:
        """Perform a full-duplex SPI transfer.

        Args:
            bus: SPI bus index.
            chip_select: Chip-select line index.
            data_out: Bytes to clock out (MOSI).
            read_length: Number of bytes to clock in (MISO).

        Returns:
            Bytes received from the device.
        """
        resp = self._call(
            self._stub.SpiTransfer,
            spi_pb2.SpiTransferRequest(bus=bus, chip_select=chip_select,
                                       data_out=data_out, read_length=read_length),
        )
        _check_error(resp, f"transfer bus {bus} cs {chip_select}")
        return resp.data_in

    def write(self, bus: int, chip_select: int, data: bytes) -> None:
        """Clock bytes out without reading a response."""
        self.transfer(bus, chip_select, data, 0)

    def read(self, bus: int, chip_select: int, n: int) -> bytes:
        """Clock in ``n`` bytes (clocks out zero-bytes on MOSI)."""
        return self.transfer(bus, chip_select, b"", n)

    def write_read(self, bus: int, chip_select: int, data_out: bytes) -> bytes:
        """Full-duplex transfer where read length matches write length."""
        return self.transfer(bus, chip_select, data_out, len(data_out))


class SpiDevice:
    """Handle to a configured SPI device returned by :meth:`SpiManager.open`."""

    def __init__(self, stub: SpiServiceStub, bus: int, chip_select: int) -> None:
        self._stub = stub
        self._bus = bus
        self._cs = chip_select

    def _call(self, method, *args):
        return method(*args, timeout=get_rpc_timeout())

    def get_config(self) -> SpiConfig:
        """Return the current configuration for this device."""
        resp = self._call(self._stub.GetSpiConfig,
                          spi_pb2.SpiBusRequest(bus=self._bus, chip_select=self._cs))
        _check_error(resp, f"get_config spidev{self._bus}.{self._cs}")
        return SpiConfig(
            bus=resp.bus,
            chip_select=resp.chip_select,
            max_speed_hz=resp.max_speed_hz,
            bits_per_word=resp.bits_per_word,
            mode=resp.mode,
            lsb_first=resp.lsb_first,
        )

    def transfer(self, data_out: bytes, read_length: int) -> bytes:
        """Perform a full-duplex SPI transfer.

        Args:
            data_out: Bytes to clock out (MOSI).
            read_length: Number of bytes to clock in (MISO).

        Returns:
            Bytes received from the device.
        """
        resp = self._call(
            self._stub.SpiTransfer,
            spi_pb2.SpiTransferRequest(bus=self._bus, chip_select=self._cs,
                                       data_out=data_out, read_length=read_length),
        )
        _check_error(resp, f"transfer spidev{self._bus}.{self._cs}")
        return resp.data_in

    def write(self, data: bytes) -> None:
        """Clock bytes out without reading a response."""
        self.transfer(data, 0)

    def read(self, n: int) -> bytes:
        """Clock in ``n`` bytes (clocks out zero-bytes on MOSI)."""
        return self.transfer(b"", n)

    def write_read(self, data_out: bytes) -> bytes:
        """Full-duplex transfer where read length matches write length."""
        return self.transfer(data_out, len(data_out))
