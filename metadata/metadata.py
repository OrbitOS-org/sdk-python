"""App metadata — aligned with the Go SDK AppMetadata / AppManifest split.

Build vars (``BUILD_DATE``, ``GIT_COMMIT``, ``ENTRY_POINT``, ``PACKAGE_TYPE``,
``BUILD_ARCH``) are substituted by the build script at package time.
"""
from __future__ import annotations

import json
import os
import platform
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Optional

from logger.logger import Logger

BASE_VERSION = "1.0.0"   # AUTO-UPDATED BY build script
BUILD_DATE   = "unknown" # AUTO-UPDATED at build time
GIT_COMMIT   = "unknown" # AUTO-UPDATED at build time
ENTRY_POINT  = ""        # AUTO-UPDATED at build time
PACKAGE_TYPE = "python"  # AUTO-UPDATED at build time
BUILD_ARCH   = ""        # AUTO-UPDATED at build time (platform.machine() fallback)

_LOG_TAG = "metadata"


@dataclass
class AppManifest:
    """Static part of the manifest — read from metadata.json or created inline.

    Equivalent to the Go SDK ``AppManifest`` struct.  Entry point, package type,
    and architecture come from the build system, not from this struct.

    Example::

        manifest = AppManifest(
            package_id="org.orbit-os.app.my-sensor",
            name="Sensor Monitor",
            version="1.2.0",
            description="Reads temperature and humidity",
            permissions=["SystemService/*", "SensorService/*"],
        )
        manifest.print_info()
        meta = build(manifest)
    """
    package_id:  str       = ""
    name:        str       = ""
    version:     str       = ""
    description: str       = ""
    permissions: list[str] = field(default_factory=list)

    def print_info(self) -> None:
        """Log a formatted manifest banner — same layout as Go's PrintInfo()."""
        perms = ", ".join(self.permissions) if self.permissions else "(none)"
        Logger.info(_LOG_TAG, "--- App metadata -------------------------------------------")
        Logger.info(_LOG_TAG, f" Package ID  : {self.package_id}")
        Logger.info(_LOG_TAG, f" Name        : {self.name}")
        Logger.info(_LOG_TAG, f" Version     : {self.version}")
        Logger.info(_LOG_TAG, f" Description : {self.description}")
        Logger.info(_LOG_TAG, f" Permissions : {perms}")
        Logger.info(_LOG_TAG, "------------------------------------------------------------")


@dataclass(frozen=True)
class AppMetadata:
    """Full manifest — AppManifest merged with build-time vars.

    Aligned with the Go SDK ``AppMetadata`` struct.
    JSON key order matches Go's manifest.json produced by build_package.sh.
    ``slug`` is Python-only (not written to manifest.json) and is intended for
    ``Logger.init()``.

    Example::

        manifest = AppManifest(
            package_id="org.orbit-os.app.my-sensor",
            name="Sensor Monitor",
            version="1.0.0",
            description="Reads temperature and humidity",
        )
        meta = build(manifest)
        Logger.init(meta.slug, "INFO", True)
        manifest.print_info()
    """
    package_id:   str            = "org.orbit-os.sdk.python"
    version:      str            = BASE_VERSION
    name:         str            = "OrbitOS Python SDK"
    description:  str            = "OrbitOS Python SDK"
    type:         str            = "python"
    architecture: str            = ""
    entry_point:  str            = ""
    build_date:   Optional[str]  = BUILD_DATE
    git_commit:   Optional[str]  = GIT_COMMIT
    permissions:  tuple[str, ...] = ()
    slug:         str            = ""  # Python-only: short id for Logger.init()

    def to_dict(self) -> dict[str, Any]:
        """Return a Go-compatible manifest dict (same field order as manifest.json)."""
        d: dict[str, Any] = OrderedDict([
            ("package_id",   self.package_id),
            ("version",      self.version),
            ("name",         self.name),
            ("description",  self.description),
            ("type",         self.type),
            ("architecture", self.architecture),
            ("entry_point",  self.entry_point),
            ("build_date",   self.build_date),
            ("git_commit",   self.git_commit),
            ("permissions",  list(self.permissions)),
        ])
        # slug is Python-only — never written to the ORB manifest
        return {k: v for k, v in d.items() if v is not None and v != "" and v != []}

    def export_to_file(self, path: str) -> None:
        """Write metadata as JSON to ``path``."""
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    def print_json(self) -> None:
        """Print metadata as formatted JSON to stdout."""
        print(json.dumps(self.to_dict(), indent=2))

    def printStartupInfo(self) -> None:
        """Log a formatted startup banner via :class:`~logger.Logger`."""
        tag = "MetaData"
        Logger.info(tag, "------------------------------------------------")
        Logger.info(tag, f" Init {self.name}")
        Logger.info(tag, "------------------------------------------------")
        Logger.info(tag, f" PackageID : {self.package_id}")
        Logger.info(tag, f" Version   : {self.version}")
        Logger.info(tag, f" BuildDate : {self.build_date}")
        Logger.info(tag, f" GitCommit : {self.git_commit}")
        Logger.info(tag, "------------------------------------------------")


def parse_app_manifest_json(data: bytes | str) -> tuple[AppManifest, Exception | None]:
    """Parse metadata.json bytes/string into an :class:`AppManifest`.

    Returns ``(manifest, None)`` on success, ``(AppManifest(), exception)`` on
    failure.  Equivalent to the Go SDK ``ParseAppManifestJSON``.
    """
    try:
        raw: dict = json.loads(data)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        return AppManifest(), e

    name = raw.get("name", "")
    description = raw.get("description", "")
    if not name or not description:
        return AppManifest(), ValueError("metadata.json: name and description are required")

    return AppManifest(
        package_id=raw.get("package_id", ""),
        name=name,
        version=raw.get("version", ""),
        description=description,
        permissions=list(raw.get("permissions", [])),
    ), None


def must_parse_app_manifest_json(path: str | os.PathLike = "metadata.json") -> AppManifest:
    """Load :class:`AppManifest` from a JSON file, raising ``ValueError`` on any error.

    Equivalent to the Go SDK ``MustParseAppManifestJSON``.  Defaults to
    ``"metadata.json"`` in the current directory; pass an absolute path when
    calling from a module (``os.path.join(os.path.dirname(__file__), "metadata.json")``).
    """
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        raise ValueError(f"metadata.json: {e}") from e
    manifest, err = parse_app_manifest_json(data)
    if err is not None:
        raise ValueError(f"metadata.json: {err}")
    return manifest


def build(manifest: AppManifest) -> AppMetadata:
    """Merge an :class:`AppManifest` with build-time vars to produce :class:`AppMetadata`.

    Equivalent to the Go SDK ``Build()``.
    ``slug`` is derived from the last dotted segment of ``package_id``
    (e.g. ``"org.orbit-os.app.sensor"`` → ``"sensor"``), falling back to a
    snake-cased ``name``.
    """
    pkg_type = PACKAGE_TYPE if PACKAGE_TYPE else "python"
    arch = BUILD_ARCH if BUILD_ARCH else platform.machine()
    slug = (
        manifest.package_id.rsplit(".", 1)[-1]
        if manifest.package_id
        else manifest.name.lower().replace(" ", "_")
    )
    return AppMetadata(
        package_id=manifest.package_id,
        version=manifest.version or BASE_VERSION,
        name=manifest.name,
        description=manifest.description,
        type=pkg_type,
        architecture=arch,
        entry_point=ENTRY_POINT,
        build_date=BUILD_DATE,
        git_commit=GIT_COMMIT,
        permissions=tuple(manifest.permissions),
        slug=slug,
    )
