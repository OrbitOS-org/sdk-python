"""
OrbitOS Python SDK — client package.

Quick start::

    from client import Client, GpioPin

    with Client.connect("192.168.1.100") as c:
        print(c.system_manager.get_device_name())
        pin = GpioPin(number=26, chip_number=0)
        c.gpio_manager.set_level(pin, high=True)
"""
from .client import Client
from .gpio_manager import GpioPin
from .pwm_manager import PwmChannel, PwmProperties
from .i2c_manager import I2CConfig, I2CBus
from .spi_manager import SpiConfig, SpiDevice
from .uart_manager import UartConfig, UartPort
from .config import get_rpc_timeout, set_rpc_timeout

__all__ = [
    "Client",
    "GpioPin",
    "PwmChannel", "PwmProperties",
    "I2CConfig", "I2CBus",
    "SpiConfig", "SpiDevice",
    "UartConfig", "UartPort",
    "get_rpc_timeout", "set_rpc_timeout",
]
