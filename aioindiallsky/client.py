"""Async Client for indi-allsky WebSocket API."""
import asyncio
import inspect
import json
import logging
import ssl as ssl_module
import sys
import types
from typing import Callable, Optional, Dict, Any, List, Union, Type

import aiohttp

from .exceptions import (
    IndiAllSkyConnectionError,
    IndiAllSkyTimeoutError,
    IndiAllSkyAuthError,
    IndiAllSkyCommandError,
)
from .models import ExposureData, SensorData, MediaData

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10.0


class IndiAllSkyClient:
    """Async Client for communicating with indi-allsky over HTTP and WebSocket endpoints."""

    def __init__(
        self,
        host: str,
        port: int = 8080,
        ssl: Union[bool, ssl_module.SSLContext] = False,
        api_key: Optional[str] = None,
        session: Optional[aiohttp.ClientSession] = None,
        request_timeout: float = DEFAULT_TIMEOUT,
    ):
        self.host = host
        self.port = port
        self.ssl = ssl
        self._api_key = api_key
        self.request_timeout = request_timeout
        
        protocol = "https" if ssl else "http"
        self.base_url = f"{protocol}://{host}:{port}/indi-allsky"

        self._session = session
        self._owned_session = False
        self._ws_events: Optional[aiohttp.ClientWebSocketResponse] = None
        self._ws_control: Optional[aiohttp.ClientWebSocketResponse] = None
        self._running = False
        self._callbacks: Dict[str, List[Callable[..., Any]]] = {
            "exposure_complete": [],
            "sensor_update": [],
            "timelapse_complete": [],
            "keogram_complete": [],
            "startrail_complete": [],
            "command_result": [],
            "all": [],
        }

    @property
    def events_url(self) -> str:
        """Get the clean public WebSocket events URL (without credentials)."""
        ws_protocol = "wss" if self.ssl else "ws"
        return f"{ws_protocol}://{self.host}:{self.port}/indi-allsky/ws/events"

    @property
    def control_url(self) -> str:
        """Get the clean public WebSocket control URL (without credentials)."""
        ws_protocol = "wss" if self.ssl else "ws"
        return f"{ws_protocol}://{self.host}:{self.port}/indi-allsky/ws/control"

    @property
    def is_connected(self) -> bool:
        """Return True if the events WebSocket connection is active."""
        return self._running and self._ws_events is not None and not self._ws_events.closed

    @property
    def is_control_connected(self) -> bool:
        """Return True if the control WebSocket connection is active."""
        return self._ws_control is not None and not self._ws_control.closed

    def _get_events_ws_url(self) -> str:
        url = self.events_url
        if self._api_key:
            url += f"?api_key={self._api_key}"
        return url

    def _get_control_ws_url(self) -> str:
        url = self.control_url
        if self._api_key:
            url += f"?api_key={self._api_key}"
        return url

    def get_image_url(self, path_or_filename: str) -> str:
        """Get the full HTTP URL for an image or static asset."""
        if path_or_filename.startswith("http://") or path_or_filename.startswith("https://"):
            return path_or_filename

        clean_path = path_or_filename.lstrip("/")
        url = f"{self.base_url}/{clean_path}"
        if self._api_key:
            url += f"?api_key={self._api_key}"
        return url

    async def fetch_image(self, path_or_filename: str) -> bytes:
        """Fetch raw binary image bytes (JPEG/PNG) for a given image file or path."""
        session = await self._get_session()
        url = self.get_image_url(path_or_filename)
        try:
            async with asyncio.timeout(self.request_timeout):
                async with session.get(url, ssl=self.ssl) as resp:
                    if resp.status in (401, 403):
                        raise IndiAllSkyAuthError(f"Authentication failed fetching image '{path_or_filename}': HTTP {resp.status}")
                    resp.raise_for_status()
                    return await resp.read()
        except IndiAllSkyAuthError:
            raise
        except TimeoutError as e:
            raise IndiAllSkyTimeoutError(f"Timeout fetching image '{path_or_filename}'") from e
        except Exception as e:
            raise IndiAllSkyConnectionError(f"Failed to fetch image '{path_or_filename}': {e}") from e

    async def fetch_latest_image(self) -> bytes:
        """Fetch raw binary bytes for the latest static snapshot image."""
        return await self.fetch_image("public/latest.jpg")

    async def __aenter__(self) -> "IndiAllSkyClient":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[types.TracebackType],
    ) -> None:
        await self.disconnect()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owned_session = True
        return self._session

    def register_callback(
        self, event_type: str, callback: Callable[..., Any]
    ) -> Callable[[], None]:
        """Register a callback for a specific event type. Returns an unregister function."""
        if event_type not in self._callbacks:
            valid_events = list(self._callbacks.keys())
            raise ValueError(f"Invalid event_type '{event_type}'. Supported events: {valid_events}")
        
        target_list = self._callbacks[event_type]
        target_list.append(callback)

        def unregister() -> None:
            if callback in target_list:
                target_list.remove(callback)

        return unregister

    async def connect(self) -> None:
        """Connect to the indi-allsky read-only WebSocket event stream (/ws/events)."""
        session = await self._get_session()
        try:
            async with asyncio.timeout(self.request_timeout):
                self._ws_events = await session.ws_connect(
                    self._get_events_ws_url(), ssl=self.ssl
                )
            self._running = True
            logger.info("Connected to indi-allsky events WebSocket at %s:%s", self.host, self.port)
        except TimeoutError as e:
            raise IndiAllSkyTimeoutError(f"Timeout connecting to events stream at {self.host}:{self.port}") from e
        except aiohttp.ClientResponseError as e:
            if e.status in (401, 403):
                raise IndiAllSkyAuthError(f"Authentication failed for events stream: {e}") from e
            raise IndiAllSkyConnectionError(f"Connection failed to events stream: {e}") from e
        except Exception as e:
            raise IndiAllSkyConnectionError(f"Failed connecting to WS events: {e}") from e

    async def connect_control(self) -> None:
        """Connect to the authenticated control WebSocket (/ws/control)."""
        if self._ws_control and not self._ws_control.closed:
            return

        session = await self._get_session()
        try:
            async with asyncio.timeout(self.request_timeout):
                self._ws_control = await session.ws_connect(
                    self._get_control_ws_url(), ssl=self.ssl
                )
            logger.info("Connected to indi-allsky control WebSocket at %s:%s", self.host, self.port)
        except TimeoutError as e:
            raise IndiAllSkyTimeoutError(f"Timeout connecting to control endpoint at {self.host}:{self.port}") from e
        except aiohttp.ClientResponseError as e:
            if e.status in (401, 403):
                raise IndiAllSkyAuthError(f"Authentication failed for control endpoint: {e}") from e
            raise IndiAllSkyConnectionError(f"Connection failed to control endpoint: {e}") from e
        except Exception as e:
            raise IndiAllSkyConnectionError(f"Failed connecting to WS control: {e}") from e

    async def send_command(self, action: str, **kwargs: Any) -> bool:
        """Send a control command over the control WebSocket."""
        if not self._ws_control or self._ws_control.closed:
            await self.connect_control()

        if not self._ws_control or self._ws_control.closed:
            raise IndiAllSkyConnectionError("Control WebSocket connection is not active")

        command_payload = {"action": action, **kwargs}
        try:
            await self._ws_control.send_str(json.dumps(command_payload))
            return True
        except Exception as e:
            raise IndiAllSkyCommandError(f"Failed sending command '{action}': {e}") from e

    async def listen(
        self, auto_reconnect: bool = False, reconnect_delay: float = 5.0
    ) -> None:
        """Listen for incoming WebSocket events in a loop, optionally auto-reconnecting on disconnect."""
        while True:
            if self._ws_events is None or self._ws_events.closed:
                try:
                    await self.connect()
                except Exception as conn_err:
                    if auto_reconnect:
                        logger.warning("Failed connecting to WebSocket, retrying in %.1fs: %s", reconnect_delay, conn_err)
                        await asyncio.sleep(reconnect_delay)
                        continue
                    raise

            if self._ws_events is None:
                raise IndiAllSkyConnectionError("WebSocket event connection is not active")

            unexpected_close = False
            try:
                async for msg in self._ws_events:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        try:
                            data = json.loads(msg.data)
                            await self._handle_event(data)
                        except json.JSONDecodeError:
                            logger.warning("Received invalid JSON: %s", msg.data)
                    elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                        if self._running:
                            unexpected_close = True
                        break
            except Exception as e:
                logger.error("Error in WebSocket event listener: %s", e)
                if not auto_reconnect:
                    raise IndiAllSkyConnectionError(f"WebSocket listener error: {e}") from e
            finally:
                was_running = self._running
                self._running = False
                logger.info("WebSocket listener loop exited")
                if not auto_reconnect and was_running and unexpected_close and sys.exc_info()[1] is None:
                    raise IndiAllSkyConnectionError("WebSocket connection lost unexpectedly")

            if auto_reconnect:
                logger.info("Auto-reconnecting WebSocket in %.1f seconds...", reconnect_delay)
                await asyncio.sleep(reconnect_delay)
            else:
                break

    async def _handle_event(self, event_data: Dict[str, Any]) -> None:
        event_name = event_data.get("event")
        if not isinstance(event_name, str):
            return

        payload = event_data.get("data")
        payload_dict: Dict[str, Any] = payload if isinstance(payload, dict) else {}

        parsed_object: Any = payload_dict
        if event_name == "exposure_complete":
            parsed_object = ExposureData.from_dict(payload_dict)
        elif event_name == "sensor_update":
            parsed_object = SensorData.from_dict(payload_dict)
        elif event_name in ("timelapse_complete", "keogram_complete", "startrail_complete"):
            parsed_object = MediaData.from_dict(event_name.replace("_complete", ""), payload_dict)

        for cb in list(self._callbacks.get(event_name, [])):
            try:
                if inspect.iscoroutinefunction(cb):
                    await cb(parsed_object)
                else:
                    cb(parsed_object)
            except Exception as e:
                logger.error("Error in callback for %s: %s", event_name, e, exc_info=True)

        for cb in list(self._callbacks.get("all", [])):
            try:
                if inspect.iscoroutinefunction(cb):
                    await cb(event_name, parsed_object)
                else:
                    cb(event_name, parsed_object)
            except Exception as e:
                logger.error("Error in generic callback: %s", e, exc_info=True)

    async def send_query(self, action: str, **kwargs: Any) -> bool:
        """Send a read-only query command (e.g. get_sensors, get_status, ping) over events stream or control WS."""
        command_payload = {"action": action, **kwargs}
        payload_str = json.dumps(command_payload)

        # Prefer read-only event stream if already connected
        if self._ws_events and not self._ws_events.closed:
            try:
                await self._ws_events.send_str(payload_str)
                return True
            except Exception as e:
                logger.debug("Failed sending query over events WS: %s", e)

        return await self.send_command(action, **kwargs)

    async def fetch_sensors(self) -> bool:
        """Fetch real-time sensor dump over WebSocket (no control auth required)."""
        return await self.send_query("get_sensors")

    async def get_status(self) -> bool:
        """Fetch server status over WebSocket (no control auth required)."""
        return await self.send_query("get_status")

    async def ping(self) -> bool:
        """Ping server over WebSocket (no control auth required)."""
        return await self.send_query("ping")

    async def pause(self) -> bool:
        """Pause capture loop."""
        return await self.send_command("pause")

    async def unpause(self) -> bool:
        """Resume capture loop."""
        return await self.send_command("unpause")

    async def reboot(self) -> bool:
        """Reboot system host."""
        return await self.send_command("reboot")

    async def shutdown(self) -> bool:
        """Shutdown system host."""
        return await self.send_command("shutdown")

    async def restart_service(self, service: str = "indi-allsky") -> bool:
        """Restart a specific service (indi-allsky, indiserver, gunicorn)."""
        return await self.send_command("restart_service", service=service)

    async def restart_indiserver(self) -> bool:
        """Restart the indiserver driver service."""
        return await self.restart_service("indiserver")

    async def restart_allsky(self) -> bool:
        """Restart the main indi-allsky capture engine service."""
        return await self.restart_service("indi-allsky")

    async def restart_gunicorn(self) -> bool:
        """Restart the gunicorn web app server service."""
        return await self.restart_service("gunicorn")

    async def reload_config(self) -> bool:
        """Reload camera and system configuration."""
        return await self.send_command("reload_config")

    async def generate_keogram(self) -> bool:
        """Trigger keogram generation."""
        return await self.send_command("generate_keogram")

    async def generate_timelapse(self) -> bool:
        """Trigger timelapse generation."""
        return await self.send_command("generate_timelapse")

    async def generate_startrail(self) -> bool:
        """Trigger star trail generation."""
        return await self.send_command("generate_startrail")

    async def trigger_darks(self) -> bool:
        """Trigger dark frame acquisition."""
        return await self.send_command("trigger_darks")

    async def disconnect(self) -> None:
        """Close WebSocket and HTTP sessions cleanly."""
        self._running = False
        if self._ws_events and not self._ws_events.closed:
            await self._ws_events.close()
        self._ws_events = None

        if self._ws_control and not self._ws_control.closed:
            await self._ws_control.close()
        self._ws_control = None

        if self._owned_session and self._session and not self._session.closed:
            await self._session.close()
            self._session = None
            self._owned_session = False
        logger.info("Disconnected from indi-allsky")
