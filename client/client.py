"""
OrbitOS SDK client.

Use :meth:`Client.connect` to connect to a device (auto-selects transport).
For explicit transport control use the other classmethods:

* ``Client.from_uds(socket_path)``        — Unix socket, no TLS (on-device)
* ``Client.from_tcp(host, port)``          — TCP insecure (development only)
* ``Client.from_tcp_tls(host, port)``      — TCP + TLS (remote connections)
* ``Client.connect(host)``                 — UDS first, TLS-TCP (requires certs)

Example::

    from client import Client, GpioPin

    with Client.connect("192.168.1.100") as c:
        print(c.system_manager.get_device_name())
        pin = GpioPin(number=26, chip_number=0)
        c.gpio_manager.set_level(pin, high=True)

Certs search order (``ca.crt`` required for TCP+TLS):

1. ``$ORBIT_GRPC_CERTS_DIR``
2. ``certs/grpc/`` next to the running executable / ``.pyz``
3. ``certs/grpc/`` two levels above this file (dev tree)
"""
from __future__ import annotations

import os
import socket
import ssl
import sys
import threading
from typing import Optional

import grpc

# Add generated stubs directory to sys.path so that grpc stubs can resolve
# "from common import types_pb2" style cross-imports without rewriting files.
_gen_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api"))
if _gen_path not in sys.path:
    sys.path.insert(0, _gen_path)

from .auth_manager import AuthManager
from .system_manager import SystemManager
from .ethernet_manager import EthernetManager
from .cellular_manager import CellularManager
from .wifi_manager import WiFiManager
from .power_manager import PowerManager
from .package_manager import PackageManager
from .sensor_manager import SensorManager
from .time_manager import TimeManager
from .development_manager import DevelopmentManager
from .firewall_manager import FirewallManager
from .bluetooth_manager import BluetoothManager
from .gpio_manager import GpioManager
from .pwm_manager import PwmManager
from .uart_manager import UartManager
from .i2c_manager import I2CManager
from .spi_manager import SpiManager
from .ai_manager import AIManager
from .app_hub_manager import AppHubManager
from .camera_manager import CameraManager
from .event_manager import EventManager
from .update_manager import UpdateManager
from .vpn_manager import VPNManager

_UNIX_SOCKET = "/run/gravity/ipc/system_server.sock"
_TCP_PORT = 6000
_MAX_MSG = 64 * 1024 * 1024  # 64 MiB — matches Go SDK
_CHANNEL_OPTIONS = [
    ("grpc.max_send_message_length", _MAX_MSG),
    ("grpc.max_receive_message_length", _MAX_MSG),
]


def _default_certs_dir() -> str:
    """Return the best available certs/grpc/ directory.

    Search order mirrors the Go SDK (walks up from executable/cwd):
    1. $ORBIT_GRPC_CERTS_DIR env var
    2. next to the running .pyz / argv[0] (shiv deployments)
    3. two levels above __file__ (dev source tree)
    """
    env = os.environ.get("ORBIT_GRPC_CERTS_DIR", "").strip()
    if env:
        return env

    candidates = [
        # argv[0] is the .pyz path when running via shiv
        os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "certs", "grpc"),
        # dev source tree: client/ → sdk/ → workspace/
        os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")), "certs", "grpc"),
    ]
    for path in candidates:
        if os.path.isfile(os.path.join(path, "ca.crt")):
            return path
    return candidates[0]


def _make_tls_ctx(certs_dir: str) -> ssl.SSLContext:
    """Build an ssl.SSLContext that verifies the CA chain but not the hostname.

    Mirrors the Go SDK's InsecureSkipVerify=true + VerifyPeerCertificate approach:
    the server cert (CN-only, no SANs) is accepted as long as it is signed by the
    trusted CA.  grpc-python's BoringSSL rejects such certs, so TLS is handled
    entirely at the Python ssl layer via a local loopback proxy.
    """
    ca_path = os.path.join(certs_dir, "ca.crt")
    if not os.path.isfile(ca_path):
        raise FileNotFoundError(f"CA certificate not found: {ca_path}")
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.load_verify_locations(ca_path)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.set_alpn_protocols(["h2"])
    cert_path = os.path.join(certs_dir, "client.crt")
    key_path = os.path.join(certs_dir, "client.key")
    if os.path.isfile(cert_path) and os.path.isfile(key_path):
        ctx.load_cert_chain(cert_path, key_path)
    return ctx


def _fwd(src: socket.socket, dst: socket.socket) -> None:
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except Exception:
        pass
    finally:
        for s in (src, dst):
            try:
                s.close()
            except Exception:
                pass


def _ssl_proxy_channel(host: str, port: int, ssl_ctx: ssl.SSLContext,
                        options: list) -> grpc.Channel:
    """Route a gRPC channel through a local loopback proxy that handles TLS.

    gRPC connects to 127.0.0.1:<random-port> (insecure); the proxy forwards
    each connection to the device over a real TLS socket using Python's ssl
    module (check_hostname=False, verify CA chain).  This replicates the Go
    SDK's behaviour for CN-only server certs that grpc-python/BoringSSL refuses.
    """
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    local_port = srv.getsockname()[1]
    srv.listen(10)

    def _handle(client_sock: socket.socket) -> None:
        try:
            raw = socket.create_connection((host, port), timeout=15)
            remote = ssl_ctx.wrap_socket(raw, server_hostname=None)
            t1 = threading.Thread(target=_fwd, args=(client_sock, remote), daemon=True)
            t2 = threading.Thread(target=_fwd, args=(remote, client_sock), daemon=True)
            t1.start()
            t2.start()
        except Exception:
            try:
                client_sock.close()
            except Exception:
                pass

    def _accept_loop() -> None:
        while True:
            try:
                client_sock, _ = srv.accept()
                threading.Thread(target=_handle, args=(client_sock,), daemon=True).start()
            except OSError:
                break

    threading.Thread(target=_accept_loop, daemon=True, name="orbit-tls-proxy").start()
    return grpc.insecure_channel(f"127.0.0.1:{local_port}", options=options)


