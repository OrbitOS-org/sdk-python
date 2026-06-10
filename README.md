# OrbitOS Python SDK

Python SDK for the OrbitOS Gravity system server.

## Directory layout

```
orbit-os-sdk-python/
├── api/            ← gRPC stubs (pre-generated)
├── client/         ← all managers + Client + config
├── logger/         ← structured logger (stdout + logd socket)
└── metadata/       ← app metadata and build-info helpers
```

## Installation

```bash
pip install grpcio>=1.62.0 protobuf>=4.25.0
pip install -e .
```

TLS certificates (`ca.crt`, optional `client.crt` + `client.key`) go in `certs/grpc/`.

---

## Quick start

```python
from client import Client
from client.gpio_manager import GpioPin, GpioDirection, GpioLevel

# Auto: Unix socket when running on-device, TCP+TLS otherwise
with Client.connect("192.168.1.100") as c:

    # System info
    print(c.system_manager.get_device_name())
    print(c.system_manager.get_os_version())
    version, revision = c.system_manager.get_api_version()

    # GPIO
    pin = GpioPin(number=26, chip_number=0)
    c.gpio_manager.set_direction(pin, GpioDirection.OUT)
    c.gpio_manager.set_level(pin, GpioLevel.HIGH)

    # I2C
    buses = c.i2c_manager.list_buses()
    data = c.i2c_manager.read(bus=1, addr=0x48, n=2)

    # Event streaming
    for event in c.event_manager.subscribe():
        print(event.type, event.payload)
        break  # cancel stream by leaving the loop
```

---

## Connection constructors

| Constructor | Transport | TLS | Typical use |
|---|---|---|---|
| `Client.from_uds(socket_path)` | Unix socket | No | On-device apps |
| `Client.from_tcp(host, port)` | TCP | No | Local development |
| `Client.from_tcp_tls(host, port)` | TCP | Yes | Remote connections |
| `Client.connect(host)` | UDS → TCP+TLS | Optional | Portable apps |

---

## API reference

### SystemManager

#### Device identity

```python
c.system_manager.get_api_version()       # → (version: int, revision: int)
c.system_manager.get_device_name()       # → str
c.system_manager.get_architecture()      # → str
c.system_manager.get_soc_model()         # → str
c.system_manager.get_soc_vendor()        # → str
c.system_manager.get_board_model()       # → str
c.system_manager.get_board_vendor()      # → str
c.system_manager.get_hardware_version()  # → str
c.system_manager.get_hardware_model()    # → str
c.system_manager.get_system_uuid()       # → str
c.system_manager.get_board_serial()      # → str
c.system_manager.get_cpu_serial()        # → str
c.system_manager.get_machine_id()        # → str
```

#### CPU & memory

```python
c.system_manager.get_cpu_model()    # → str
c.system_manager.get_cpu_cores()    # → int
c.system_manager.get_cpu_threads()  # → int
c.system_manager.get_cpu_min_mhz()  # → float
c.system_manager.get_cpu_max_mhz()  # → float
c.system_manager.get_total_ram()    # → int  (bytes)
c.system_manager.get_metrics()      # → MetricsInfoResponse proto (CPU/RAM/disk usage)
```

#### OS & runtime

```python
c.system_manager.get_os_name()             # → str
c.system_manager.get_os_version()          # → str
c.system_manager.get_os_revision()         # → str
c.system_manager.get_runtime_version()     # → str
c.system_manager.get_runtime_build_date()  # → str
c.system_manager.get_distro()              # → str
c.system_manager.get_distro_version()      # → str
c.system_manager.get_kernel_version()      # → str
```

#### Feature toggles

```python
c.system_manager.enable_dev_mode()              # → bool
c.system_manager.disable_dev_mode()             # → bool
c.system_manager.is_dev_mode_enabled()          # → bool
c.system_manager.enable_ssh_server()            # → bool
c.system_manager.disable_ssh_server()           # → bool
c.system_manager.is_ssh_server_enabled()        # → bool
c.system_manager.enable_reboot_on_failure()     # → bool
c.system_manager.disable_reboot_on_failure()    # → bool
c.system_manager.is_reboot_on_failure_enabled() # → bool
c.system_manager.allow_untrusted_apps()         # → bool
c.system_manager.disallow_untrusted_apps()      # → bool
c.system_manager.is_untrusted_apps_allowed()    # → bool
```

### EthernetManager

```python
c.ethernet_manager.list_ethernet_interfaces()
c.ethernet_manager.is_ethernet_connected("eth0")              # → bool
c.ethernet_manager.get_ethernet_link_properties("eth0")
c.ethernet_manager.set_ethernet_config("eth0", dhcp_enable=True, ...)
```

### CellularManager

```python
c.cellular_manager.list_cellular_interfaces()
c.cellular_manager.is_cellular_connected("wwan0")  # → bool
c.cellular_manager.connect("wwan0")                # → bool
c.cellular_manager.disconnect("wwan0")             # → bool
```

### WiFiManager

```python
from client.wifi_manager import WiFiMode

c.wifi_manager.list_wifi_interfaces()
c.wifi_manager.scan_wifi("wlan0")
c.wifi_manager.set_client_config("wlan0", ssid="MyNet", password="secret", ...)
c.wifi_manager.connect("wlan0")                    # → bool
c.wifi_manager.set_ap_config("wlan0", ssid="HotSpot", ...)
c.wifi_manager.start_ap("wlan0")                   # → bool
c.wifi_manager.set_wifi_mode("wlan0", WiFiMode.CLIENT)
```

### PowerManager

