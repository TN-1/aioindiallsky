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
        "sensors": {"temp": {"name": "Temperature", "value": 22.5, "unit": "C"}},
        "sensor_user": [1, 2],
        "sensor_temp": [22.5],
    }
    sensor = SensorData.from_dict(raw)
    assert sensor.last_update == "2026-08-13 20:00:00"
    assert "temp" in sensor.sensors
    assert sensor.sensors["temp"]["value"] == 22.5
    assert sensor.raw_user == [1, 2]
    assert sensor.raw_data == raw


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
