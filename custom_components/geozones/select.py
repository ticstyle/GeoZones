# custom_components/geozones/select.py
"""Select platform entity exposing custom zone selection dropdown options."""

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_SOURCE_TRACKER, DOMAIN
from .utils import async_get_custom_zone_names

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up GeoZones select entity from a config entry."""
    source_tracker = entry.data[CONF_SOURCE_TRACKER]
    entity_id_slug = source_tracker.split(".")[-1]

    async_add_entities(
        [GeoZoneCustomZonesSelect(hass, entry, entity_id_slug)]
    )


class GeoZoneCustomZonesSelect(SelectEntity, RestoreEntity):
    """Select entity representing browsable custom zones from the shared custom zones file."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        entity_id_slug: str,
    ) -> None:
        """Initialize custom zones dropdown select entity."""
        self.hass = hass
        self._entry = entry
        self._entity_id_slug = entity_id_slug

        self._attr_name = f"GeoZones {entity_id_slug} Custom Zones"
        self._attr_unique_id = f"geozones_{entity_id_slug}_custom_zones"
        self._attr_icon = "mdi:map-marker-multiple"

        self._attr_options: list[str] = []
        self._attr_current_option: str | None = None

    @property
    def device_info(self) -> DeviceInfo:
        """Link entity to main device container block."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=f"GeoZones {self._entity_id_slug}",
            manufacturer="ticstyle",
            model="GeoZones",
        )

    async def async_added_to_hass(self) -> None:
        """Load initial options and attach dispatcher listeners."""
        await super().async_added_to_hass()

        if last_state := await self.async_get_last_state():
            self._attr_current_option = last_state.state

        await self._async_update_options()

        @callback
        def _handle_reload_signal() -> None:
            self.hass.async_create_task(self._async_update_options())

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_reload_{self._entry.entry_id}",
                _handle_reload_signal,
            )
        )

    async def _async_update_options(self) -> None:
        """Fetch updated custom zone options from storage and update state."""
        options = await async_get_custom_zone_names(self.hass)
        self._attr_options = options

        if self._attr_current_option not in options:
            self._attr_current_option = options[0] if options else None

        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Select a custom zone option."""
        if option in self._attr_options:
            self._attr_current_option = option
            self.async_write_ha_state()
