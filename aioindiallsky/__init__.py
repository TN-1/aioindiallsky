"""aioindiallsky package."""
from importlib.metadata import version, PackageNotFoundError

from .client import IndiAllSkyClient
from .exceptions import (
    IndiAllSkyError,
    IndiAllSkyConnectionError,
    IndiAllSkyTimeoutError,
    IndiAllSkyAuthError,
    IndiAllSkyCommandError,
)
from .models import ExposureData, SensorData, MediaData, MonthItem, VideoItem, ImageItem

try:
    __version__ = version("aioindiallsky")
except PackageNotFoundError:
    __version__ = "0.1.5"

__all__ = [
    "IndiAllSkyClient",
    "IndiAllSkyError",
    "IndiAllSkyConnectionError",
    "IndiAllSkyTimeoutError",
    "IndiAllSkyAuthError",
    "IndiAllSkyCommandError",
    "ExposureData",
    "SensorData",
    "MediaData",
    "MonthItem",
    "VideoItem",
    "ImageItem",
]
