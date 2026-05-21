"""AutoBrows Selenium automation framework package."""

from .config import FrameworkConfig
from .driver_factory import create_driver

__all__ = ["FrameworkConfig", "create_driver"]
