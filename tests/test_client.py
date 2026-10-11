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
