"""AuthManager: local device authentication via Gravity."""
from __future__ import annotations

import grpc

from api.auth_service.v26 import auth_service_pb2 as auth_pb2
from api.auth_service.v26.auth_service_pb2_grpc import AuthServiceStub

from .config import get_rpc_timeout


class AuthManager:
    """Authenticate users against the Gravity runtime."""

    def __init__(self, channel: grpc.Channel) -> None:
        self._stub = AuthServiceStub(channel)

    def login(self, username: str, password: str) -> tuple[str, int]:
        """Authenticate with username and password.

        Returns:
            Tuple of (session_token, expires_at) where expires_at is a Unix timestamp.

        Raises:
            RuntimeError: if authentication fails.
        """
        resp = self._stub.Login(
            auth_pb2.LoginRequest(username=username, password=password),
            timeout=get_rpc_timeout(),
        )
        if resp.error.message:
            raise RuntimeError(resp.error.message)
        return resp.token, resp.expires_at

    def logout(self, token: str) -> None:
        """Invalidate a session token.

        Raises:
            RuntimeError: if logout fails.
        """
        resp = self._stub.Logout(
            auth_pb2.LogoutRequest(token=token),
            timeout=get_rpc_timeout(),
        )
        if resp.error.message:
            raise RuntimeError(resp.error.message)
        if not resp.success:
            raise RuntimeError("logout failed")
