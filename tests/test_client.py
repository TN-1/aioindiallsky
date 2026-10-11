"""Tests for aioindiallsky client."""
import asyncio
import ssl
import pytest
import aiohttp
from unittest.mock import AsyncMock, MagicMock, patch

from aioindiallsky import (
    IndiAllSkyClient,
    IndiAllSkyConnectionError,
    IndiAllSkyCommandError,
    ExposureData,
    SensorData,
)


@pytest.mark.asyncio
async def test_client_init_and_url_building(client):
    assert client.base_url == "http://127.0.0.1:8080/indi-allsky"
    # Public properties are clean without credentials
    assert client.events_url == "ws://127.0.0.1:8080/indi-allsky/ws/events"
    assert client.control_url == "ws://127.0.0.1:8080/indi-allsky/ws/control"
    # Private API key is stored securely in private attribute
    assert client._api_key == "test_api_key"
    # Connection URLs append credential privately
    assert "test_api_key" in client._get_events_ws_url()
    assert "test_api_key" in client._get_control_ws_url()


@pytest.mark.asyncio
async def test_get_image_url(client):
    url = client.get_image_url("public/latest.jpg")
    assert url == "http://127.0.0.1:8080/indi-allsky/public/latest.jpg?api_key=test_api_key"

    full_url = client.get_image_url("https://example.com/image.jpg")
    assert full_url == "https://example.com/image.jpg"


@pytest.mark.asyncio
async def test_ipv6_url_building():
    client_ipv6 = IndiAllSkyClient(host="2001:db8::1", port=8080, api_key="test_key")
    assert client_ipv6.base_url == "http://[2001:db8::1]:8080/indi-allsky"
    assert client_ipv6.events_url == "ws://[2001:db8::1]:8080/indi-allsky/ws/events"
    assert client_ipv6.control_url == "ws://[2001:db8::1]:8080/indi-allsky/ws/control"

    # Already bracketed IPv6
    client_bracketed = IndiAllSkyClient(host="[2001:db8::1]", port=443, ssl=True)
    assert client_bracketed.base_url == "https://[2001:db8::1]:443/indi-allsky"
    assert client_bracketed.events_url == "wss://[2001:db8::1]:443/indi-allsky/ws/events"
    assert client_bracketed.control_url == "wss://[2001:db8::1]:443/indi-allsky/ws/control"


@pytest.mark.asyncio
async def test_fetch_image_success():
    client = IndiAllSkyClient(host="127.0.0.1")
    fake_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF"  # JPEG magic header

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.read.return_value = fake_bytes
    mock_response.raise_for_status = MagicMock()

    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_response
    mock_context.__aexit__.return_value = None

    mock_session = MagicMock()
    mock_session.get.return_value = mock_context

    with patch.object(client, "_get_session", return_value=mock_session):
        data = await client.fetch_image("public/latest.jpg")
        assert data == fake_bytes

        latest_data = await client.fetch_latest_image()
        assert latest_data == fake_bytes


@pytest.mark.asyncio
async def test_custom_ssl_context_support():
    custom_ssl = ssl.create_default_context()
    client = IndiAllSkyClient(host="127.0.0.1", ssl=custom_ssl)
    assert client.ssl == custom_ssl
    assert client.events_url.startswith("wss://")


@pytest.mark.asyncio
async def test_async_context_manager():
    client = IndiAllSkyClient(host="127.0.0.1")
    async with client as c:
        assert c is client
    assert client._running is False
    assert client._ws_events is None


@pytest.mark.asyncio
async def test_callback_registration_and_unregistration(client):
    received = []

    def on_exposure(data):
        received.append(data)

    with pytest.raises(ValueError, match="Invalid event_type"):
        client.register_callback("invalid_event_name", on_exposure)

    unregister = client.register_callback("exposure_complete", on_exposure)
    assert len(client._callbacks["exposure_complete"]) == 1

    payload = {"event": "exposure_complete", "data": {"filename": "test.jpg", "exposure": 2.0}}
    await client._handle_event(payload)
    assert len(received) == 1
    assert isinstance(received[0], ExposureData)
    assert received[0].filename == "test.jpg"

    # Double unregister is safe
    unregister()
    unregister()
    assert len(client._callbacks["exposure_complete"]) == 0


