"""WiFiManager: Wi-Fi client and access-point configuration."""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import List, Optional

import grpc

from api.common import types_pb2
from api.wifi_service.v26 import wifi_service_pb2 as wifi_pb2
from api.wifi_service.v26.wifi_service_pb2_grpc import WiFiServiceStub

from .config import get_rpc_timeout


class WiFiMode(IntEnum):
    UNKNOWN   = 0
    AP        = 1
    CLIENT    = 2
    AP_CLIENT = 3
    DISABLED  = 4


WIFI_MODE_UNKNOWN   = WiFiMode.UNKNOWN
WIFI_MODE_AP        = WiFiMode.AP
WIFI_MODE_CLIENT    = WiFiMode.CLIENT
WIFI_MODE_AP_CLIENT = WiFiMode.AP_CLIENT
WIFI_MODE_DISABLED  = WiFiMode.DISABLED


@dataclass
class WiFiInterface:
    interface_name: str
    state: int
    mac_address: str


@dataclass
class WiFiLinkProperties:
    interface_name: str
    state: int
    mac_address: str
    mtu: int
    ipv4_address: str
    ipv4_gateway: str
    ipv4_dns: List[str]
    mode: WiFiMode


@dataclass
class APProperties:
    """Current state of the software access point."""
    interface_name: str
    ssid: str
    security: str
    ipv4_address: str
    channel: int
    band: str
    hidden: bool
    active: bool
    connected_clients: int


@dataclass
class ClientProperties:
    """Current state of the Wi-Fi client association."""
    interface_name: str
    ssid: str
    security: str
    state: int
    ipv4_address: str
    ipv4_gateway: str
    ipv4_dns: List[str]
    signal_strength: int


@dataclass
class WiFiNetwork:
    """A network found during a scan."""
    ssid: str
    security: str
    signal_strength: int
    channel: int
    band: str


