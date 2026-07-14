"""Diagnostics support for GeoZones platform internal state verification."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import HomeAssistant

from .const import CONF_GEOJSON_SOURCE, CONF_SOURCE_TRACKER

# Sensitive configuration keys and attributes to scrub from logs
TO_REDACT = {
    "entry_id",
    "unique_id",
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_SOURCE_TRACKER,
    CONF_GEOJSON_SOURCE,
    "source_entity_id",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return sanitized system diagnostics for debugging integration configurations."""
    source_tracker = entry.data.get(CONF_SOURCE_TRACKER, "")
    entity_id_slug = source_tracker.split(".")[-1] if source_tracker else ""
    mirror_entity_id = f"device_tracker.geozones_{entity_id_slug}"

    # Extract current tracking entity state and attributes matrix safely
    mirror_state = hass.states.get(mirror_entity_id)
    mirror_data = {}

    if mirror_state:
        mirror_data = {
            "state": mirror_state.state,
            "attributes": dict(mirror_state.attributes),
        }

    diagnostics_data = {
        "config_entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "mirror_entity": async_redact_data(mirror_data, TO_REDACT),
    }

    return diagnostics_data