@pytest.mark.asyncio
async def test_async_and_all_callbacks():
    client = IndiAllSkyClient(host="127.0.0.1")
    async_received = []
    all_received = []

    async def async_cb(data):
        async_received.append(data)

    def all_cb(event_name, data):
        all_received.append((event_name, data))

    client.register_callback("sensor_update", async_cb)
    client.register_callback("all", all_cb)

    payload = {
        "event": "sensor_update",
        "data": {"last_update": "now", "sensors": {"temp": 20}},
    }
    await client._handle_event(payload)

    assert len(async_received) == 1
    assert isinstance(async_received[0], SensorData)
    assert len(all_received) == 1
    assert all_received[0][0] == "sensor_update"


@pytest.mark.asyncio
async def test_send_command_success(client):
    mock_ws = AsyncMock()
    mock_ws.closed = False
    client._ws_control = mock_ws

    result = await client.pause()
    assert result is True
    mock_ws.send_str.assert_called_once()
    assert '"action": "pause"' in mock_ws.send_str.call_args[0][0]


@pytest.mark.asyncio
async def test_send_command_failure_raises_exception(client):
    mock_ws = AsyncMock()
    mock_ws.closed = False
    mock_ws.send_str.side_effect = Exception("WS send error")
    client._ws_control = mock_ws

    with pytest.raises(IndiAllSkyCommandError, match="Failed sending command"):
        await client.pause()


@pytest.mark.asyncio
async def test_send_query_fallback(client):
    mock_ws_events = AsyncMock()
    mock_ws_events.closed = False
    client._ws_events = mock_ws_events

    # Uses events WS if open
    res = await client.fetch_sensors()
    assert res is True
    mock_ws_events.send_str.assert_called_once()
    assert '"action": "get_sensors"' in mock_ws_events.send_str.call_args[0][0]


@pytest.mark.asyncio
async def test_credentials_redacted_in_logs(caplog):
    client = IndiAllSkyClient(host="127.0.0.1", api_key="SUPER_SECRET_KEY")
    mock_session = AsyncMock()
    mock_ws = AsyncMock()
    mock_ws.closed = False
    mock_session.ws_connect.return_value = mock_ws

    with patch.object(client, "_get_session", return_value=mock_session):
        with caplog.at_level("INFO"):
            await client.connect()

    assert "SUPER_SECRET_KEY" not in caplog.text
    assert "Connected to indi-allsky events WebSocket at 127.0.0.1:8080" in caplog.text


@pytest.mark.asyncio
async def test_disconnect_clears_references_and_session():
    mock_session = AsyncMock()
    mock_session.closed = False

    client = IndiAllSkyClient(host="127.0.0.1", session=mock_session)
    mock_ws_events = AsyncMock()
    mock_ws_events.closed = False
    client._ws_events = mock_ws_events

    await client.disconnect()
    mock_ws_events.close.assert_called_once()
    assert client._ws_events is None
    # External session must NOT be closed
    mock_session.close.assert_not_called()


@pytest.mark.asyncio
async def test_is_connected_properties(client):
    assert client.is_connected is False
    assert client.is_control_connected is False

    mock_ws_events = AsyncMock()
    mock_ws_events.closed = False
    client._ws_events = mock_ws_events
    client._running = True
    assert client.is_connected is True

    mock_ws_control = AsyncMock()
    mock_ws_control.closed = False
    client._ws_control = mock_ws_control
    assert client.is_control_connected is True


