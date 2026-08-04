# custom_components/geozones/__init__.py
"""The GeoZones Component initialization runtime orchestration module."""

from datetime import datetime
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .const import (
    CONF_GEOJSON_SOURCE,
    CONF_SOURCE_TRACKER,
    CONF_USE_CUSTOM_ZONES,
    DEFAULT_USE_CUSTOM_ZONES,
    DOMAIN,
)
from .dashboard import async_remove_dashboard, async_setup_dashboard
from .utils import (
    async_add_custom_zone,
    async_ensure_custom_zones_file,
    async_remove_custom_zone,
    async_rename_custom_zone,
    fetch_and_process_geojson,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [
    Platform.DEVICE_TRACKER,
    Platform.BUTTON,
    Platform.SELECT,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def _get_active_select_zone_name(hass: HomeAssistant) -> str | None:
    """Extract selected zone name from any registered GeoZones select entity."""
    for state in hass.states.async_all("select"):
        if (
            state.entity_id.startswith("select.geozones_")
            and state.state not in (None, "unknown", "unavailable")
        ):
            return state.state
    return None


async def _async_reprocess_all_entries(hass: HomeAssistant) -> None:
    """Reprocess all active GeoZones config entries and notify listening entities."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        source_tracker = entry.data[CONF_SOURCE_TRACKER]
        geojson_source = entry.data[CONF_GEOJSON_SOURCE]
        use_custom = entry.data.get(CONF_USE_CUSTOM_ZONES, DEFAULT_USE_CUSTOM_ZONES)
        entity_id_slug = source_tracker.split(".")[-1]

        path = await fetch_and_process_geojson(
            hass, geojson_source, entity_id_slug, use_custom
        )
        if path:
            async_dispatcher_send(hass, f"{DOMAIN}_reload_{entry.entry_id}")


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the GeoZones component domain and register custom actions."""
    await async_ensure_custom_zones_file(hass)

    async def handle_add_zone(call: ServiceCall) -> None:
        """Handle the add_zone custom service execution."""
        name: str | None = call.data.get("name")
        radius: float = float(call.data.get("radius", 50.0))
        lat: float | None = call.data.get("latitude")
        lon: float | None = call.data.get("longitude")
        entity_id: str | None = call.data.get("entity_id")

        if not name:
            name = f"Marked Spot {dt_util.now().strftime('%Y-%m-%d %H:%M')}"

        if lat is None or lon is None:
            if not entity_id:
                raise ServiceValidationError(
                    "You must provide either latitude and longitude coordinates, or a valid device_tracker entity_id."
                )
            state = hass.states.get(entity_id)
            if state is None:
                raise ServiceValidationError(
                    f"Target entity {entity_id} was not found."
                )
            lat = state.attributes.get("latitude")
            lon = state.attributes.get("longitude")
            if lat is None or lon is None:
                raise ServiceValidationError(
                    f"Target entity {entity_id} does not currently have valid latitude and longitude attributes."
                )

        await async_add_custom_zone(hass, name, float(lat), float(lon), float(radius))
        await _async_reprocess_all_entries(hass)

    async def handle_remove_zone(call: ServiceCall) -> None:
        """Handle the remove_zone custom service execution."""
        name: str | None = call.data.get("name")

        if not name:
            name = _get_active_select_zone_name(hass)

        if not name:
            raise ServiceValidationError(
                "Zone name was not specified and no custom zone is currently selected in the dropdown."
            )

        removed = await async_remove_custom_zone(hass, name)
        if not removed:
            _LOGGER.warning(
                "Zone '%s' was not found in the custom zones file or belongs to a read-only source file",
                name,
            )
            return
        await _async_reprocess_all_entries(hass)

    async def handle_rename_zone(call: ServiceCall) -> None:
        """Handle the rename_zone custom service execution."""
        name: str | None = call.data.get("name")
        new_name: str = call.data["new_name"]

        if not name:
            name = _get_active_select_zone_name(hass)

        if not name:
            raise ServiceValidationError(
                "Target zone name was not specified and no custom zone is currently selected in the dropdown."
            )

        renamed = await async_rename_custom_zone(hass, name, new_name)
        if not renamed:
            _LOGGER.warning(
                "Zone '%s' was not found in the custom zones file or belongs to a read-only source file",
                name,
            )
            return
        await _async_reprocess_all_entries(hass)

    async def handle_reload(call: ServiceCall) -> None:
        """Handle the reload custom service execution."""
        await _async_reprocess_all_entries(hass)

    hass.services.async_register(
        DOMAIN,
        "add_zone",
        handle_add_zone,
        schema=vol.Schema(
            {
                vol.Optional("name"): cv.string,
                vol.Optional("entity_id"): cv.entity_id,
                vol.Optional("latitude"): vol.Coerce(float),
                vol.Optional("longitude"): vol.Coerce(float),
                vol.Optional("radius", default=50.0): vol.Coerce(float),
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        "remove_zone",
        handle_remove_zone,
        schema=vol.Schema({vol.Optional("name"): cv.string}),
    )

    hass.services.async_register(
        DOMAIN,
        "rename_zone",
        handle_rename_zone,
        schema=vol.Schema(
            {
                vol.Optional("name"): cv.string,
                vol.Required("new_name"): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        "reload",
        handle_reload,
        schema=vol.Schema({}),
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Establish entity entries from active config payload structures."""
    hass.data.setdefault(DOMAIN, {})

    await async_ensure_custom_zones_file(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if not hass.data[DOMAIN].get("panel_registered"):
        hass.data[DOMAIN]["panel_registered"] = True
        try:
            await async_setup_dashboard(hass)
        except ValueError:
            _LOGGER.debug("GeoZones panel already registered")
        except OSError as err:
            hass.data[DOMAIN]["panel_registered"] = False
            _LOGGER.error("Failed to register GeoZones panel: %s", err)

    async def nightly_refresh_callback(now: datetime) -> None:
        """Automated scheduled update tracking execution pass handle context."""
        _LOGGER.info("Starting scheduled nightly update sweep for GeoZones structures")
        source_tracker = entry.data[CONF_SOURCE_TRACKER]
        geojson_source = entry.data[CONF_GEOJSON_SOURCE]
        use_custom = entry.data.get(CONF_USE_CUSTOM_ZONES, DEFAULT_USE_CUSTOM_ZONES)
        entity_id_slug = source_tracker.split(".")[-1]

        path = await fetch_and_process_geojson(
            hass, geojson_source, entity_id_slug, use_custom
        )

        if path:
            async_dispatcher_send(hass, f"{DOMAIN}_reload_{entry.entry_id}")

    unsub_timer = async_track_time_change(
        hass, nightly_refresh_callback, hour=2, minute=37, second=0
    )

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

    if unload_ok:
        remaining_entries = [
            e
            for e in hass.config_entries.async_entries(DOMAIN)
            if e.entry_id != entry.entry_id
        ]
        if not remaining_entries and hass.data[DOMAIN].get("panel_registered"):
            await async_remove_dashboard(hass)
            hass.data[DOMAIN]["panel_registered"] = False

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Force a complete thread-safe reload cycle sequence when settings are adjusted."""
    _LOGGER.info("Reconfiguration detected. Reloading GeoZones instance")
    await hass.config_entries.async_reload(entry.entry_id)
