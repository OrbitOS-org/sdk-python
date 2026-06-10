"""SystemManager: device identity, OS information, and runtime metrics."""
from __future__ import annotations

import grpc

from api.common import types_pb2
from api.system_service.v26.system_service_pb2_grpc import SystemServiceStub

from .config import get_rpc_timeout


class SystemManager:
    """Read-only device and OS properties plus dev-mode toggles.

    All string getters return an empty string on failure rather than raising,
    consistent with the Go SDK behaviour.
    """

    def __init__(self, channel: grpc.Channel) -> None:
        self._stub = SystemServiceStub(channel)

    def _str(self, method) -> str:
        return method(types_pb2.Empty(), timeout=get_rpc_timeout()).value

    def _int(self, method) -> int:
        return method(types_pb2.Empty(), timeout=get_rpc_timeout()).value

    def _uint64(self, method) -> int:
        return method(types_pb2.Empty(), timeout=get_rpc_timeout()).value

    def _float(self, method) -> float:
        return method(types_pb2.Empty(), timeout=get_rpc_timeout()).value

    def _bool(self, method) -> bool:
        return method(types_pb2.Empty(), timeout=get_rpc_timeout()).value

    def get_api_version(self) -> tuple[int, int]:
        """Return ``(version, revision)`` of the Gravity API running on the device."""
        resp = self._stub.GetApiVersion(types_pb2.Void(), timeout=get_rpc_timeout())
        return (resp.version, resp.revision)

    def get_api_version_info(self) -> str:
        """Return the API version and revision as a formatted string (e.g. ``'v26.0000.0000'``)."""
        resp = self._stub.GetApiVersionInfo(types_pb2.Void(), timeout=get_rpc_timeout())
        return resp.value

    # ── Device identity ──────────────────────────────────────────────────────

    def get_device_name(self) -> str: return self._str(self._stub.GetDeviceName)
    def get_soc_model(self) -> str: return self._str(self._stub.GetSocModel)
    def get_soc_vendor(self) -> str: return self._str(self._stub.GetSocVendor)
    def get_board_model(self) -> str: return self._str(self._stub.GetBoardModel)
    def get_board_vendor(self) -> str: return self._str(self._stub.GetBoardVendor)
    def get_hardware_version(self) -> str: return self._str(self._stub.GetHardwareVersion)
    def get_hardware_model(self) -> str: return self._str(self._stub.GetHardwareModel)
    def get_system_uuid(self) -> str: return self._str(self._stub.GetSystemUuid)
    def get_board_serial(self) -> str: return self._str(self._stub.GetBoardSerial)
    def get_cpu_serial(self) -> str: return self._str(self._stub.GetCpuSerial)
    def get_machine_id(self) -> str: return self._str(self._stub.GetMachineId)
    def get_architecture(self) -> str: return self._str(self._stub.GetArchitecture)

    # ── CPU & memory ─────────────────────────────────────────────────────────

    def get_cpu_model(self) -> str: return self._str(self._stub.GetCpuModel)
    def get_total_ram(self) -> int: return self._uint64(self._stub.GetTotalRAM)
    def get_cpu_cores(self) -> int: return self._int(self._stub.GetCpuCores)
    def get_cpu_threads(self) -> int: return self._int(self._stub.GetCpuThreads)
    def get_cpu_min_mhz(self) -> float: return self._float(self._stub.GetCpuMinMhz)
    def get_cpu_max_mhz(self) -> float: return self._float(self._stub.GetCpuMaxMhz)

    # ── OS & runtime ─────────────────────────────────────────────────────────

    def get_os_name(self) -> str: return self._str(self._stub.GetOsName)
    def get_os_version(self) -> str: return self._str(self._stub.GetOsVersion)
    def get_os_revision(self) -> str: return self._str(self._stub.GetOsRevision)
    def get_runtime_version(self) -> str: return self._str(self._stub.GetRuntimeVersion)
    def get_runtime_build_date(self) -> str: return self._str(self._stub.GetRuntimeBuildDate)
    def get_distro(self) -> str: return self._str(self._stub.GetDistro)
    def get_distro_version(self) -> str: return self._str(self._stub.GetDistroVersion)
    def get_kernel_version(self) -> str: return self._str(self._stub.GetKernelVersion)

    def get_metrics(self):
        """Return a ``MetricsInfoResponse`` proto with CPU/RAM/disk usage."""
        return self._stub.GetMetrics(types_pb2.Empty(), timeout=get_rpc_timeout())

    # ── Feature toggles ──────────────────────────────────────────────────────

    def allow_untrusted_apps(self) -> bool: return self._bool(self._stub.AllowUntrustedApps)
    def disallow_untrusted_apps(self) -> bool: return self._bool(self._stub.DisallowUntrustedApps)
    def is_untrusted_apps_allowed(self) -> bool: return self._bool(self._stub.IsUntrustedAppsAllowed)
    def enable_reboot_on_failure(self) -> bool: return self._bool(self._stub.EnableRebootOnFailure)
    def disable_reboot_on_failure(self) -> bool: return self._bool(self._stub.DisableRebootOnFailure)
    def is_reboot_on_failure_enabled(self) -> bool: return self._bool(self._stub.IsRebootOnFailureEnabled)
    def enable_dev_mode(self) -> bool: return self._bool(self._stub.EnableDevMode)
    def disable_dev_mode(self) -> bool: return self._bool(self._stub.DisableDevMode)
    def is_dev_mode_enabled(self) -> bool: return self._bool(self._stub.IsDevModeEnabled)
    def enable_ssh_server(self) -> bool: return self._bool(self._stub.EnableSSHServer)
    def disable_ssh_server(self) -> bool: return self._bool(self._stub.DisableSSHServer)
    def is_ssh_server_enabled(self) -> bool: return self._bool(self._stub.IsSSHServerEnabled)

    def attach(self) -> bool: return self._bool(self._stub.Attach)

    # ── Go SDK aliases ────────────────────────────────────────────────────────

    def get_build_version(self) -> str: return self.get_os_revision()
    def get_build_date(self) -> str: return self.get_runtime_build_date()
