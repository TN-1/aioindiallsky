# aioindiallsky

Asynchronous Python client library for communicating with **indi-allsky** over HTTP and WebSocket event streams. Designed for Home Assistant custom components and Python automation scripts.

## Installation

```bash
pip install aioindiallsky
```

## Quick Start Example

```python
import asyncio
from aioindiallsky import IndiAllSkyClient, ExposureData, SensorData

async def main():
    async with IndiAllSkyClient(host="192.168.1.100", port=8080) as client:
        # Register event callbacks (returns an unregister function)
        async def on_exposure(exposure: ExposureData):
            print(f"New Exposure! File: {exposure.filename}, Duration: {exposure.exposure}s, SQM: {exposure.sqm}")
            # Fetch image bytes for Home Assistant Camera / Image entity
            image_bytes = await client.fetch_image(exposure.filename)
            print(f"Downloaded {len(image_bytes)} bytes")

        def on_sensors(sensors: SensorData):
            print("Sensor Update:")
            for key, info in sensors.sensors.items():
                print(f"  {info['name']}: {info['value']} {info['unit']}")

        unsub_exposure = client.register_callback("exposure_complete", on_exposure)
        unsub_sensors = client.register_callback("sensor_update", on_sensors)

        # Connect and start listener
        await client.connect()
        try:
            await client.listen()
        finally:
            unsub_exposure()
            unsub_sensors()

if __name__ == "__main__":
    asyncio.run(main())
```

## Image & Media API

* `await client.fetch_image(filename)`: Fetch raw binary image bytes (JPEG/PNG) for a given filename or relative path. Perfect for Home Assistant `ImageEntity` or `Camera` snapshot methods.
* `await client.fetch_latest_image()`: Fetch raw binary bytes for the latest static snapshot (`public/latest.jpg`).
* `client.get_image_url(filename)`: Generate the full HTTP URL for an image filename.

## Supported Commands

* `client.pause()`: Pause image capture loop
* `client.unpause()`: Resume image capture loop
* `client.reboot()`: Reboot host system
* `client.shutdown()`: Shutdown host system
* `client.restart_service(service_name)`: Restart service (`indi-allsky`, `indiserver`, `gunicorn`)
* `client.generate_keogram()`: Trigger keogram compilation
* `client.generate_timelapse()`: Trigger timelapse compilation
* `client.generate_startrail()`: Trigger star trail compilation
* `client.trigger_darks()`: Initiate dark frame capture sequence
