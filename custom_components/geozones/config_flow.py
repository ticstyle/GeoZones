"""Config flow framework implementation details for GeoZones handling setups."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    TextSelector,
)

from .const import CONF_GEOJSON_SOURCE, CONF_SOURCE_TRACKER, DOMAIN
from .utils import fetch_and_process_geojson

_LOGGER = logging.getLogger(__name__)


class GeoZonesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle creation and reconfiguration process logic for GeoZones tracker entries."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle initial step workflow data collection inputs."""
        errors: dict[str, str] = {}

        if user_input is not None:
            source_tracker = user_input[CONF_SOURCE_TRACKER]
            geojson_source = user_input[CONF_GEOJSON_SOURCE]
            entity_id_slug = source_tracker.split(".")[-1]

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

        data_schema = vol.Schema(
            {
                vol.Required(CONF_SOURCE_TRACKER): EntitySelector(
                    EntitySelectorConfig(domain="device_tracker")
                ),
                vol.Required(CONF_GEOJSON_SOURCE): TextSelector(),
            }
        )

        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle native user-initiated entry reconfiguration adjustments."""
        errors: dict[str, str] = {}
        config_entry = self._get_reconfigure_entry()

        if user_input is not None:
            source_tracker = user_input[CONF_SOURCE_TRACKER]
            geojson_source = user_input[CONF_GEOJSON_SOURCE]
            entity_id_slug = source_tracker.split(".")[-1]

            processed_path = await fetch_and_process_geojson(
                self.hass, geojson_source, entity_id_slug
            )

            if processed_path is None:
                errors["base"] = "processing_failed"
            else:
                return self.async_update_reload_and_abort(
                    config_entry,
                    data_updates={
                        CONF_SOURCE_TRACKER: source_tracker,
                        CONF_GEOJSON_SOURCE: geojson_source,
                    },
                )

        current_tracker = config_entry.data.get(CONF_SOURCE_TRACKER)
        current_source = config_entry.data.get(CONF_GEOJSON_SOURCE)

        data_schema = vol.Schema(
            {
                vol.Required(CONF_SOURCE_TRACKER, default=current_tracker): EntitySelector(
                    EntitySelectorConfig(domain="device_tracker")
                ),
                vol.Required(CONF_GEOJSON_SOURCE, default=current_source): TextSelector(),
            }
        )

        return self.async_show_form(step_id="reconfigure", data_schema=data_schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> config_entries.OptionsFlow:
        """Hook options flow framework logic handlers to the entry instances."""
        return GeoZonesOptionsFlowHandler()


class GeoZonesOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle continuous inline configuration adjustments after setup cycles."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage option configuration updates."""
        errors: dict[str, str] = {}

        if user_input is not None:
            source_tracker = user_input[CONF_SOURCE_TRACKER]
            geojson_source = user_input[CONF_GEOJSON_SOURCE]
            entity_id_slug = source_tracker.split(".")[-1]

            processed_path = await fetch_and_process_geojson(
                self.hass, geojson_source, entity_id_slug
            )

            if processed_path is None:
                errors["base"] = "processing_failed"
            else:
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={
                        CONF_SOURCE_TRACKER: source_tracker,
                        CONF_GEOJSON_SOURCE: geojson_source,
                    },
                )
                return self.async_create_entry(title="", data={})

        # self.config_entry is now fully inherited from parent class seamlessly
        current_tracker = self.config_entry.data.get(CONF_SOURCE_TRACKER)
        current_source = self.config_entry.data.get(CONF_GEOJSON_SOURCE)

        data_schema = vol.Schema(
            {
                vol.Required(CONF_SOURCE_TRACKER, default=current_tracker): EntitySelector(
                    EntitySelectorConfig(domain="device_tracker")
                ),
                vol.Required(CONF_GEOJSON_SOURCE, default=current_source): TextSelector(),
            }
        )

        return self.async_show_form(step_id="init", data_schema=data_schema, errors=errors)
        
