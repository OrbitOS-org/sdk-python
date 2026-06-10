"""BluetoothManager: classic Bluetooth and BLE operations."""
from __future__ import annotations

import grpc

from api.bluetooth_service.v26.bluetooth_service_pb2_grpc import BluetoothServiceStub

from .config import get_rpc_timeout

_STREAM_TIMEOUT = 30.0


class BluetoothManager:
    """Full Bluetooth and BLE control — adapter, bonding, GATT, and advertising.

    Methods that perform scanning or bonding use a longer timeout than regular
    RPC calls. All request/response types come from
    ``bluetooth_service.v26.bluetooth_service_pb2``.
    """

    def __init__(self, channel: grpc.Channel) -> None:
        self._stub = BluetoothServiceStub(channel)

    def _u(self, method, *args, **kwargs):
        return method(*args, timeout=get_rpc_timeout(), **kwargs)

    def _s(self, method, *args, **kwargs):
        return method(*args, timeout=_STREAM_TIMEOUT, **kwargs)

    # ── Adapter ──────────────────────────────────────────────────────────────

    def get_adapter_info(self, request): return self._u(self._stub.GetAdapterInfo, request)
    def enable_bluetooth(self, request): return self._u(self._stub.EnableBluetooth, request)
    def disable_bluetooth(self, request): return self._u(self._stub.DisableBluetooth, request)
    def get_local_name(self, request): return self._u(self._stub.GetLocalName, request)
    def set_local_name(self, request): return self._u(self._stub.SetLocalName, request)
    def set_discoverable(self, request): return self._u(self._stub.SetDiscoverable, request)

    # ── Classic BT ───────────────────────────────────────────────────────────

    def start_scan(self, request): return self._s(self._stub.StartScan, request)
    def get_bonded_devices(self, request): return self._u(self._stub.GetBondedDevices, request)
    def bond_device(self, request): return self._s(self._stub.BondDevice, request)
    def remove_bond(self, request): return self._u(self._stub.RemoveBond, request)
    def connect_device(self, request): return self._u(self._stub.ConnectDevice, request)
    def disconnect_device(self, request): return self._u(self._stub.DisconnectDevice, request)
    def get_connection_state(self, request): return self._u(self._stub.GetConnectionState, request)

    # ── BLE ──────────────────────────────────────────────────────────────────

    def start_ble_scan(self, request): return self._s(self._stub.StartBleScan, request)
    def gatt_connect(self, request): return self._u(self._stub.GattConnect, request)
    def gatt_disconnect(self, request): return self._u(self._stub.GattDisconnect, request)
    def get_gatt_state(self, request): return self._u(self._stub.GetGattState, request)
    def gatt_discover_services(self, request): return self._u(self._stub.GattDiscoverServices, request)
    def gatt_read_characteristic(self, request): return self._u(self._stub.GattReadCharacteristic, request)
    def gatt_write_characteristic(self, request): return self._u(self._stub.GattWriteCharacteristic, request)
    def gatt_subscribe_characteristic(self, request): return self._s(self._stub.GattSubscribeCharacteristic, request)
    def gatt_read_descriptor(self, request): return self._u(self._stub.GattReadDescriptor, request)
    def gatt_write_descriptor(self, request): return self._u(self._stub.GattWriteDescriptor, request)
    def gatt_read_rssi(self, request): return self._u(self._stub.GattReadRssi, request)
    def request_mtu(self, request): return self._u(self._stub.RequestMtu, request)
    def request_connection_priority(self, request): return self._u(self._stub.RequestConnectionPriority, request)
    def set_preferred_phy(self, request): return self._u(self._stub.SetPreferredPhy, request)
    def read_phy(self, request): return self._u(self._stub.ReadPhy, request)

    # ── Advertising ──────────────────────────────────────────────────────────

    def start_advertising(self, request): return self._u(self._stub.StartAdvertising, request)
    def stop_advertising(self, request): return self._u(self._stub.StopAdvertising, request)
