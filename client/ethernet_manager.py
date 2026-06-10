"""EthernetManager: Ethernet interface configuration and link properties."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import grpc

from api.common import types_pb2
from api.ethernet_service.v26 import ethernet_service_pb2 as eth_pb2
from api.ethernet_service.v26.ethernet_service_pb2_grpc import EthernetServiceStub

from .config import get_rpc_timeout


@dataclass
class EthernetInterface:
    """Summary of a discovered Ethernet interface."""
    interface_name: str
    state: int
    mac_address: str


@dataclass
class EthernetLinkProperties:
    """Full link state and IP configuration for an Ethernet interface."""
    interface_name: str
    mac_address: str
    state: int
    mtu: int
    ipv4_address: str
    ipv4_gateway: str
    ipv4_dns: List[str]


class EthernetManager:
    """Manage Ethernet interfaces — list, query, and configure."""

    def __init__(self, channel: grpc.Channel) -> None:
        self._stub = EthernetServiceStub(channel)

    def _call(self, method, *args):
        return method(*args, timeout=get_rpc_timeout())

    def list_ethernet_interfaces(self) -> List[EthernetInterface]:
        """Return all discovered Ethernet interfaces."""
        resp = self._call(self._stub.ListEthernetInterfaces, types_pb2.Empty())
        return [
            EthernetInterface(
                interface_name=i.interface_name,
                state=i.state,
                mac_address=i.mac_address,
            )
            for i in resp.interfaces
        ]

    def is_ethernet_connected(self, interface_name: str) -> bool:
        """Return ``True`` if the interface has an active link."""
        resp = self._call(self._stub.IsEthernetConnected, eth_pb2.InterfaceRequest(interface_name=interface_name))
        return resp.value

    def get_ethernet_link_properties(self, interface_name: str) -> Optional[EthernetLinkProperties]:
        """Return full link properties, or ``None`` if unavailable."""
        resp = self._call(self._stub.GetEthernetLinkProperties, eth_pb2.InterfaceRequest(interface_name=interface_name))
        if not resp.HasField("properties"):
            return None
        props = resp.properties
        return EthernetLinkProperties(
            interface_name=props.interface_name,
            mac_address=props.mac_address,
            state=props.state,
            mtu=props.mtu,
            ipv4_address=props.ipv4_address,
            ipv4_gateway=props.ipv4_gateway,
            ipv4_dns=list(props.ipv4_dns),
        )

    def set_ethernet_config(self, interface_name: str, enable: bool = True, dhcp_enable: bool = True,
                            ipv4_address: str = "", ipv4_gateway: str = "", ipv4_dns: List[str] = None) -> bool:
        """Apply static or DHCP IP configuration to an interface."""
        config = eth_pb2.EthernetConfig(
            interface_name=interface_name, dhcp_enable=dhcp_enable,
            ipv4_address=ipv4_address or "", ipv4_gateway=ipv4_gateway or "",
            ipv4_dns=ipv4_dns or [],
        )
        resp = self._call(self._stub.SetEthernetConfig, config)
        return resp.value

    def enable_ethernet(self, interface_name: str) -> bool:
        """Enable an Ethernet interface."""
        resp = self._call(self._stub.EnableEthernet, eth_pb2.InterfaceRequest(interface_name=interface_name))
        return resp.value

    def disable_ethernet(self, interface_name: str) -> bool:
        """Disable an Ethernet interface."""
        resp = self._call(self._stub.DisableEthernet, eth_pb2.InterfaceRequest(interface_name=interface_name))
        return resp.value
