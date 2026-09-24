"""Tests for aioindiallsky models."""
from aioindiallsky.models import ExposureData, SensorData, MediaData


def test_exposure_data_from_dict_valid():
    raw = {
        "filename": "allsky_0001.jpg",
        "createDate": "2026-08-13 20:00:00",
        "exposure": 5.5,
        "gain": 100.0,
        "binmode": 1,
        "night": True,
        "camera_id": 2,
        "id": 42,
        "temp": -10.5,
        "adu": 1500.0,
        "sqm": 21.4,
        "stars": 150,
        "hfr": 2.3,
    }
    exp = ExposureData.from_dict(raw)
    assert exp.filename == "allsky_0001.jpg"
    assert exp.exposure == 5.5
    assert exp.gain == 100.0
    assert exp.binmode == 1
    assert exp.night is True
    assert exp.camera_id == 2
    assert exp.id == 42
    assert exp.temp == -10.5
    assert exp.sqm == 21.4
    assert exp.stars == 150
    assert exp.raw_data == raw


def test_exposure_data_from_dict_null_safety():
    raw = {
        "filename": None,
        "createDate": None,
        "exposure": None,
        "gain": None,
        "binmode": None,
        "night": None,
        "camera_id": None,
        "id": None,
        "temp": None,
        "sqm": "invalid_number",
    }
    exp = ExposureData.from_dict(raw)
    assert exp.filename == ""
    assert exp.exposure == 0.0
    assert exp.gain == 0.0
    assert exp.binmode == 1
    assert exp.night is False
    assert exp.camera_id == 0
    assert exp.id is None
    assert exp.temp is None
    assert exp.sqm is None


def test_exposure_data_unsupported_temp():
    raw = {"temp": -273.15}
    exp = ExposureData.from_dict(raw)
    assert exp.temp is None


def test_sensor_data_from_dict():
    raw = {
        "last_update": "2026-08-13 20:00:00",
        "sensors": {
            "custom_ambient_temp": {"name": "Temperature", "value": 22.5, "unit": "C"},
        },
        "sensor_user": [0, 50.0, 14.2, -2.5, 75.0, 25.0, 180.0, 20.1, 19.8, 14200.0],
        "sensor_temp": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 48.5],
    }
    sensor = SensorData.from_dict(raw)
    assert sensor.last_update == "2026-08-13 20:00:00"
    assert "custom_ambient_temp" in sensor.sensors
    assert sensor.raw_user == [0, 50.0, 14.2, -2.5, 75.0, 25.0, 180.0, 20.1, 19.8, 14200.0]
    assert sensor.raw_temp == [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 48.5]
    assert sensor.raw_data == raw
    # Normalized fields extracted from raw_user / raw_temp slots
    assert sensor.dew_heater == 50.0
    assert sensor.dew_point == 14.2
    assert sensor.frost_point == -2.5
    assert sensor.fan_duty_cycle == 75.0
    assert sensor.heat_index == 25.0
    assert sensor.wind_direction == 180.0
    assert sensor.device_sqm == 20.1
    assert sensor.camera_sqm == 19.8
    assert sensor.camera_sqm_adu == 14200.0
    assert sensor.cpu_temperature == 48.5


def test_sensor_data_fallback_slots_and_cpu_temp():
    raw = {
        "sensors": {},
        "sensor_user": [0, 0, 12.3, 0, 0, 0, 0, 0, 0, 9999.0],
        "sensor_temp": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 62.4],
    }
    sensor = SensorData.from_dict(raw)
    assert sensor.dew_point == 12.3
    assert sensor.camera_sqm_adu == 9999.0
    assert sensor.cpu_temperature == 62.4


def test_media_data_from_dict():
    raw = {
        "filename": "timelapse.mp4",
        "dayDate": "2026-08-13",
        "night": True,
        "camera_id": 1,
        "id": 10,
    }
    media = MediaData.from_dict("timelapse", raw)
    assert media.media_type == "timelapse"
    assert media.filename == "timelapse.mp4"
    assert media.day_date == "2026-08-13"
    assert media.camera_id == 1
    assert media.id == 10
    assert media.raw_data == raw