class Client:
    """
    Main SDK client. Holds one manager per Gravity service.

    Obtain via :meth:`connect` (recommended) or the other classmethods for
    explicit transport control.

    Attributes:
        system_manager: Device identity, OS info, metrics.
        ethernet_manager: Ethernet interface configuration.
        cellular_manager: Cellular / LTE interface management.
        wifi_manager: Wi-Fi client and access-point configuration.
        power_manager: Reboot and shutdown.
        package_manager: App installation and removal.
        sensor_manager: Sensor capability discovery and event streaming.
        time_manager: System time and NTP configuration.
        development_manager: Remote log streaming.
        firewall_manager: Firewall zones and rules.
        bluetooth_manager: Classic BT and BLE operations.
        gpio_manager: GPIO digital I/O.
        pwm_manager: PWM channel control.
        uart_manager: UART port operations.
        i2c_manager: I2C bus read/write.
        spi_manager: SPI device transfer.
        ai_manager: On-device ML model loading and inference.
        app_hub_manager: HTTP service registration on the device portal.
        camera_manager: Camera capture and frame streaming.
        event_manager: System-wide event subscription.
        update_manager: OTA firmware update and factory reset.
        vpn_manager: WireGuard / OpenVPN profile management.
    """

    def __init__(self, channel: grpc.Channel) -> None:
        self._channel = channel
        self.auth_manager = AuthManager(channel)
        self.system_manager = SystemManager(channel)
        self.ethernet_manager = EthernetManager(channel)
        self.cellular_manager = CellularManager(channel)
        self.wifi_manager = WiFiManager(channel)
        self.power_manager = PowerManager(channel)
        self.package_manager = PackageManager(channel)
        self.sensor_manager = SensorManager(channel)
        self.time_manager = TimeManager(channel)
        self.development_manager = DevelopmentManager(channel)
        self.firewall_manager = FirewallManager(channel)
        self.bluetooth_manager = BluetoothManager(channel)
        self.gpio_manager = GpioManager(channel)
        self.pwm_manager = PwmManager(channel)
        self.uart_manager = UartManager(channel)
        self.i2c_manager = I2CManager(channel)
        self.spi_manager = SpiManager(channel)
        self.ai_manager = AIManager(channel)
        self.app_hub_manager = AppHubManager(channel)
        self.camera_manager = CameraManager(channel)
        self.event_manager = EventManager(channel)
        self.update_manager = UpdateManager(channel)
        self.vpn_manager = VPNManager(channel)

    # ── Alternative constructors ───────────────────────────────────────────────

    @classmethod
    def connect(cls, host: str = "", certs_dir: Optional[str] = None) -> "Client":
        """Connect using the best available transport.

        On-device (Unix socket present): uses UDS with no TLS.
        Remote (no socket): uses TCP + TLS (requires ``certs/grpc/ca.crt``).

        Args:
            host: Device IP address or hostname. Ignored when connecting via UDS.
            certs_dir: Override the TLS certs directory. Defaults to auto-discovery.

        Raises:
            FileNotFoundError: if the socket is absent and no CA cert can be found.
        """
        if os.path.exists(_UNIX_SOCKET):
            return cls.from_uds(_UNIX_SOCKET)
        return cls.from_tcp_tls(host, _TCP_PORT, certs_dir=certs_dir)

    @classmethod
    def from_uds(cls, socket_path: str = _UNIX_SOCKET) -> "Client":
        """Connect via Unix domain socket (on-device, no TLS).

        Args:
            socket_path: Path to the system server socket.
        """
        channel = grpc.insecure_channel(f"unix://{socket_path}", options=_CHANNEL_OPTIONS)
        return cls(channel)

    @classmethod
    def from_tcp(cls, host: str, port: int = _TCP_PORT) -> "Client":
        """Connect via TCP without TLS (development only).

        Args:
            host: Device IP address or hostname.
            port: gRPC port (default 6000).
        """
        channel = grpc.insecure_channel(f"{host}:{port}", options=_CHANNEL_OPTIONS)
        return cls(channel)

    @classmethod
    def from_tcp_tls(
        cls,
        host: str,
        port: int = _TCP_PORT,
        certs_dir: Optional[str] = None,
    ) -> "Client":
        """Connect via TCP with mutual TLS.

        Uses Python's ssl module (check_hostname=False, verify CA chain) routed
        through a local loopback proxy.  This matches the Go SDK's behaviour for
        server certs that have a CN but no Subject Alternative Names.

        Args:
            host: Device IP address or hostname.
            port: gRPC port (default 6000).
            certs_dir: Directory containing ``ca.crt`` and optionally
                ``client.crt`` + ``client.key``. Defaults to ``certs/grpc/``
                two levels above this file.
        """
        certs_dir = certs_dir or _default_certs_dir()
        ssl_ctx = _make_tls_ctx(certs_dir)
        channel = _ssl_proxy_channel(host, port, ssl_ctx, _CHANNEL_OPTIONS)
        return cls(channel)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the underlying gRPC channel."""
        self._channel.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *_) -> None:
        self.close()
