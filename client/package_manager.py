"""PackageManager: app (ORB package) installation and lifecycle."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import grpc

from api.common import types_pb2
from api.package_service.v26 import packagemanager_service_pb2 as pkg_pb2
from api.package_service.v26.packagemanager_service_pb2_grpc import PackageManagerServiceStub

from .config import get_rpc_timeout


@dataclass
class InstalledPackage:
    """Metadata and runtime state of a package installed on the device."""
    id: int
    package_id: str
    display_name: str
    version: str
    app_dir: str
    data_dir: str
    package_name: str
    entry_point: str
    type: str
    args: str
    enabled: bool
    auto_restart: bool
    priority_level: int
    organization: str
    serial: str
    installed_at: str
    updated_at: str
    is_running: bool
    process_id: int
    process_status: str
    started_at: str
    uptime_seconds: int


class PackageManager:
    """Install, query, and remove ORB application packages."""

    def __init__(self, channel: grpc.Channel) -> None:
        self._stub = PackageManagerServiceStub(channel)

    def list_installed_packages(self) -> List[InstalledPackage]:
        """Return all packages currently installed on the device."""
        resp = self._stub.GetInstalledPackages(types_pb2.Empty(), timeout=get_rpc_timeout())
        return [
            InstalledPackage(
                id=p.id,
                package_id=p.package_id,
                display_name=p.display_name,
                version=p.version,
                app_dir=p.app_dir,
                data_dir=p.data_dir,
                package_name=p.package_name,
                entry_point=p.entry_point,
                type=p.type,
                args=p.args,
                enabled=p.enabled,
                auto_restart=p.auto_restart,
                priority_level=p.priority_level,
                organization=p.organization,
                serial=p.serial,
                installed_at=p.installed_at,
                updated_at=p.updated_at,
                is_running=p.is_running,
                process_id=p.process_id,
                process_status=p.process_status,
                started_at=p.started_at,
                uptime_seconds=p.uptime_seconds,
            )
            for p in resp.packages
        ]

    def remove_package(self, package_id: str) -> bool:
        """Uninstall a package by its package ID."""
        resp = self._stub.RemovePackage(pkg_pb2.RemovePackageRequest(package_id=package_id), timeout=get_rpc_timeout())
        return resp.value

    def get_installed_packages(self) -> List[InstalledPackage]:
        """Alias for :meth:`list_installed_packages`."""
        return self.list_installed_packages()

    def install_package(self, local_path: str, chunk_size: int = 256 * 1024, timeout: float = 120.0) -> bool:
        """Upload and install an ORB package archive.

        Reads the file, computes its MD5, and streams it in chunks to the device.

        Args:
            local_path: Local path to the ``.orb`` package archive.
            chunk_size: Upload chunk size in bytes (default 256 KiB).
            timeout: Overall upload + install timeout in seconds.
        """
        import hashlib
        import os

        raw = open(local_path, "rb").read()
        file_size = len(raw)
        filename = os.path.basename(local_path)
        file_md5 = hashlib.md5(raw).hexdigest()
        total_chunks = (file_size + chunk_size - 1) // chunk_size or 1

        def _generate():
            offset = 0
            chunk_number = 1
            while offset < len(raw):
                chunk = raw[offset:offset + chunk_size]
                yield pkg_pb2.PackageChunk(
                    filename=filename,
                    chunk_number=chunk_number,
                    total_chunks=total_chunks,
                    data=chunk,
                    is_last=(offset + chunk_size) >= len(raw),
                    file_md5=file_md5,
                    file_size=file_size,
                )
                offset += chunk_size
                chunk_number += 1

        resp = self._stub.InstallUpdatePackage(_generate(), timeout=timeout)
        return resp.value

    def install_update_package(self, timeout: float = 60.0):
        """Return a client-streaming call for uploading an ORB archive.

        Usage::

            stream = client.package_manager.install_update_package()
            with open("app.orb", "rb") as f:
                while chunk := f.read(256 * 1024):
                    stream.send(pkg_pb2.PackageChunk(data=chunk))
            resp = stream.close_and_recv()
        """
        return self._stub.InstallUpdatePackage(timeout=timeout)
