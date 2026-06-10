"""VPNManager: WireGuard and OpenVPN profile management."""
from __future__ import annotations

from typing import Generator

import grpc

from api.common import types_pb2
from api.vpn_service.v26 import vpn_service_pb2 as vpn_pb2
from api.vpn_service.v26.vpn_service_pb2_grpc import VPNServiceStub

from .config import get_rpc_timeout

# Re-export proto constants for convenience
VPN_PROVIDER_WIREGUARD = vpn_pb2.VPN_PROVIDER_WIREGUARD
VPN_PROVIDER_OPENVPN = vpn_pb2.VPN_PROVIDER_OPENVPN
TUNNEL_STATE_UP = vpn_pb2.TUNNEL_STATE_UP
TUNNEL_STATE_DOWN = vpn_pb2.TUNNEL_STATE_DOWN


class VPNManager:
    """Manage WireGuard and OpenVPN profiles, connect, and watch tunnel events."""

    def __init__(self, channel: grpc.Channel) -> None:
        self._stub = VPNServiceStub(channel)

    def _call(self, method, *args):
        return method(*args, timeout=get_rpc_timeout())

    def get_capabilities(self):
        """Return the VPN providers supported by this device."""
        return self._call(self._stub.GetCapabilities, types_pb2.Empty())

    def list_profiles(self):
        """Return all configured VPN profiles."""
        return self._call(self._stub.ListProfiles, types_pb2.Empty())

    def apply_profile(self, profile_id: str, display_name: str, provider: int,
                      config_data: bytes, auto_connect: bool = False, connect_after_apply: bool = False):
        """Create or update a VPN profile from raw config data.

        Args:
            profile_id: Unique profile identifier.
            display_name: Human-readable profile name.
            provider: ``VPN_PROVIDER_WIREGUARD`` or ``VPN_PROVIDER_OPENVPN``.
            config_data: Raw WireGuard ``.conf`` or OpenVPN ``.ovpn`` bytes.
            auto_connect: Reconnect automatically after reboots.
            connect_after_apply: Start the tunnel immediately after applying.
        """
        profile = vpn_pb2.VpnProfile(
            profile_id=profile_id, display_name=display_name,
            provider=provider, config_data=config_data, auto_connect=auto_connect,
        )
        req = vpn_pb2.ApplyProfileRequest(profile=profile, connect_after_apply=connect_after_apply)
        return self._call(self._stub.ApplyProfile, req)

    def remove_profile(self, profile_id: str):
        """Delete a VPN profile."""
        return self._call(self._stub.RemoveProfile, vpn_pb2.VpnProfileRequest(profile_id=profile_id))

    def connect(self, profile_id: str):
        """Bring up the tunnel for a profile."""
        return self._call(self._stub.Connect, vpn_pb2.VpnProfileRequest(profile_id=profile_id))

    def disconnect(self, profile_id: str):
        """Tear down the tunnel for a profile."""
        return self._call(self._stub.Disconnect, vpn_pb2.VpnProfileRequest(profile_id=profile_id))

    def get_status(self):
        """Return the current tunnel session status."""
        return self._call(self._stub.GetStatus, types_pb2.Empty())

    def list_sessions(self):
        """Return all active VPN sessions."""
        return self._call(self._stub.ListSessions, types_pb2.Empty())

    def apply_wireguard(self, display_name: str, config_data: bytes, auto_connect: bool = False):
        """Create or update a WireGuard profile from a ``.conf`` file."""
        return self.apply_profile("", display_name, VPN_PROVIDER_WIREGUARD, config_data, auto_connect)

    def apply_openvpn(self, display_name: str, config_data: bytes, auto_connect: bool = False):
        """Create or update an OpenVPN profile from an ``.ovpn`` file."""
        return self.apply_profile("", display_name, VPN_PROVIDER_OPENVPN, config_data, auto_connect)

    def is_connected(self) -> bool:
        """Return ``True`` if a VPN tunnel is currently active."""
        resp = self.get_status()
        return any(s.state == TUNNEL_STATE_UP for s in resp.sessions)

    def watch_events(self, profile_id: str = "", timeout: float | None = None) -> Generator:
        """Stream ``VPNEvent`` messages for a profile's tunnel state changes.

        Args:
            profile_id: Filter to a specific profile (empty = all profiles).
            timeout: Stream idle timeout.

        Example::

            for event in client.vpn_manager.watch_events(profile_id="wg0"):
                if event.state == TUNNEL_STATE_UP:
                    print("VPN connected")
        """
        req = vpn_pb2.WatchEventsRequest(profile_id=profile_id)
        stream = self._stub.WatchEvents(req, timeout=timeout)
        try:
            for event in stream:
                yield event
        finally:
            stream.cancel()
