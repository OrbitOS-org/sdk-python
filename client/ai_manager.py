"""AIManager: on-device ML model loading and inference."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Generator, Iterator, List

import grpc

from api.ai_service.v26 import ai_service_pb2 as ai_pb2
from api.ai_service.v26.ai_service_pb2_grpc import AiServiceStub

from .config import get_rpc_timeout

# Re-export proto enums for convenience
ONNX = ai_pb2.ONNX
TFLITE = ai_pb2.TFLITE
EXEC_CPU = ai_pb2.EXEC_CPU
EXEC_GPU = ai_pb2.EXEC_GPU
EXEC_HIGH_THREADS = ai_pb2.EXEC_HIGH_THREADS
TENSOR_FLOAT32 = ai_pb2.TENSOR_FLOAT32
TENSOR_UINT8 = ai_pb2.TENSOR_UINT8


@dataclass
class ModelInfo:
    """Summary of a loaded model."""
    model_id: str
    version: str
    backend: int
    loaded_at_unix: int


class AIManager:
    """Load ONNX/TFLite models and run inference on the device NPU or CPU.

    Model files are referenced by their path on the device filesystem.
    :meth:`upload_and_load_model` streams a local file to the device and loads it
    in one step.
    """

    def __init__(self, channel: grpc.Channel) -> None:
        self._stub = AiServiceStub(channel)

    def _call(self, method, *args):
        return method(*args, timeout=get_rpc_timeout())

    def load_model(self, model_id: str, model_path: str,
                   backend: int = ONNX, execution: int = EXEC_CPU, version: str = ""):
        """Load a model already present on the device filesystem.

        Args:
            model_id: Unique identifier used for subsequent :meth:`infer` calls.
            model_path: Absolute path on the device (e.g. ``"/data/model.onnx"``).
            backend: ``ONNX`` or ``TFLITE``.
            execution: ``EXEC_CPU``, ``EXEC_GPU``, or ``EXEC_HIGH_THREADS``.
            version: Optional version label.
        """
        req = ai_pb2.LoadModelRequest(
            model_id=model_id, model_path=model_path,
            backend=backend, execution=execution, version=version or "",
        )
        return self._call(self._stub.LoadModel, req)

    def unload_model(self, model_id: str):
        """Unload a model and free its resources."""
        return self._call(self._stub.UnloadModel, ai_pb2.UnloadModelRequest(model_id=model_id))

    def list_models(self) -> List[ModelInfo]:
        """Return all currently loaded models."""
        resp = self._call(self._stub.ListModels, ai_pb2.ListModelsRequest())
        return [
            ModelInfo(
                model_id=m.model_id,
                version=m.version,
                backend=m.backend,
                loaded_at_unix=m.loaded_at_unix,
            )
            for m in resp.models
        ]

    def is_model_loaded(self, model_id: str):
        """Check whether a model is currently loaded."""
        return self._call(self._stub.IsModelLoaded, ai_pb2.IsModelLoadedRequest(model_id=model_id))

    def infer(self, model_id: str, input_data: bytes, input_shape: list[int] | None = None,
              input_dtype: int = TENSOR_FLOAT32):
        """Run a single inference pass.

        Args:
            model_id: ID of a loaded model.
            input_data: Raw tensor bytes (row-major, matching ``input_dtype``).
            input_shape: Tensor dimensions (optional — uses model default if omitted).
            input_dtype: ``TENSOR_FLOAT32`` or ``TENSOR_UINT8``.
        """
        req = ai_pb2.InferRequest(
            model_id=model_id, input_data=input_data,
            input_shape=input_shape or [], input_dtype=input_dtype,
        )
        return self._call(self._stub.Infer, req)

    def upload_and_load_model(self, model_id: str, local_path: str,
                              backend: int = ONNX, execution: int = EXEC_CPU,
                              version: str = "", chunk_size: int = 256 * 1024):
        """Stream a local model file to the device and load it.

        Args:
            model_id: Unique identifier to assign.
            local_path: Path to the model file on the local machine.
            backend: ``ONNX`` or ``TFLITE``.
            execution: Execution provider.
            chunk_size: Upload chunk size in bytes (default 256 KiB).

        Returns:
            ``LoadModelResponse`` proto on success.
        """
        import os
        file_size = os.path.getsize(local_path)
        filename = os.path.basename(local_path)

        def _generate():
            yield ai_pb2.UploadModelChunk(meta=ai_pb2.UploadModelMeta(
                model_id=model_id, backend=backend, execution=execution,
                version=version or "", total_bytes=file_size, filename=filename,
            ))
            with open(local_path, "rb") as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield ai_pb2.UploadModelChunk(data=chunk)

        return self._stub.UploadAndLoadModel(_generate(), timeout=max(120.0, get_rpc_timeout()))

    def stream_infer(self, requests: Iterator, timeout: float | None = None) -> Generator:
        """Bidirectional streaming inference.

        Yields ``InferResponse`` messages as they arrive.
        Call ``stream.cancel()`` when done — handled automatically via the
        generator's ``finally`` block.
        """
        stream = self._stub.StreamInfer(requests, timeout=timeout)
        try:
            for resp in stream:
                yield resp
        finally:
            stream.cancel()
