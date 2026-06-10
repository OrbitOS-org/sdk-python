"""UartManager: UART port operations."""
from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Iterator

import grpc

from api.common import types_pb2
from api.uart_service.v26 import uart_service_pb2 as uart_pb2
from api.uart_service.v26.uart_service_pb2_grpc import UartServiceStub

from .config import get_rpc_timeout


class UartParity(IntEnum):
    NONE = 0
    EVEN = 1
    ODD  = 2


class UartStopBits(IntEnum):
    ONE = 0
    TWO = 1


class UartFlowControl(IntEnum):
    NONE     = 0
    HARDWARE = 1
    SOFTWARE = 2


UART_PARITY_NONE    = UartParity.NONE
UART_PARITY_EVEN    = UartParity.EVEN
UART_PARITY_ODD     = UartParity.ODD
UART_STOPBITS_1     = UartStopBits.ONE
UART_STOPBITS_2     = UartStopBits.TWO
UART_FLOW_NONE      = UartFlowControl.NONE
UART_FLOW_HARDWARE  = UartFlowControl.HARDWARE
UART_FLOW_SOFTWARE  = UartFlowControl.SOFTWARE


@dataclass
class UartConfig:
    """UART port open parameters."""
    port: str
    baudrate: int
    data_bits: int
    parity: UartParity = UartParity.NONE
    stop_bits: UartStopBits = UartStopBits.ONE
    flow_control: UartFlowControl = UartFlowControl.NONE


def _check_error(resp: Any, op_name: str) -> None:
    if resp.error.code != types_pb2.ERROR_CODE_NONE:
        raise RuntimeError(f"{op_name}: {resp.error.message or 'unknown error'}")


class UartManager:
    """Open, configure, read from, and write to UART ports.

    Use :meth:`open` to open a port and obtain a :class:`UartPort` handle
    for subsequent operations without repeating the port name.
    The flat methods (:meth:`write`, :meth:`listen`, etc.) are still
    available for one-off calls.
    """

    def __init__(self, channel: grpc.Channel) -> None:
        self._stub = UartServiceStub(channel)

    def _call(self, method, *args):
        return method(*args, timeout=get_rpc_timeout())

    def list_ports(self) -> list[str]:
        """Return device paths for all available UART ports."""
        resp = self._call(self._stub.ListUartPorts, types_pb2.Void())
        _check_error(resp, "list_ports")
        return list(resp.ports)

    def open(self, cfg: UartConfig) -> UartPort:
        """Open and configure a UART port, returning a handle for all subsequent operations."""
        req = uart_pb2.UartConfigRequest(
            port=cfg.port,
            baudrate=int(cfg.baudrate),
            data_bits=int(cfg.data_bits),
            parity=cfg.parity,
            stop_bits=cfg.stop_bits,
            flow_control=cfg.flow_control,
        )
        resp = self._call(self._stub.OpenUart, req)
        _check_error(resp, f"open {cfg.port}")
        return UartPort(self._stub, cfg.port)

    def close(self, port: str) -> None:
        """Close an open UART port."""
        resp = self._call(self._stub.CloseUart, uart_pb2.UartPortRequest(port=port))
        _check_error(resp, f"close {port}")

    def get_config(self, port: str) -> UartConfig:
        """Return the current configuration of an open port."""
        resp = self._call(self._stub.GetUartConfig, uart_pb2.UartPortRequest(port=port))
        _check_error(resp, f"get_config {port}")
        return UartConfig(
            port=resp.port,
            baudrate=resp.baudrate,
            data_bits=resp.data_bits,
            parity=UartParity(resp.parity),
            stop_bits=UartStopBits(resp.stop_bits),
            flow_control=UartFlowControl(resp.flow_control),
        )

    def write(self, port: str, data: bytes) -> int:
        """Write bytes to an open port. Returns the number of bytes written."""
        resp = self._call(self._stub.WriteUart, uart_pb2.UartWriteRequest(port=port, data=data))
        _check_error(resp, f"write {port}")
        return resp.bytes_written

    def listen(self, port: str, max_chunk_size: int = 256) -> Iterator[bytes]:
        """Stream received bytes from an open port.

        Yields raw ``bytes`` chunks as they arrive from the device.
        The generator runs until the stream is cancelled or an error occurs.

        Args:
            port: Port device path (e.g. ``"/dev/ttyS0"``).
            max_chunk_size: Maximum bytes per chunk returned by the server.
        """
        req = uart_pb2.UartReadRequest(port=port, max_chunk_size=max_chunk_size)
        stream = self._stub.ListenUart(req, timeout=max(30.0, get_rpc_timeout()))
        for chunk in stream:
            _check_error(chunk, f"listen {port}")
            if chunk.data:
                yield chunk.data


