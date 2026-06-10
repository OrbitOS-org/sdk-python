"""UpdateManager: OTA firmware update and factory reset."""
from __future__ import annotations

import grpc

from api.common import types_pb2
from api.update_service.v26 import update_service_pb2 as upd_pb2
from api.update_service.v26.update_service_pb2_grpc import UpdateServiceStub

from .config import get_rpc_timeout


class UpdateManager:
    """Apply OTA firmware updates and perform factory resets."""

    def __init__(self, channel: grpc.Channel) -> None:
        self._stub = UpdateServiceStub(channel)

    def factory_reset(self) -> bool:
        """Restore the device to factory defaults.

        .. warning::
            This erases all user data and installed packages.
        """
        resp = self._stub.FactoryReset(types_pb2.Empty(), timeout=get_rpc_timeout())
        return resp.value

    def update(self, local_path: str, chunk_size: int = 256 * 1024, timeout: float = 120.0) -> bool:
        """Upload a firmware archive and apply it.

        The file is read into memory, checksummed, and streamed to the device
        in ``chunk_size``-byte chunks.

        Args:
            local_path: Local path to the ``.ota`` firmware archive.
            chunk_size: Upload chunk size in bytes (default 256 KiB).
            timeout: Overall upload + apply timeout in seconds.

        Returns:
            ``True`` on success.
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
                yield upd_pb2.FileChunk(
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

        resp = self._stub.Update(_generate(), timeout=timeout)
        return resp.value
