"""FirewallManager: firewall zone and rule management."""
from __future__ import annotations

from enum import IntEnum
from typing import List

import grpc

from api.common import types_pb2
from api.firewall_service.v26 import firewall_service_pb2 as fw_pb2
from api.firewall_service.v26.firewall_service_pb2_grpc import FirewallServiceStub

from .config import get_rpc_timeout


class ZonePolicy(IntEnum):
    ACCEPT = 0
    DROP   = 1
    REJECT = 2


class FirewallProtocol(IntEnum):
    ANY  = 0
    TCP  = 1
    UDP  = 2
    ICMP = 3


POLICY_ACCEPT = ZonePolicy.ACCEPT
POLICY_DROP   = ZonePolicy.DROP
POLICY_REJECT = ZonePolicy.REJECT
PROTO_ANY     = FirewallProtocol.ANY
PROTO_TCP     = FirewallProtocol.TCP
PROTO_UDP     = FirewallProtocol.UDP
PROTO_ICMP    = FirewallProtocol.ICMP


class FirewallManager:
    """Manage iptables-backed zones and forwarding rules."""

    def __init__(self, channel: grpc.Channel) -> None:
        self._stub = FirewallServiceStub(channel)

    def _call(self, method, *args):
        return method(*args, timeout=get_rpc_timeout())

    def list_zones(self):
        """Return all configured firewall zones."""
        return self._call(self._stub.ListZones, types_pb2.Empty())

    def add_zone(self, name: str, interfaces: List[str],
                 input_policy: ZonePolicy = ZonePolicy.ACCEPT,
                 output_policy: ZonePolicy = ZonePolicy.ACCEPT,
                 masquerade: bool = False):
        """Create a new firewall zone.

        Args:
            name: Unique zone name.
            interfaces: Network interfaces assigned to this zone.
            input_policy: Default inbound policy.
            output_policy: Default outbound policy.
            masquerade: Enable NAT masquerading for this zone.
        """
        req = fw_pb2.ZoneRequest(
            name=name or "", interfaces=interfaces or [],
            input_policy=input_policy, output_policy=output_policy, masquerade=masquerade,
        )
        return self._call(self._stub.AddZone, req)

    def remove_zone(self, name: str):
        """Delete a firewall zone by name."""
        return self._call(self._stub.RemoveZone, fw_pb2.ZoneNameRequest(name=name or ""))

    def list_rules(self):
        """Return all configured forwarding rules."""
        return self._call(self._stub.ListRules, types_pb2.Empty())

    def add_rule(self, src_zone: str, dst_zone: str, protocol: FirewallProtocol,
                 src_ip: str, dest_port: int, action: ZonePolicy,
                 comment: str = "") -> bool:
        """Add a forwarding rule.

        Args:
            src_zone: Source zone name.
            dst_zone: Destination zone name.
            protocol: Protocol filter.
            src_ip: Source IP filter (empty = any).
            dest_port: Destination port (0 = any).
            action: Policy applied to matching traffic.
            comment: Optional human-readable description.
        """
        req = fw_pb2.FirewallRuleRequest(
            src_zone=src_zone or "", dst_zone=dst_zone or "",
            protocol=protocol, src_ip=src_ip or "",
            dest_port=dest_port, action=action, comment=comment or "",
        )
        resp = self._call(self._stub.AddRule, req)
        return resp.value

    def remove_rule(self, rule_id: str):
        """Remove a forwarding rule by its ID."""
        return self._call(self._stub.RemoveRule, fw_pb2.FirewallRuleIdRequest(rule_id=rule_id or ""))

    def flush_rules(self):
        """Remove all forwarding rules."""
        return self._call(self._stub.FlushRules, types_pb2.Empty())

    def apply_firewall(self) -> bool:
        """Commit all pending zone and rule changes to the kernel."""
        resp = self._call(self._stub.ApplyFirewall, types_pb2.Empty())
        return resp.value