class WiFiManager:
    """Manage Wi-Fi interfaces — scan, connect as client, or run as AP."""

    def __init__(self, channel: grpc.Channel) -> None:
        self._stub = WiFiServiceStub(channel)

    def _call(self, method, *args):
        return method(*args, timeout=get_rpc_timeout())

    def list_wifi_interfaces(self) -> List[WiFiInterface]:
        """Return all discovered Wi-Fi interfaces."""
        resp = self._call(self._stub.ListWiFiInterfaces, types_pb2.Empty())
        return [
            WiFiInterface(
                interface_name=i.interface_name,
                state=i.state,
                mac_address=i.mac_address,
            )
            for i in resp.interfaces
        ]

    def is_wifi_connected(self, interface_name: str) -> bool:
        resp = self._call(self._stub.IsWiFiConnected, wifi_pb2.WiFiInterfaceRequest(interface_name=interface_name))
        return resp.value

    def get_wifi_link_properties(self, interface_name: str) -> Optional[WiFiLinkProperties]:
        resp = self._call(self._stub.GetWiFiLinkProperties, wifi_pb2.WiFiInterfaceRequest(interface_name=interface_name))
        if not resp.HasField("properties"):
            return None
        props = resp.properties
        cp = props.client_properties if props.HasField("client_properties") else None
        return WiFiLinkProperties(
            interface_name=props.interface_name,
            state=props.state,
            mac_address=props.mac_address,
            mtu=props.mtu,
            ipv4_address=cp.ipv4_address if cp else "",
            ipv4_gateway=cp.ipv4_gateway if cp else "",
            ipv4_dns=list(cp.ipv4_dns) if cp else [],
            mode=WiFiMode(props.mode),
        )

    def set_wifi_mode(self, interface_name: str, mode: WiFiMode) -> bool:
        """Set interface mode (client or AP)."""
        resp = self._call(self._stub.SetWiFiMode, wifi_pb2.SetWiFiModeRequest(interface_name=interface_name, mode=int(mode.value)))
        return resp.value

    def get_wifi_mode(self, interface_name: str) -> WiFiMode:
        resp = self._call(self._stub.GetWiFiMode, wifi_pb2.WiFiInterfaceRequest(interface_name=interface_name))
        return WiFiMode(resp.properties.mode) if resp.HasField("properties") else WiFiMode.UNKNOWN

    def set_ap_config(self, interface_name: str, ssid: str, password: str, security: str,
                      ipv4_address: str, channel: int, band: str, hidden: bool) -> bool:
        """Configure the software access point."""
        config = wifi_pb2.APConfig(
            interface_name=interface_name, ssid=ssid, password=password or "",
            security=security or "", ipv4_address=ipv4_address or "",
            channel=channel, band=band or "", hidden=hidden,
        )
        resp = self._call(self._stub.SetAPConfig, config)
        return resp.value

    def get_ap_properties(self, interface_name: str) -> Optional[APProperties]:
        resp = self._call(self._stub.GetAPProperties, wifi_pb2.WiFiInterfaceRequest(interface_name=interface_name))
        if not resp.HasField("properties"):
            return None
        props = resp.properties
        return APProperties(
            interface_name=props.interface_name,
            ssid=props.ssid,
            security=props.security,
            ipv4_address=props.ipv4_address,
            channel=props.channel,
            band=props.band,
            hidden=props.hidden,
            active=props.active,
            connected_clients=props.connected_clients,
        )

    def start_ap(self, interface_name: str) -> bool:
        """Start the software access point."""
        resp = self._call(self._stub.StartAP, wifi_pb2.WiFiInterfaceRequest(interface_name=interface_name))
        return resp.value

    def stop_ap(self, interface_name: str) -> bool:
        """Stop the software access point."""
        resp = self._call(self._stub.StopAP, wifi_pb2.WiFiInterfaceRequest(interface_name=interface_name))
        return resp.value

    def set_client_config(self, interface_name: str, ssid: str, password: str, security: str,
                          dhcp_enable: bool, ipv4_address: str, ipv4_gateway: str, ipv4_dns: List[str]) -> bool:
        """Configure the Wi-Fi client association and IP settings."""
        config = wifi_pb2.ClientConfig(
            interface_name=interface_name, ssid=ssid, password=password or "",
            security=security or "", dhcp_enable=dhcp_enable,
            ipv4_address=ipv4_address or "", ipv4_gateway=ipv4_gateway or "",
            ipv4_dns=ipv4_dns or [],
        )
        resp = self._call(self._stub.SetClientConfig, config)
        return resp.value

    def get_client_properties(self, interface_name: str) -> Optional[ClientProperties]:
        """Return the current Wi-Fi client association state."""
        resp = self._call(self._stub.GetClientProperties, wifi_pb2.WiFiInterfaceRequest(interface_name=interface_name))
        if not resp.HasField("properties"):
            return None
        props = resp.properties
        return ClientProperties(
            interface_name=props.interface_name,
            ssid=props.ssid,
            security=props.security,
            state=props.state,
            ipv4_address=props.ipv4_address,
            ipv4_gateway=props.ipv4_gateway,
            ipv4_dns=list(props.ipv4_dns),
            signal_strength=props.signal_strength,
        )

    def connect(self, interface_name: str) -> bool:
        """Initiate a connection to the configured SSID."""
        resp = self._call(self._stub.Connect, wifi_pb2.WiFiInterfaceRequest(interface_name=interface_name))
        return resp.value

    def disconnect(self, interface_name: str) -> bool:
        """Disconnect from the current SSID."""
        resp = self._call(self._stub.Disconnect, wifi_pb2.WiFiInterfaceRequest(interface_name=interface_name))
        return resp.value

    def scan_wifi(self, interface_name: str) -> List[WiFiNetwork]:
        """Perform a passive scan and return visible networks."""
        resp = self._call(self._stub.ScanWiFi, wifi_pb2.ScanWiFiRequest(interface_name=interface_name))
        return [
            WiFiNetwork(
                ssid=n.ssid,
                security=n.security,
                signal_strength=n.signal_strength,
                channel=n.channel,
                band=n.band,
            )
            for n in resp.networks
        ]

    # ── Short-name aliases ────────────────────────────────────────────────────

    def list_interfaces(self) -> List[WiFiInterface]:
        return self.list_wifi_interfaces()

    def get_link_properties(self, interface_name: str) -> Optional[WiFiLinkProperties]:
        return self.get_wifi_link_properties(interface_name)

    def is_connected(self, interface_name: str) -> bool:
        return self.is_wifi_connected(interface_name)

    def get_mode(self, interface_name: str) -> WiFiMode:
        return self.get_wifi_mode(interface_name)

    def set_mode_client(self, interface_name: str) -> bool:
        """Switch the interface to client (station) mode."""
        return self.set_wifi_mode(interface_name, WiFiMode.CLIENT)

    def scan(self, interface_name: str, force_rescan: bool = False) -> List[WiFiNetwork]:
        """Scan for visible networks. ``force_rescan`` is accepted for API parity with Go."""
        return self.scan_wifi(interface_name)
