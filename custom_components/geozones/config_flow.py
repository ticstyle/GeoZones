"""Config flow framework implementation details for GeoZones handling setups."""

import logging
import os
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
)

from .const import (
    CONF_GEOJSON_SOURCE,
    CONF_HOME_SSIDS,
    CONF_HOME_ZONE,
    CONF_MAX_GPS_ACCURACY,
    CONF_SOURCE_TRACKER,
    CONF_WIFI_SSID_SENSOR,
    DOMAIN,
)
from .utils import fetch_and_process_geojson, get_all_geojson_files

_LOGGER = logging.getLogger(__name__)


class GeoZonesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle creation and reconfiguration process logic for GeoZones tracker entries."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow layout handler."""
        self._user_data: dict[str, Any] = {}

    def _find_matching_wifi_sensor(self, tracker_entity_id: str) -> str | None:
        """Find a matching Wi-Fi sensor for the selected device tracker."""
        if not self.hass:
            return None

        tracker_slug = tracker_entity_id.split(".")[-1]
        base_slug = (
            tracker_slug.replace("_phone", "")
            .replace("_iphone", "")
            .replace("_android", "")
        )

        all_sensors = self.hass.states.async_entity_ids("sensor")

        # Priority 1: Direct match containing full slug and wifi
        for entity_id in all_sensors:
            if tracker_slug in entity_id and "wifi" in entity_id:
                return entity_id

        # Priority 2: Match containing base slug and wifi
        for entity_id in all_sensors:
            if base_slug in entity_id and "wifi" in entity_id:
                return entity_id

        return None

    def _get_previously_configured_ssids(self) -> list[str]:
        """Collect all unique SSIDs previously configured in other integration entries."""
        ssids: set[str] = set()
        if self.hass:
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                entry_ssids = entry.data.get(CONF_HOME_SSIDS, [])
                if isinstance(entry_ssids, list):
                    ssids.update(entry_ssids)
        return sorted(list(ssids))

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle initial step workflow data collection inputs."""
        errors: dict[str, str] = {}

        if user_input is not None:
            source_tracker = user_input[CONF_SOURCE_TRACKER]
            geojson_source = user_input[CONF_GEOJSON_SOURCE]
            entity_id_slug = source_tracker.split(".")[-1]

            if os.path.basename(geojson_source).startswith("geozones_"):
                errors["base"] = "system_file_forbidden"
            else:
                processed_path = await fetch_and_process_geojson(
                    self.hass, geojson_source, entity_id_slug
                )

                if processed_path is None:
                    errors["base"] = "processing_failed"
                    _LOGGER.warning(
                        "Could not setup entry due to data processing errors"
                    )
                else:
                    await self.async_set_unique_id(f"geozones_{entity_id_slug}")
                    self._abort_if_unique_id_configured()

                    # Save intermediate inputs and jump to the advanced settings step
                    self._user_data = {
                        CONF_SOURCE_TRACKER: source_tracker,
                        CONF_GEOJSON_SOURCE: geojson_source,
                    }
                    return await self.async_step_advanced()

        local_files = await self.hass.async_add_executor_job(
            get_all_geojson_files, self.hass
        )

        if local_files:
            files_text = "\n" + "\n".join([f"- {f}" for f in local_files])
            suggested_file = local_files[0]
        else:
            files_text = "\n\n*(No local files discovered in folder configuration)*"
            suggested_file = None

        source_schema = (
            vol.Required(CONF_GEOJSON_SOURCE, default=suggested_file)
            if suggested_file
            else vol.Required(CONF_GEOJSON_SOURCE)
        )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_SOURCE_TRACKER): EntitySelector(
                    EntitySelectorConfig(domain="device_tracker")
                ),
                source_schema: TextSelector(),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={"local_files": files_text},
        )

    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle secondary advanced logic setup parameters."""
        errors: dict[str, str] = {}

        if user_input is not None:
            source_tracker = self._user_data[CONF_SOURCE_TRACKER]
            entity_id_slug = source_tracker.split(".")[-1]

            return self.async_create_entry(
                title=f"GeoZones {entity_id_slug}",
                data={
                    CONF_SOURCE_TRACKER: source_tracker,
                    CONF_GEOJSON_SOURCE: self._user_data[CONF_GEOJSON_SOURCE],
                    CONF_MAX_GPS_ACCURACY: user_input.get(CONF_MAX_GPS_ACCURACY, 50),
                    CONF_WIFI_SSID_SENSOR: user_input.get(CONF_WIFI_SSID_SENSOR),
                    CONF_HOME_SSIDS: user_input.get(CONF_HOME_SSIDS, []),
                    CONF_HOME_ZONE: user_input.get(CONF_HOME_ZONE, "zone.home"),
                },
            )

        suggested_wifi = self._find_matching_wifi_sensor(
            self._user_data[CONF_SOURCE_TRACKER]
        )

        schema_dict = {
            vol.Optional(CONF_MAX_GPS_ACCURACY, default=50): NumberSelector(
                NumberSelectorConfig(min=1, max=1000, step=1)
            ),
        }

        if suggested_wifi:
            schema_dict[
                vol.Optional(CONF_WIFI_SSID_SENSOR, default=suggested_wifi)
            ] = EntitySelector(EntitySelectorConfig(domain="sensor"))
        else:
            schema_dict[vol.Optional(CONF_WIFI_SSID_SENSOR)] = EntitySelector(
                EntitySelectorConfig(domain="sensor")
            )

        schema_dict[vol.Optional(CONF_HOME_SSIDS)] = SelectSelector(
            SelectSelectorConfig(
                options=self._get_previously_configured_ssids(),
                multiple=True,
                custom_value=True,
            )
        )

        schema_dict[vol.Optional(CONF_HOME_ZONE, default="zone.home")] = (
            EntitySelector(EntitySelectorConfig(domain="zone"))
        )

        return self.async_show_form(
            step_id="advanced",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )

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

            if os.path.basename(geojson_source).startswith("geozones_"):
                errors["base"] = "system_file_forbidden"
            else:
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
                            CONF_MAX_GPS_ACCURACY: user_input.get(
                                CONF_MAX_GPS_ACCURACY, 50
                            ),
                            CONF_WIFI_SSID_SENSOR: user_input.get(
                                CONF_WIFI_SSID_SENSOR
                            ),
                            CONF_HOME_SSIDS: user_input.get(CONF_HOME_SSIDS, []),
                            CONF_HOME_ZONE: user_input.get(
                                CONF_HOME_ZONE, "zone.home"
                            ),
                        },
                    )

        local_files = await self.hass.async_add_executor_job(
            get_all_geojson_files, self.hass
        )
        files_text = (
            "\n" + "\n".join([f"- {f}" for f in local_files])
            if local_files
            else "\n\n*(No local files discovered in folder configuration)*"
        )

        current_tracker = config_entry.data.get(CONF_SOURCE_TRACKER)
        current_source = config_entry.data.get(CONF_GEOJSON_SOURCE)
        current_accuracy = config_entry.data.get(CONF_MAX_GPS_ACCURACY, 50)
        current_wifi_sensor = config_entry.data.get(CONF_WIFI_SSID_SENSOR)
        current_ssids = config_entry.data.get(CONF_HOME_SSIDS, [])
        current_home_zone = config_entry.data.get(CONF_HOME_ZONE, "zone.home")

        schema_dict = {
            vol.Required(
                CONF_SOURCE_TRACKER, default=current_tracker
            ): EntitySelector(EntitySelectorConfig(domain="device_tracker")),
            vol.Required(
                CONF_GEOJSON_SOURCE, default=current_source
            ): TextSelector(),
            vol.Optional(
                CONF_MAX_GPS_ACCURACY, default=current_accuracy
            ): NumberSelector(NumberSelectorConfig(min=1, max=1000, step=1)),
        }

        # Automatically locate the best-matched sensor if none is currently saved
        suggested_wifi = current_wifi_sensor or self._find_matching_wifi_sensor(
            current_tracker
        )

        if suggested_wifi:
            schema_dict[
                vol.Optional(CONF_WIFI_SSID_SENSOR, default=suggested_wifi)
            ] = EntitySelector(EntitySelectorConfig(domain="sensor"))
        else:
            schema_dict[vol.Optional(CONF_WIFI_SSID_SENSOR)] = EntitySelector(
                EntitySelectorConfig(domain="sensor")
            )

        schema_dict[vol.Optional(CONF_HOME_SSIDS, default=current_ssids)] = (
            SelectSelector(
                SelectSelectorConfig(
                    options=self._get_previously_configured_ssids(),
                    multiple=True,
                    custom_value=True,
                )
            )
        )

        schema_dict[vol.Optional(CONF_HOME_ZONE, default=current_home_zone)] = (
            EntitySelector(EntitySelectorConfig(domain="zone"))
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
            description_placeholders={"local_files": files_text},
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Hook options flow framework logic handlers to the entry instances."""
        return GeoZonesOptionsFlowHandler()


class GeoZonesOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle continuous inline configuration adjustments after setup cycles."""

    def _get_previously_configured_ssids(self) -> list[str]:
        """Collect all unique SSIDs previously configured in other integration entries."""
        ssids: set[str] = set()
        if self.hass:
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                entry_ssids = entry.data.get(CONF_HOME_SSIDS, [])
                if isinstance(entry_ssids, list):
                    ssids.update(entry_ssids)
        return sorted(list(ssids))

    def _find_matching_wifi_sensor(self, tracker_entity_id: str) -> str | None:
        """Find a matching Wi-Fi sensor for the selected device tracker."""
        if not self.hass:
            return None

        tracker_slug = tracker_entity_id.split(".")[-1]
        base_slug = (
            tracker_slug.replace("_phone", "")
            .replace("_iphone", "")
            .replace("_android", "")
        )

        all_sensors = self.hass.states.async_entity_ids("sensor")

        # Priority 1: Direct match containing full slug and wifi
        for entity_id in all_sensors:
            if tracker_slug in entity_id and "wifi" in entity_id:
                return entity_id

        # Priority 2: Match containing base slug and wifi
        for entity_id in all_sensors:
            if base_slug in entity_id and "wifi" in entity_id:
                return entity_id

        return None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage option configuration updates."""
        errors: dict[str, str] = {}

        if user_input is not None:
            source_tracker = user_input[CONF_SOURCE_TRACKER]
            geojson_source = user_input[CONF_GEOJSON_SOURCE]
            entity_id_slug = source_tracker.split(".")[-1]

            if os.path.basename(geojson_source).startswith("geozones_"):
                errors["base"] = "system_file_forbidden"
            else:
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
                            CONF_MAX_GPS_ACCURACY: user_input.get(
                                CONF_MAX_GPS_ACCURACY, 50
                            ),
                            CONF_WIFI_SSID_SENSOR: user_input.get(
                                CONF_WIFI_SSID_SENSOR
                            ),
                            CONF_HOME_SSIDS: user_input.get(CONF_HOME_SSIDS, []),
                            CONF_HOME_ZONE: user_input.get(
                                CONF_HOME_ZONE, "zone.home"
                            ),
                        },
                    )
                    return self.async_create_entry(title="", data={})

        local_files = await self.hass.async_add_executor_job(
            get_all_geojson_files, self.hass
        )
        files_text = (
            "\n" + "\n".join([f"- {f}" for f in local_files])
            if local_files
            else "\n\n*(No local files discovered in folder configuration)*"
        )

        current_tracker = self.config_entry.data.get(CONF_SOURCE_TRACKER)
        current_source = self.config_entry.data.get(CONF_GEOJSON_SOURCE)
        current_accuracy = self.config_entry.data.get(CONF_MAX_GPS_ACCURACY, 50)
        current_wifi_sensor = self.config_entry.data.get(CONF_WIFI_SSID_SENSOR)
        current_ssids = self.config_entry.data.get(CONF_HOME_SSIDS, [])
        current_home_zone = self.config_entry.data.get(CONF_HOME_ZONE, "zone.home")

        schema_dict = {
            vol.Required(
                CONF_SOURCE_TRACKER, default=current_tracker
            ): EntitySelector(EntitySelectorConfig(domain="device_tracker")),
            vol.Required(
                CONF_GEOJSON_SOURCE, default=current_source
            ): TextSelector(),
            vol.Optional(
                CONF_MAX_GPS_ACCURACY, default=current_accuracy
            ): NumberSelector(NumberSelectorConfig(min=1, max=1000, step=1)),
        }

        # Automatically locate the best-matched sensor if none is currently saved
        suggested_wifi = current_wifi_sensor or self._find_matching_wifi_sensor(
            current_tracker
        )

        if suggested_wifi:
            schema_dict[
                vol.Optional(CONF_WIFI_SSID_SENSOR, default=suggested_wifi)
            ] = EntitySelector(EntitySelectorConfig(domain="sensor"))
        else:
            schema_dict[vol.Optional(CONF_WIFI_SSID_SENSOR)] = EntitySelector(
                EntitySelectorConfig(domain="sensor")
            )

        schema_dict[vol.Optional(CONF_HOME_SSIDS, default=current_ssids)] = (
            SelectSelector(
                SelectSelectorConfig(
                    options=self._get_previously_configured_ssids(),
                    multiple=True,
                    custom_value=True,
                )
            )
        )

        schema_dict[vol.Optional(CONF_HOME_ZONE, default=current_home_zone)] = (
            EntitySelector(EntitySelectorConfig(domain="zone"))
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
            description_placeholders={"local_files": files_text},
        )