class UartPort:
    """Handle to an open UART port returned by :meth:`UartManager.open`."""

    def __init__(self, stub: UartServiceStub, port: str) -> None:
        self._stub = stub
        self._port = port

    def _call(self, method, *args):
        return method(*args, timeout=get_rpc_timeout())

    def close(self) -> None:
        """Close the port."""
        resp = self._call(self._stub.CloseUart, uart_pb2.UartPortRequest(port=self._port))
        _check_error(resp, f"close {self._port}")

    def get_config(self) -> UartConfig:
        """Return the current configuration of the port."""
        resp = self._call(self._stub.GetUartConfig, uart_pb2.UartPortRequest(port=self._port))
        _check_error(resp, f"get_config {self._port}")
        return UartConfig(
            port=resp.port,
            baudrate=resp.baudrate,
            data_bits=resp.data_bits,
            parity=UartParity(resp.parity),
            stop_bits=UartStopBits(resp.stop_bits),
            flow_control=UartFlowControl(resp.flow_control),
        )

    def write(self, data: bytes) -> int:
        """Write bytes to the port. Returns the number of bytes written."""
        resp = self._call(self._stub.WriteUart,
                          uart_pb2.UartWriteRequest(port=self._port, data=data))
        _check_error(resp, f"write {self._port}")
        return resp.bytes_written

    def listen(self, max_chunk_size: int = 256) -> Iterator[bytes]:
        """Stream received bytes from the port.

        Yields raw ``bytes`` chunks as they arrive from the device.
        The generator runs until the stream is cancelled or an error occurs.
        """
        req = uart_pb2.UartReadRequest(port=self._port, max_chunk_size=max_chunk_size)
        stream = self._stub.ListenUart(req, timeout=max(30.0, get_rpc_timeout()))
        for chunk in stream:
            _check_error(chunk, f"listen {self._port}")
            if chunk.data:
                yield chunk.data

    def listen_async(self, max_chunk_size: int = 256,
                     max_queue: int = 256) -> tuple[queue.Queue, threading.Event]:
        """Start a background thread that pushes received bytes into a queue.

        Opens the stream immediately — raises on failure before the thread starts.
        Returns a ``(queue, stop_event)`` pair. Read ``bytes`` chunks from the
        queue; the queue receives ``None`` when the stream ends. Set
        ``stop_event`` to stop the thread.

        Args:
            max_chunk_size: Maximum bytes per chunk returned by the server.
            max_queue: Maximum number of chunks buffered before dropping.

        Example::

            q, stop = port.listen_async()
            while (chunk := q.get()) is not None:
                process(chunk)
        """
        req = uart_pb2.UartReadRequest(port=self._port, max_chunk_size=max_chunk_size)
        stream = self._stub.ListenUart(req, timeout=max(30.0, get_rpc_timeout()))

        q: queue.Queue = queue.Queue(maxsize=max_queue)
        stop_event = threading.Event()

        def _worker() -> None:
            try:
                for chunk in stream:
                    if stop_event.is_set():
                        break
                    _check_error(chunk, f"listen {self._port}")
                    if chunk.data:
                        try:
                            q.put_nowait(chunk.data)
                        except queue.Full:
                            pass
            finally:
                q.put(None)

        threading.Thread(target=_worker, daemon=True).start()
        return q, stop_event
