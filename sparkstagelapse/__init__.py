from __future__ import annotations

from .dashboard.client import DashboardClient
from .display import SparkDisplay, display
import logging

logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = ["SparkDisplay", "display", "DashboardClient"]

__version__ = "0.1.0"
