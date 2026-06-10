"""Structured logger — writes to stdout and the logd Unix socket."""
from __future__ import annotations

import socket
import threading
import time
from enum import IntEnum
from typing import Optional


class LogLevel(IntEnum):
    TRACE = 0
    DEBUG = 1
    INFO = 2
    WARN = 3
    ERROR = 4
    FATAL = 5

    @property
    def letter(self) -> str:
        return self.name[0]

    @classmethod
    def from_string(cls, s: str) -> "LogLevel":
        try:
            return cls[s.upper()]
        except KeyError:
            raise ValueError(f"Invalid log level: {s!r}")


class _State:
    level: LogLevel = LogLevel.TRACE
    conn: Optional[socket.socket] = None
    mutex = threading.Lock()
    print_stdout: bool = True
    socket_path: str = "/tmp/logd.sock"
    app_name: str = "void"


class Logger:
    """Static structured logger.

    Log lines go to stdout and, when ``/tmp/logd.sock`` is present,
    to the device log daemon (logd).

    Stdout format::

        2024-01-01 12:00:00 I [tag]: message

    Socket format (used by logd)::

        appname|I|tag|message

    Example::

        Logger.init("myapp", "INFO", enable_stdout=True)
        Logger.info("main", "Service started")
        Logger.error("db", "Connection refused")
    """

    @staticmethod
    def init(app_name: str, level_str: str, enable_stdout: bool) -> None:
        """Initialise the logger.

        Args:
            app_name: App name embedded in every socket log line.
            level_str: Minimum level string (``"TRACE"``…``"FATAL"``).
            enable_stdout: Whether to print to stdout.
        """
        Logger.set_app_name(app_name)
        Logger.set_level_str(level_str)
        Logger.set_print_stdout(enable_stdout)

    @staticmethod
    def set_app_name(name: str) -> None:
        with _State.mutex:
            _State.app_name = name

    @staticmethod
    def set_print_stdout(enable: bool) -> None:
        _State.print_stdout = enable

    @staticmethod
    def set_level(level: LogLevel) -> None:
        _State.level = level

    @staticmethod
    def set_level_str(level_str: str) -> None:
        _State.level = LogLevel.from_string(level_str)

    @staticmethod
    def get_level() -> LogLevel:
        return _State.level

    @staticmethod
    def trace(tag: str, text: str) -> None: Logger._print(LogLevel.TRACE, tag, text)

    @staticmethod
    def debug(tag: str, text: str) -> None: Logger._print(LogLevel.DEBUG, tag, text)

    @staticmethod
    def info(tag: str, text: str) -> None: Logger._print(LogLevel.INFO, tag, text)

    @staticmethod
    def warn(tag: str, text: str) -> None: Logger._print(LogLevel.WARN, tag, text)

    @staticmethod
    def error(tag: str, text: str) -> None: Logger._print(LogLevel.ERROR, tag, text)

    @staticmethod
    def fatal(tag: str, text: str) -> None: Logger._print(LogLevel.FATAL, tag, text)

    @staticmethod
    def _print(level: LogLevel, tag: str, msg: str) -> None:
        if level < _State.level:
            return
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        tag_display = tag[:17]
        lines = msg.splitlines() or [""]
        with _State.mutex:
            for line in lines:
                if _State.print_stdout:
                    print(f"{timestamp} {level.letter} [{tag_display}]: {line}")
                Logger._send_to_socket(level, tag, line)

    @staticmethod
    def _send_to_socket(level: LogLevel, tag: str, msg: str) -> None:
        if _State.conn is None:
            Logger._connect()
        if _State.conn is None:
            return
        try:
            _State.conn.send(f"{_State.app_name}|{level.letter}|{tag}|{msg}".encode("utf-8"))
        except (socket.error, OSError):
            try:
                _State.conn.close()
            except Exception:
                pass
            _State.conn = None

    @staticmethod
    def _connect() -> None:
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            sock.connect(_State.socket_path)
            _State.conn = sock
        except (socket.error, OSError, AttributeError):
            _State.conn = None
