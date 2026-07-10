"""Config flow framework implementation details for GeoZones handling setups."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    TextSelector,
)

from .const import CONF_GEOJSON_SOURCE, CONF_SOURCE_TRACKER, DOMAIN
from .utils import fetch_and_process_geojson

_LOGGER = logging.getLogger(__name__)


class GeoZonesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle creation process logic for new GeoZones tracker entity targets."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
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

        # Use clean selectors without passing forbidden config dictionary elements
        data_schema = vol.Schema(
            {
                vol.Required(CONF_SOURCE_TRACKER): EntitySelector(
                    EntitySelectorConfig(domain="device_tracker")
                ),
                vol.Required(CONF_GEOJSON_SOURCE): TextSelector(),
            }
        )

        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)