"""Camera platform for Bermuda floor plan."""

from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING

from homeassistant.components.camera import Camera
from PIL import Image, ImageDraw

from .const import (
    CONF_DEVICE_COORDS,
    CONF_ENABLE_TRIANGULATION,
    CONF_FLOORPLAN_IMAGE,
    CONF_SCANNER_COORDS,
    DEFAULT_ENABLE_TRIANGULATION,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from . import BermudaConfigEntry
    from .coordinator import BermudaDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: BermudaConfigEntry, async_add_entities) -> None:
    """Set up camera platform."""
    coordinator: BermudaDataUpdateCoordinator = entry.runtime_data.coordinator
    async_add_entities([BermudaFloorPlanCamera(coordinator, entry)])


class BermudaFloorPlanCamera(Camera):
    """Camera entity showing device positions on the floor plan."""

    def __init__(self, coordinator: BermudaDataUpdateCoordinator, entry: BermudaConfigEntry) -> None:
        super().__init__()
        self.coordinator = coordinator
        self.entry = entry

    @property
    def name(self) -> str:
        return "Bermuda Floor Plan"

    async def async_camera_image(self) -> bytes | None:
        """Return camera image."""
        image_path = self.entry.options.get(CONF_FLOORPLAN_IMAGE)
        if not image_path:
            return None
        path = Path(image_path)
        if not path.exists():
            return None
        data = await self.coordinator.hass.async_add_executor_job(path.read_bytes)
        base = Image.open(io.BytesIO(data)).convert("RGBA")
        draw = ImageDraw.Draw(base)
        scanner_coords = self.entry.options.get(CONF_SCANNER_COORDS, {})
        for coords in scanner_coords.values():
            if isinstance(coords, list | tuple) and len(coords) >= 2:
                x, y = float(coords[0]), float(coords[1])
                draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=(0, 0, 255, 192))
        device_coords = self.entry.options.get(CONF_DEVICE_COORDS, {})
        for coords in device_coords.values():
            if isinstance(coords, list | tuple) and len(coords) >= 2:
                x, y = float(coords[0]), float(coords[1])
                draw.rectangle((x - 3, y - 3, x + 3, y + 3), fill=(255, 0, 0, 192))
        if self.entry.options.get(CONF_ENABLE_TRIANGULATION, DEFAULT_ENABLE_TRIANGULATION):
            for device in self.coordinator.devices.values():
                if device.coord_x is not None and device.coord_y is not None:
                    x, y = device.coord_x, device.coord_y
                    draw.rectangle((x - 2, y - 2, x + 2, y + 2), fill=(0, 255, 0, 192))
        out = io.BytesIO()
        base.save(out, format="PNG")
        return out.getvalue()