```python
c.power_manager.reboot(force=False, reason="update")
c.power_manager.shutdown(force=False)
```

### PackageManager

```python
packages = c.package_manager.get_installed_packages()
c.package_manager.remove_package("myapp")          # → bool
```

### GpioManager

```python
from client.gpio_manager import GpioPin, GpioDirection, GpioLevel
from client.gpio_manager import GPIO_DIR_OUT, GPIO_DIR_IN, GPIO_LEVEL_HIGH, GPIO_LEVEL_LOW

pin = GpioPin(number=26, chip_number=0)
c.gpio_manager.list_pins()                         # → List[GpioPin]
c.gpio_manager.set_direction(pin, GpioDirection.OUT)
c.gpio_manager.get_direction(pin)                  # → GpioDirection
c.gpio_manager.set_level(pin, GpioLevel.HIGH)
c.gpio_manager.get_level(pin)                      # → GpioLevel
```

### PwmManager

```python
from client.pwm_manager import PwmChannel

channels = c.pwm_manager.list_channels()                                # → List[PwmChannel]
props    = c.pwm_manager.get_properties(channels[0])                    # → PwmProperties
c.pwm_manager.set_pwm(channels[0], duty_cycle=0.5, frequency_hz=1000.0)
c.pwm_manager.stop_pwm(channels[0])
```

### I2CManager

```python
from client.i2c_manager import I2CConfig

buses  = c.i2c_manager.list_buses()                                     # → List[int]
addrs  = c.i2c_manager.scan_bus(bus=1)                                  # → List[int]
cfg    = c.i2c_manager.get_config(bus=1)                                # → I2CConfig
c.i2c_manager.set_config(I2CConfig(bus=1, clock_hz=400_000))
data   = c.i2c_manager.read(bus=1, addr=0x48, n=2)                     # → bytes
c.i2c_manager.write(bus=1, addr=0x3C, data=b'\x00\x01')
result = c.i2c_manager.write_read(bus=1, addr=0x48, write_data=b'\x00', read_len=2)
```

### SpiManager

```python
from client.spi_manager import SpiConfig

c.spi_manager.set_config(SpiConfig(bus=0, chip_select=0, max_speed_hz=1_000_000, bits_per_word=8))
rx = c.spi_manager.transfer(bus=0, chip_select=0, data_out=b'\xAB\xCD', read_length=2)
```

### UartManager

```python
from client.uart_manager import UartConfig, UartParity, UartFlowControl

ports = c.uart_manager.list_ports()                                     # → List[str]
port  = c.uart_manager.open(UartConfig(port="/dev/ttyS0", baudrate=115200, data_bits=8))
port.write(b"AT\r\n")
for chunk in port.listen():
    print(chunk)
port.close()
```

### AIManager

```python
c.ai_manager.upload_and_load_model("face", "/data/face.onnx", backend=c.ai_manager.ONNX)
resp = c.ai_manager.infer("face", input_data=tensor_bytes, input_shape=[1, 3, 224, 224])
```

### CameraManager

```python
devices = c.camera_manager.list_devices()                              # → List[CameraDeviceInfo]
info    = c.camera_manager.get_device_info("/dev/video0")
c.camera_manager.lock_camera("/dev/video0", client_id="myapp")         # → bool

img = c.camera_manager.capture_image("/dev/video0", width=1280, height=720)
open("frame.jpg", "wb").write(img.image_data)

for frame in c.camera_manager.stream_frames("/dev/video0", fps=30):
    process(frame)
    if done:
        break

c.camera_manager.unlock_camera("/dev/video0", client_id="myapp")       # → bool
```

### EventManager

```python
from client.event_manager import EVENT_APP_CRASHED, EVENT_NET_DOWN

for event in c.event_manager.subscribe(EVENT_APP_CRASHED, EVENT_NET_DOWN):
    handle(event)
    if done:
        break  # cancels the stream
```

### VPNManager

```python
from client.vpn_manager import VPN_PROVIDER_WIREGUARD, VPN_PROVIDER_OPENVPN

# Apply a profile
c.vpn_manager.apply_profile("wg0", "Office VPN", VPN_PROVIDER_WIREGUARD,
                             open("wg0.conf", "rb").read(), connect_after_apply=True)

# Convenience helpers
c.vpn_manager.apply_wireguard("Office VPN", open("wg0.conf", "rb").read())
c.vpn_manager.apply_openvpn("Corp VPN",     open("corp.ovpn", "rb").read())

# Status
profiles  = c.vpn_manager.list_profiles()
status    = c.vpn_manager.get_status()
sessions  = c.vpn_manager.list_sessions()
connected = c.vpn_manager.is_connected()           # → bool

# Connect / disconnect / remove
c.vpn_manager.connect("wg0")
c.vpn_manager.disconnect("wg0")
c.vpn_manager.remove_profile("wg0")

# Watch tunnel events
for event in c.vpn_manager.watch_events(profile_id="wg0"):
    print(event.state)
```

### UpdateManager

```python
c.update_manager.update("/tmp/firmware.ota")   # streams file then applies it
c.update_manager.factory_reset()               # wipes all user data
```

### Logger

```python
from logger import Logger, LogLevel

Logger.init("myapp", "INFO", enable_stdout=True)
Logger.info("main", "Service started on port 8080")
Logger.error("db", f"Query failed: {err}")
```

### AppMetadata

```python
from metadata import AppMetadata

meta = AppMetadata(
    app_name="my-app",
    display_name="My Sensor App",
    version="1.0.0",
    organization="Acme",
)
meta.printStartupInfo()
meta.export_to_file("/data/meta.json")
```
