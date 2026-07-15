"""The GeoZones Component initialization runtime orchestration module."""

from datetime import datetime
import logging
import os
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_change

from .const import CONF_GEOJSON_SOURCE, CONF_SOURCE_TRACKER, DOMAIN, STORAGE_DIR
from .utils import fetch_and_process_geojson

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER]

# Tell Hassfest that YAML configurations are not supported for this domain
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the GeoZones component domain and ensure storage folder exists."""
    target_dir = hass.config.path(STORAGE_DIR)

    def _ensure_directory() -> None:
        """Ensure storage directory exists on disk without raising existing folder errors."""
        os.makedirs(target_dir, exist_ok=True)

    await hass.async_add_executor_job(_ensure_directory)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Establish entity entries from active config payload structures."""
    hass.data.setdefault(DOMAIN, {})

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def nightly_refresh_callback(now: datetime) -> None:
        """Automated scheduled update tracking execution pass handle context."""
        _LOGGER.info("Starting scheduled nightly update sweep for GeoZones structures")
        source_tracker = entry.data[CONF_SOURCE_TRACKER]
        geojson_source = entry.data[CONF_GEOJSON_SOURCE]
        entity_id_slug = source_tracker.split(".")[-1]

        path = await fetch_and_process_geojson(hass, geojson_source, entity_id_slug)

        if path:
            async_dispatcher_send(hass, f"{DOMAIN}_reload_{entry.entry_id}")

    unsub_timer = async_track_time_change(
        hass, nightly_refresh_callback, hour=2, minute=37, second=0
    )

    # Attach update listener to handle instant container reloads when options change
    unsub_options = entry.add_update_listener(async_reload_entry)

    hass.data[DOMAIN][entry.entry_id] = (unsub_timer, unsub_options)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Gracefully dismantle elements when entries are removed or modified."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok and entry.entry_id in hass.data[DOMAIN]:
        unsub_timer, unsub_options = hass.data[DOMAIN].pop(entry.entry_id)
        unsub_timer()
        unsub_options()

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Force a complete thread-safe reload cycle sequence when settings are adjusted."""
    _LOGGER.info("Reconfiguration detected. Reloading GeoZones instance")
    await hass.config_entries.async_reload(entry.entry_id)
