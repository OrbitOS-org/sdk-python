"""CellularManager: cellular / LTE interface management."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional

import grpc

from api.common import types_pb2
from api.cellular_service.v26 import cellular_service_pb2 as cell_pb2
from api.cellular_service.v26.cellular_service_pb2_grpc import CellularServiceStub

from .config import get_rpc_timeout


@dataclass
class CellularInterface:
    """Summary of a discovered cellular interface."""
    interface_name: str
    mac_address: str
    mtu: int
    ipv4_address: str
    ipv4_gateway: str
    ipv4_dns: List[str]


@dataclass
class CellularLinkProperties:
    """Full link state and modem details for a cellular interface."""
    interface_name: str
    mac_address: str
    mtu: int
    ipv4_address: str
    ipv4_gateway: str
    ipv4_dns: List[str]
    three_gpp: Optional[Any] = None
    modem_generic: Optional[Any] = None
    sim_info: Optional[Any] = None


class CellularManager:
    """Manage cellular interfaces — list, query, connect, and configure APN."""

    def __init__(self, channel: grpc.Channel) -> None:
        self._stub = CellularServiceStub(channel)

    def _call(self, method, *args):
        return method(*args, timeout=get_rpc_timeout())

    def list_cellular_interfaces(self) -> List[CellularInterface]:
        """Return all discovered cellular interfaces."""
        resp = self._call(self._stub.ListCellularInterfaces, types_pb2.Empty())
        return [
            CellularInterface(
                interface_name=i.interface_name,
                mac_address=i.mac_address,
                mtu=i.mtu,
                ipv4_address=i.ipv4_address,
                ipv4_gateway=i.ipv4_gateway,
                ipv4_dns=list(i.ipv4_dns),
            )
            for i in resp.interfaces
        ]

    def is_cellular_connected(self, interface_name: str) -> bool:
        """Return ``True`` if the modem has an active data session."""
        resp = self._call(self._stub.IsCellularConnected, cell_pb2.CellularInterfaceRequest(interface_name=interface_name))
        return resp.value

    def get_cellular_link_properties(self, interface_name: str) -> Optional[CellularLinkProperties]:
        """Return full modem and IP properties, or ``None`` if unavailable."""
        resp = self._call(self._stub.GetCellularLinkProperties, cell_pb2.CellularInterfaceRequest(interface_name=interface_name))
        if not resp.HasField("properties"):
            return None
        props = resp.properties
        return CellularLinkProperties(
            interface_name=props.interface_name,
            mac_address=props.mac_address,
            mtu=props.mtu,
            ipv4_address=props.ipv4_address,
            ipv4_gateway=props.ipv4_gateway,
            ipv4_dns=list(props.ipv4_dns),
            three_gpp=props.three_gpp if props.HasField("three_gpp") else None,
            modem_generic=props.modem_generic if props.HasField("modem_generic") else None,
            sim_info=props.sim_info if props.HasField("sim_info") else None,
        )

    def set_cellular_config(self, interface_name: str, dhcp_enable: bool,
                            ipv4_address: str, ipv4_gateway: str, ipv4_dns: List[str]) -> bool:
        """Apply IP configuration (static or DHCP) for the data session."""
        config = cell_pb2.CellularConfig(
            interface_name=interface_name, dhcp_enable=dhcp_enable,
            ipv4_address=ipv4_address or "", ipv4_gateway=ipv4_gateway or "",
            ipv4_dns=ipv4_dns or [],
        )
        resp = self._call(self._stub.SetCellularConfig, config)
        return resp.value

    def connect(self, interface_name: str) -> bool:
        """Start a cellular data session."""
        resp = self._call(self._stub.Connect, cell_pb2.CellularInterfaceRequest(interface_name=interface_name))
        return resp.value

    def disconnect(self, interface_name: str) -> bool:
        """Tear down the cellular data session."""
        resp = self._call(self._stub.Disconnect, cell_pb2.CellularInterfaceRequest(interface_name=interface_name))
        return resp.value