@pytest.mark.asyncio
async def test_login_success():
    client = IndiAllSkyClient(
        host="127.0.0.1", username="admin", password="password123"
    )
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()

    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_response
    mock_context.__aexit__.return_value = None

    mock_session = MagicMock()
    mock_session.post.return_value = mock_context

    with patch.object(client, "_get_session", return_value=mock_session):
        assert await client.login() is True
        assert client._logged_in is True
        mock_session.post.assert_called_once_with(
            "http://127.0.0.1:8080/indi-allsky/login",
            json={"USERNAME": "admin", "PASSWORD": "password123", "NEXT": ""},
            ssl=False,
        )


@pytest.mark.asyncio
async def test_login_failure():
    from aioindiallsky import IndiAllSkyAuthError

    client = IndiAllSkyClient(
        host="127.0.0.1", username="admin", password="wrongpassword"
    )
    mock_response = AsyncMock()
    mock_response.status = 400
    mock_response.json = AsyncMock(
        return_value={"form_global": ["Invalid username or password"]}
    )

    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_response
    mock_context.__aexit__.return_value = None

    mock_session = MagicMock()
    mock_session.post.return_value = mock_context

    with patch.object(client, "_get_session", return_value=mock_session):
        with pytest.raises(IndiAllSkyAuthError, match="Invalid username or password"):
            await client.login()
        assert client._logged_in is False


@pytest.mark.asyncio
async def test_post_json_success():
    client = IndiAllSkyClient(host="127.0.0.1", api_key="secret123")
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"result": "ok", "items": [1, 2, 3]})

    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_response
    mock_context.__aexit__.return_value = None

    mock_session = MagicMock()
    mock_session.post.return_value = mock_context

    with patch.object(client, "_get_session", return_value=mock_session):
        res = await client.post_json("ajax/test", {"test": 1})
        assert res == {"result": "ok", "items": [1, 2, 3]}
        mock_session.post.assert_called_once_with(
            "http://127.0.0.1:8080/indi-allsky/ajax/test?api_key=secret123",
            json={"test": 1},
            headers={
                "Referer": "http://127.0.0.1:8080/indi-allsky/",
                "X-Requested-With": "XMLHttpRequest",
            },
            ssl=False,
        )


@pytest.mark.asyncio
async def test_post_json_auth_error():
    from aioindiallsky import IndiAllSkyAuthError

    client = IndiAllSkyClient(host="127.0.0.1")
    mock_response = AsyncMock()
    mock_response.status = 401
    mock_response.raise_for_status = MagicMock()

    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_response
    mock_context.__aexit__.return_value = None

    mock_session = MagicMock()
    mock_session.post.return_value = mock_context

    with patch.object(client, "_get_session", return_value=mock_session):
        with pytest.raises(IndiAllSkyAuthError, match="Authentication failed"):
            await client.post_json("ajax/test", {})


@pytest.mark.asyncio
async def test_get_video_years():
    client = IndiAllSkyClient(host="127.0.0.1")
    html_page = """
    <html><body>
    <select id="YEAR_SELECT"><option value="2026">2026</option><option value="2025">2025</option></select>
    </body></html>
    """
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.text = AsyncMock(return_value=html_page)

    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_response
    mock_context.__aexit__.return_value = None

    mock_session = MagicMock()
    mock_session.get.return_value = mock_context

    with patch.object(client, "_get_session", return_value=mock_session):
        years = await client.get_video_years()
        assert years == [2026, 2025]


@pytest.mark.asyncio
async def test_get_image_years():
    client = IndiAllSkyClient(host="127.0.0.1")
    mock_catalog = {
        "YEAR_SELECT": [[2026, "2026"], [2025, "2025"]],
    }
    with patch.object(client, "get_image_catalog", AsyncMock(return_value=mock_catalog)):
        years = await client.get_image_years(camera_id=1)
        assert years == [2026, 2025]


