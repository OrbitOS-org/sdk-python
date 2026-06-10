"""CameraManager: camera capture and frame streaming."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generator, List

import grpc

from api.common import types_pb2
from api.camera_service.v26 import camera_service_pb2 as cam_pb2
from api.camera_service.v26.camera_service_pb2_grpc import CameraServiceStub

from .config import get_rpc_timeout


@dataclass
class CameraDeviceInfo:
    """Driver and format capabilities for a camera device."""
    device_id: str
    driver: str
    card: str
    supported_formats: List[str] = field(default_factory=list)
    resolutions: List[str] = field(default_factory=list)


@dataclass
class CapturedImage:
    """Single captured image."""
    image_data: bytes
    format: str
    timestamp: int


class CameraManager:
    """Capture images and stream video frames from V4L2 camera devices."""

    def __init__(self, channel: grpc.Channel) -> None:
        self._stub = CameraServiceStub(channel)

    def _call(self, method, *args):
        return method(*args, timeout=get_rpc_timeout())

    def list_devices(self) -> List[CameraDeviceInfo]:
        """Return all camera devices discovered on the system."""
        resp = self._call(self._stub.ListDevices, cam_pb2.ListDevicesRequest())
        return [
            CameraDeviceInfo(
                device_id=d.device_id,
                driver=d.driver,
                card=d.card,
                supported_formats=list(d.supported_formats),
                resolutions=list(d.resolutions),
            )
            for d in resp.devices
        ]

    def lock_camera(self, device_id: str, client_id: str) -> bool:
        """Acquire exclusive access to a camera device."""
        resp = self._call(self._stub.LockCamera, cam_pb2.LockRequest(device_id=device_id, client_id=client_id))
        return resp.success

    def unlock_camera(self, device_id: str, client_id: str) -> bool:
        """Release exclusive access to a camera device."""
        resp = self._call(self._stub.UnlockCamera, cam_pb2.UnlockRequest(device_id=device_id, client_id=client_id))
        return resp.success

    def capture_image(self, device_id: str, width: int = 0, height: int = 0, format: str = "mjpeg") -> CapturedImage:
        """Capture a single frame.

        Args:
            device_id: V4L2 device path (e.g. ``"/dev/video0"``).
            width: Desired frame width in pixels (0 = device default).
            height: Desired frame height in pixels (0 = device default).
            format: Image encoding (``"mjpeg"`` or ``"yuv420"``).
        """
        req = cam_pb2.CaptureImageRequest(device_id=device_id, width=width, height=height, format=format)
        resp = self._call(self._stub.CaptureImage, req)
        return CapturedImage(
            image_data=resp.image_data,
            format=resp.format,
            timestamp=resp.timestamp,
        )

    def stream_frames(self, device_id: str, fps: int = 30, width: int = 0, height: int = 0,
                      timeout: float | None = None) -> Generator:
        """Stream ``Frame`` proto messages from a camera device.

        Args:
            device_id: V4L2 device path (e.g. ``"/dev/video0"``).
            fps: Requested frames per second.
            width: Requested width (0 = device default).
            height: Requested height (0 = device default).
            timeout: Stream read timeout.

        Example::

            for frame in client.camera_manager.stream_frames("/dev/video0", fps=30):
                process(frame.data, frame.width, frame.height)
                if done:
                    break
        """
        req = cam_pb2.StreamFramesRequest(device_id=device_id, fps=fps, width=width, height=height)
        stream = self._stub.StreamFrames(req, timeout=timeout)
        try:
            for frame in stream:
                yield frame
        finally:
            stream.cancel()

    def get_device_info(self, device_id: str):
        """Return driver and format capabilities for a camera device."""
        return self._call(self._stub.GetDeviceInfo, cam_pb2.DeviceInfoRequest(device_id=device_id))
