"""The GeoZones Component initialization runtime orchestration module."""

from datetime import datetime
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_change

from .const import CONF_GEOJSON_SOURCE, CONF_SOURCE_TRACKER, DOMAIN
from .utils import fetch_and_process_geojson

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER]


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

        # Download and clean up the file on the disk
        path = await fetch_and_process_geojson(hass, geojson_source, entity_id_slug)
        
        if path:
            # Signal the tracker entity to reload its memory cache safely
            async_dispatcher_send(hass, f"{DOMAIN}_reload_{entry.entry_id}")

    unsub_timer = async_track_time_change(
        hass, nightly_refresh_callback, hour=2, minute=37, second=0
    )
    hass.data[DOMAIN][entry.entry_id] = unsub_timer

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Gracefully dismantle elements when entries are removed or modified."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok and entry.entry_id in hass.data[DOMAIN]:
        unsub_timer = hass.data[DOMAIN].pop(entry.entry_id)
        unsub_timer()

    return unload_ok
