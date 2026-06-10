"""AppHubManager: HTTP service registration on the device portal."""
from __future__ import annotations

from typing import Generator, List, Optional

import grpc

from api.common import types_pb2
from api.app_hub_service.v26 import app_hub_service_pb2 as hub_pb2
from api.app_hub_service.v26.app_hub_service_pb2_grpc import AppHubServiceStub

from .config import get_rpc_timeout


class AppHubManager:
    """Register an app's HTTP service so it appears on the device web portal.

    The device portal proxies inbound requests to registered services based on
    the configured routes.
    """

    def __init__(self, channel: grpc.Channel) -> None:
        self._stub = AppHubServiceStub(channel)

    def _call(self, method, *args):
        return method(*args, timeout=get_rpc_timeout())

    def register_service(self, host: str, port: int, routes: Optional[List[str]] = None,
                         health_endpoint: str = "/health", exposure_mode: int = 0):
        """Register this app's HTTP service with the portal.

        Args:
            host: Service listen address (usually ``"127.0.0.1"``).
            port: Service listen port.
            routes: URL path prefixes to proxy (e.g. ``["/api", "/ui"]``).
            health_endpoint: Health-check path polled by the portal.
            exposure_mode: Portal exposure level (``hub_pb2.EXPOSURE_*``).
        """
        route_msgs = [hub_pb2.Route(path=p) for p in (routes or [])]
        health = hub_pb2.HealthCheck(type=hub_pb2.HEALTH_CHECK_HTTP, endpoint=health_endpoint)
        req = hub_pb2.RegisterServiceRequest(
            host=host, port=port, routes=route_msgs,
            health=health, exposure_mode=exposure_mode,
        )
        return self._call(self._stub.RegisterService, req)

    def unregister_service(self):
        """Remove this app's service registration."""
        return self._call(self._stub.UnregisterService, types_pb2.Empty())

    def get_service(self, service_id: str):
        """Return the registration details for a service by ID."""
        return self._call(self._stub.GetService, hub_pb2.ServiceIdRequest(service_id=service_id))

    def list_services(self):
        """Return all registered services on the portal."""
        return self._call(self._stub.ListServices, types_pb2.Empty())

    def add_route(self, path: str):
        """Add a URL path prefix to this service's routing table."""
        return self._call(self._stub.AddRoute, hub_pb2.AddRouteRequest(route=hub_pb2.Route(path=path)))

    def remove_route(self, path: str):
        """Remove a URL path prefix from this service's routing table."""
        return self._call(self._stub.RemoveRoute, hub_pb2.RemoveRouteRequest(path=path))

    def get_routing_table(self):
        """Return the full portal routing table."""
        return self._call(self._stub.GetRoutingTable, types_pb2.Empty())

    def register_web_ui(self, addr: str, route: str):
        """Register a web UI service from an ``host:port`` address string.

        Args:
            addr: Service address in ``"host:port"`` format.
            route: URL path prefix to proxy (e.g. ``"/ui"``).
        """
        host, port_str = addr.rsplit(":", 1)
        health = hub_pb2.HealthCheck(type=hub_pb2.HEALTH_CHECK_TCP)
        req = hub_pb2.RegisterServiceRequest(
            host=host or "127.0.0.1", port=int(port_str),
            routes=[hub_pb2.Route(path=route)],
            health=health,
        )
        return self._call(self._stub.RegisterService, req)

    def watch_services(self, timeout: float | None = None) -> Generator:
        """Stream ``ServiceEvent`` messages as services register or deregister.

        Example::

            for event in client.app_hub_manager.watch_services():
                print(event.service_id, event.type)
        """
        stream = self._stub.WatchServices(types_pb2.Empty(), timeout=timeout)
        try:
            for event in stream:
                yield event
        finally:
            stream.cancel()
