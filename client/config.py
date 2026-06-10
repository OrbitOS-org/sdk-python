"""SDK-wide RPC timeout configuration."""
_rpc_timeout: float = 10.0


def set_rpc_timeout(seconds: float) -> None:
    """Set the default gRPC call timeout (seconds). Minimum 1 s."""
    global _rpc_timeout
    _rpc_timeout = max(1.0, float(seconds))


def get_rpc_timeout() -> float:
    """Return the current default gRPC call timeout in seconds."""
    return _rpc_timeout