@pytest.mark.asyncio
async def test_get_video_catalog():
    client = IndiAllSkyClient(host="127.0.0.1")
    expected_data = {
        "YEAR_SELECT": 2026,
        "MONTH_SELECT": 10,
        "video_list": [{"url": "videos/20261011_night.mp4", "night": True}],
    }

    with patch.object(client, "post_json", AsyncMock(return_value=expected_data)) as mock_post:
        result = await client.get_video_catalog(camera_id=1, year=2026, month=10, time_of_day="night")
        assert result == expected_data
        mock_post.assert_called_once_with(
            "ajax/videoviewer",
            {
                "CAMERA_ID": 1,
                "YEAR_SELECT": 2026,
                "MONTH_SELECT": 10,
                "TIMEOFDAY_SELECT": "night",
            },
        )


@pytest.mark.asyncio
async def test_get_image_catalog():
    client = IndiAllSkyClient(host="127.0.0.1")
    expected_data = {
        "IMAGE_DATA": [{"url": "images/20261011/img01.jpg"}],
    }

    with patch.object(client, "post_json", AsyncMock(return_value=expected_data)) as mock_post:
        result = await client.get_image_catalog(
            camera_id=0, year=2026, month=10, day=11, hour=21, filter_detections=True
        )
        assert result == expected_data
        mock_post.assert_called_once_with(
            "ajax/imageviewer",
            {
                "CAMERA_ID": 0,
                "YEAR_SELECT": 2026,
                "MONTH_SELECT": 10,
                "DAY_SELECT": 11,
                "HOUR_SELECT": 21,
                "FILTER_DETECTIONS": True,
            },
        )


@pytest.mark.asyncio
async def test_get_video_months_and_videos():
    client = IndiAllSkyClient(host="127.0.0.1")
    mock_catalog = {
        "MONTH_SELECT": [[10, "October"], [9, "September"]],
        "video_list": [
            {
                "id": 100,
                "url": "images/test/timelapse.mp4",
                "dayDate": "20261011",
                "dayDate_long": "October 11, 2026",
                "night": True,
                "success": True,
                "keogram": "images/test/keogram.jpg",
                "startrail": "images/test/startrail.jpg",
                "avg_stars": 42,
            }
        ],
    }
    with patch.object(client, "get_video_catalog", AsyncMock(return_value=mock_catalog)):
        months = await client.get_video_months(year=2026, camera_id=1)
        assert len(months) == 2
        assert months[0].month == 10
        assert months[0].name == "October"

        videos = await client.get_videos(year=2026, month=10, camera_id=1)
        assert len(videos) == 1
        assert videos[0].id == 100
        assert videos[0].mime_type == "video/mp4"
        assert videos[0].keogram_url == "images/test/keogram.jpg"
        assert videos[0].avg_stars == 42


@pytest.mark.asyncio
async def test_get_image_helpers():
    client = IndiAllSkyClient(host="127.0.0.1")
    mock_catalog = {
        "MONTH_SELECT": [[10, "October"]],
        "DAY_SELECT": [[11, "11"], [10, "10"]],
        "HOUR_SELECT": [[20, "20"], [19, "19"]],
        "IMAGE_DATA": [
            {
                "id": 200,
                "url": "images/test/img01.jpg",
                "ts": 1791710881,
                "date": "20:00:00",
                "width": 4056,
                "height": 3140,
            }
        ],
    }
    with patch.object(client, "get_image_catalog", AsyncMock(return_value=mock_catalog)):
        months = await client.get_image_months(year=2026, camera_id=1)
        assert len(months) == 1
        assert months[0].month == 10

        days = await client.get_image_days(year=2026, month=10, camera_id=1)
        assert days == [11, 10]

        hours = await client.get_image_hours(year=2026, month=10, day=11, camera_id=1)
        assert hours == [20, 19]

        images = await client.get_images(year=2026, month=10, day=11, hour=20, camera_id=1)
        assert len(images) == 1
        assert images[0].id == 200
        assert images[0].mime_type == "image/jpeg"
        assert images[0].width == 4056



