"""Data models for aioindiallsky library."""
from dataclasses import dataclass
from typing import Dict, Any, Optional, List


def _safe_float(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_int(val: Any, default: int = 0) -> int:
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _safe_optional_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_optional_int(val: Any) -> Optional[int]:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


@dataclass
class ExposureData:
    filename: str
    create_date: str
    exposure: float
    gain: float
    binmode: int
    night: bool
    camera_id: int
    id: Optional[int] = None
    temp: Optional[float] = None
    adu: Optional[float] = None
    sqm: Optional[float] = None
    stars: Optional[int] = None
    hfr: Optional[float] = None
    raw_data: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExposureData":
        return cls(
            filename=str(data.get("filename", "") or ""),
            create_date=str(data.get("createDate", "") or ""),
            exposure=_safe_float(data.get("exposure"), 0.0),
            gain=_safe_float(data.get("gain"), 0.0),
            binmode=_safe_int(data.get("binmode"), 1),
            night=bool(data.get("night", False)),
            camera_id=_safe_int(data.get("camera_id"), 0),
            id=_safe_optional_int(data.get("id")),
            temp=_safe_optional_float(data.get("temp")),
            adu=_safe_optional_float(data.get("adu")),
            sqm=_safe_optional_float(data.get("sqm")),
            stars=_safe_optional_int(data.get("stars")),
            hfr=_safe_optional_float(data.get("hfr")),
            raw_data=data,
        )


@dataclass
class SensorData:
    last_update: Optional[str]
    sensors: Dict[str, Any]
    raw_user: List[Any]
    raw_temp: List[Any]
    raw_data: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SensorData":
        last_up = data.get("last_update")
        sensors_raw = data.get("sensors")
        sensors_dict: Dict[str, Any] = sensors_raw if isinstance(sensors_raw, dict) else {}
        user_raw = data.get("sensor_user")
        raw_user_list: List[Any] = user_raw if isinstance(user_raw, list) else []
        temp_raw = data.get("sensor_temp")
        raw_temp_list: List[Any] = temp_raw if isinstance(temp_raw, list) else []

        return cls(
            last_update=str(last_up) if last_up is not None else None,
            sensors=sensors_dict,
            raw_user=raw_user_list,
            raw_temp=raw_temp_list,
            raw_data=data,
        )


@dataclass
class MediaData:
    media_type: str  # 'timelapse', 'keogram', 'startrail', 'minitimelapse'
    filename: str
    day_date: str
    night: bool
    camera_id: int
    id: Optional[int] = None
    raw_data: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, media_type: str, data: Dict[str, Any]) -> "MediaData":
        return cls(
            media_type=media_type,
            filename=str(data.get("filename", "") or ""),
            day_date=str(data.get("dayDate", "") or ""),
            night=bool(data.get("night", False)),
            camera_id=_safe_int(data.get("camera_id"), 0),
            id=_safe_optional_int(data.get("id")),
            raw_data=data,
        )
