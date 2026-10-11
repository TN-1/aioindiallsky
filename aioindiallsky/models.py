"""Data models for aioindiallsky library."""
from dataclasses import dataclass
from typing import Dict, Any, Optional, List

_UNSUPPORTED_TEMPERATURE = -273.15


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
        f = float(val)
        if round(f, 2) <= _UNSUPPORTED_TEMPERATURE:
            return None
        return f
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


def _extract_slot_value(lst: List[Any], index: int) -> Optional[float]:
    if index < len(lst):
        item = lst[index]
        res = item.get("value") if isinstance(item, dict) else item
        return _safe_optional_float(res)
    return None


def _extract_cpu_temp(raw_temp: List[Any]) -> Optional[float]:
    if len(raw_temp) > 10:
        item = raw_temp[10]
        res = item.get("value") if isinstance(item, dict) else item
        f_val = _safe_optional_float(res)
        if f_val is not None and f_val > 0:
            return round(f_val, 1)
    return None


@dataclass
class SensorData:
    last_update: Optional[str]
    sensors: Dict[str, Any]
    raw_user: List[Any]
    raw_temp: List[Any]
    raw_data: Optional[Dict[str, Any]] = None
    dew_heater: Optional[float] = None
    dew_point: Optional[float] = None
    frost_point: Optional[float] = None
    fan_duty_cycle: Optional[float] = None
    heat_index: Optional[float] = None
    wind_direction: Optional[float] = None
    device_sqm: Optional[float] = None
    camera_sqm: Optional[float] = None
    camera_sqm_adu: Optional[float] = None
    cpu_temperature: Optional[float] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SensorData":
        last_up = data.get("last_update")
        sensors_raw = data.get("sensors")
        sensors_dict: Dict[str, Any] = sensors_raw if isinstance(sensors_raw, dict) else {}
        user_raw = data.get("sensor_user")
        raw_user_list: List[Any] = user_raw if isinstance(user_raw, list) else []
        temp_raw = data.get("sensor_temp")
        raw_temp_list: List[Any] = temp_raw if isinstance(temp_raw, list) else []

        dew_heater = _safe_optional_float(data.get("dew_heater"))
        if dew_heater is None:
            dew_heater = _extract_slot_value(raw_user_list, 1)

        dew_point = _safe_optional_float(data.get("dew_point"))
        if dew_point is None:
            dew_point = _extract_slot_value(raw_user_list, 2)

        frost_point = _safe_optional_float(data.get("frost_point"))
        if frost_point is None:
            frost_point = _extract_slot_value(raw_user_list, 3)

        fan_duty_cycle = _safe_optional_float(data.get("fan_duty_cycle"))
        if fan_duty_cycle is None:
            fan_duty_cycle = _extract_slot_value(raw_user_list, 4)

        heat_index = _safe_optional_float(data.get("heat_index"))
        if heat_index is None:
            heat_index = _extract_slot_value(raw_user_list, 5)

        wind_direction = _safe_optional_float(data.get("wind_direction"))
        if wind_direction is None:
            wind_direction = _extract_slot_value(raw_user_list, 6)

        device_sqm = _safe_optional_float(data.get("device_sqm"))
        if device_sqm is None:
            device_sqm = _extract_slot_value(raw_user_list, 7)

        camera_sqm = _safe_optional_float(data.get("camera_sqm"))
        if camera_sqm is None:
            camera_sqm = _extract_slot_value(raw_user_list, 8)

        camera_sqm_adu = _safe_optional_float(data.get("camera_sqm_adu"))
        if camera_sqm_adu is None:
            camera_sqm_adu = _extract_slot_value(raw_user_list, 9)

        cpu_temperature = _safe_optional_float(data.get("cpu_temperature"))
        if cpu_temperature is None:
            cpu_temperature = _extract_cpu_temp(raw_temp_list)

        return cls(
            last_update=str(last_up) if last_up is not None else None,
            sensors=sensors_dict,
            raw_user=raw_user_list,
            raw_temp=raw_temp_list,
            raw_data=data,
            dew_heater=dew_heater,
            dew_point=dew_point,
            frost_point=frost_point,
            fan_duty_cycle=fan_duty_cycle,
            heat_index=heat_index,
            wind_direction=wind_direction,
            device_sqm=device_sqm,
            camera_sqm=camera_sqm,
            camera_sqm_adu=camera_sqm_adu,
            cpu_temperature=cpu_temperature,
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


@dataclass
class MonthItem:
    month: int
    name: str

    @classmethod
    def from_entry(cls, entry: Any) -> Optional["MonthItem"]:
        if isinstance(entry, (list, tuple)) and len(entry) >= 2:
            try:
                m_int = int(entry[0])
                return cls(month=m_int, name=str(entry[1]))
            except (ValueError, TypeError):
                return None
        return None


@dataclass
class VideoItem:
    id: int
    url: str
    day_date: str
    day_date_long: str
    night: bool
    success: bool
    keogram_url: Optional[str] = None
    keogram_thumbnail_url: Optional[str] = None
    startrail_url: Optional[str] = None
    startrail_thumbnail_url: Optional[str] = None
    startrail_timelapse_url: Optional[str] = None
    panorama_timelapse_url: Optional[str] = None
    avg_stars: Optional[int] = None
    avg_sqm: Optional[float] = None
    max_kpindex: Optional[float] = None
    max_moonphase: Optional[float] = None
    raw_data: Optional[Dict[str, Any]] = None

    @property
    def mime_type(self) -> str:
        return "video/mp4"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VideoItem":
        def _clean_str(val: Any) -> Optional[str]:
            if val is None or val == "None" or val == "":
                return None
            return str(val)

        return cls(
            id=_safe_int(data.get("id"), 0),
            url=str(data.get("url", "") or ""),
            day_date=str(data.get("dayDate", "") or ""),
            day_date_long=str(data.get("dayDate_long", "") or ""),
            night=bool(data.get("night", False)),
            success=bool(data.get("success", False)),
            keogram_url=_clean_str(data.get("keogram")),
            keogram_thumbnail_url=_clean_str(data.get("keogram_thumbnail")),
            startrail_url=_clean_str(data.get("startrail")),
            startrail_thumbnail_url=_clean_str(data.get("startrail_thumbnail")),
            startrail_timelapse_url=_clean_str(data.get("startrail_timelapse")),
            panorama_timelapse_url=_clean_str(data.get("panorama_timelapse")),
            avg_stars=_safe_optional_int(data.get("avg_stars")),
            avg_sqm=_safe_optional_float(data.get("avg_sqm")),
            max_kpindex=_safe_optional_float(data.get("max_kpindex")),
            max_moonphase=_safe_optional_float(data.get("max_moonphase")),
            raw_data=data,
        )


@dataclass
class ImageItem:
    id: int
    url: str
    timestamp: int
    time_str: str
    width: int
    height: int
    raw_data: Optional[Dict[str, Any]] = None

    @property
    def mime_type(self) -> str:
        if self.url.lower().endswith(".png"):
            return "image/png"
        return "image/jpeg"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ImageItem":
        return cls(
            id=_safe_int(data.get("id"), 0),
            url=str(data.get("url", "") or ""),
            timestamp=_safe_int(data.get("ts"), 0),
            time_str=str(data.get("date", "") or ""),
            width=_safe_int(data.get("width"), 0),
            height=_safe_int(data.get("height"), 0),
            raw_data=data,
        )
