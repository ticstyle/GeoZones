"""Config flow framework implementation details for GeoZones handling setups."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import entity_registry as er

from .const import CONF_GEOJSON_SOURCE, CONF_SOURCE_TRACKER, DOMAIN
from .utils import fetch_and_process_geojson

_LOGGER = logging.getLogger(__name__)


class GeoZonesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle creation process logic for new GeoZones tracker entity targets."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle initial step workflow data collection inputs."""
        errors: dict[str, str] = {}

        if user_input is not None:
            source_tracker = user_input[CONF_SOURCE_TRACKER]
            geojson_source = user_input[CONF_GEOJSON_SOURCE]

            # Construct unique identifier key mapping details matching raw device tracker string base
            entity_id_slug = source_tracker.split(".")[-1]

            # Run sorting and download routines dynamically during confirmation setup loop sequence
            processed_path = await fetch_and_process_geojson(
                self.hass, geojson_source, entity_id_slug
            )

            if processed_path is None:
                errors["base"] = "processing_failed"
                _LOGGER.warning("Could not setup entry due to data processing errors")
            else:
                await self.async_set_unique_id(f"geozones_{entity_id_slug}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"GeoZones {entity_id_slug}",
                    data={
                        CONF_SOURCE_TRACKER: source_tracker,
                        CONF_GEOJSON_SOURCE: geojson_source,
                    },
                )

        # Build dynamic list containing available option trackers from existing entity registry maps
        entity_registry = er.async_get(self.hass)
        trackers = [
            entity.entity_id
            for entity in entity_registry.entities.values()
            if entity.domain == "device_tracker"
        ]

        # Add fallback tracker entries from state space engine registry tracking records
        state_trackers = self.hass.states.async_entity_ids("device_tracker")
        all_trackers = sorted(list(set(trackers + state_trackers)))

        data_schema = vol.Schema(
            {
                vol.Required(CONF_SOURCE_TRACKER): vol.In(all_trackers),
                vol.Required(CONF_GEOJSON_SOURCE): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)
