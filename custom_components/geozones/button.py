# custom_components/geozones/button.py
"""Button platform entities for instant GeoZones location marking and reloading."""

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_SOURCE_TRACKER, DOMAIN
from .utils import async_add_custom_zone, fetch_and_process_geojson

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up GeoZones button entities from a config entry."""
    source_tracker = entry.data[CONF_SOURCE_TRACKER]
    entity_id_slug = source_tracker.split(".")[-1]

    async_add_entities(
        [
            GeoZoneMarkLocationButton(hass, entry, source_tracker, entity_id_slug),
            GeoZoneReloadButton(hass, entry, source_tracker, entity_id_slug),
        ]
    )


class GeoZoneMarkLocationButton(ButtonEntity):
    """Button entity to instantly add a custom zone at the target tracker's location."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        source_tracker: str,
        entity_id_slug: str,
    ) -> None:
        """Initialize location marker button instance."""
        self.hass = hass
        self._entry = entry
        self._source_tracker = source_tracker
        self._entity_id_slug = entity_id_slug

        self._attr_name = f"GeoZones {entity_id_slug} Mark Location"
        self._attr_unique_id = f"geozones_{entity_id_slug}_mark_location"
        self._attr_icon = "mdi:map-marker-plus"

    @property
    def device_info(self) -> DeviceInfo:
        """Link entity to main device container block."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=f"GeoZones {self._entity_id_slug}",
            manufacturer="ticstyle",
            model="GeoZones",
        )

    async def async_press(self) -> None:
        """Execute zone creation at current tracker coordinates when pressed."""
        tracker_state = self.hass.states.get(self._source_tracker)
        if not tracker_state:
            raise ServiceValidationError(
                f"Tracker {self._source_tracker} was not found."
            )

        lat = tracker_state.attributes.get("latitude")
        lon = tracker_state.attributes.get("longitude")

        if lat is None or lon is None:
            raise ServiceValidationError(
                f"Tracker {self._source_tracker} does not have valid GPS coordinates."
            )

        name = f"Marked Spot {dt_util.now().strftime('%Y-%m-%d %H:%M')}"
        await async_add_custom_zone(
            self.hass, name, float(lat), float(lon), radius=50.0
        )

        # Reprocess all entries and fire dispatcher signals
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            src = entry.data[CONF_SOURCE_TRACKER]
            source_file = entry.data.get("geojson_source", "")
            use_custom = entry.data.get("use_custom_zones", True)
            slug = src.split(".")[-1]

            path = await fetch_and_process_geojson(
                self.hass, source_file, slug, use_custom
            )
            if path:
                async_dispatcher_send(self.hass, f"{DOMAIN}_reload_{entry.entry_id}")


class GeoZoneReloadButton(ButtonEntity):
    """Button entity to trigger an instant re-sync and recalculation sweep."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        source_tracker: str,
        entity_id_slug: str,
    ) -> None:
        """Initialize reload button instance."""
        self.hass = hass
        self._entry = entry
        self._entity_id_slug = entity_id_slug

        self._attr_name = f"GeoZones {entity_id_slug} Reload"
        self._attr_unique_id = f"geozones_{entity_id_slug}_reload"
        self._attr_icon = "mdi:refresh"

    @property
    def device_info(self) -> DeviceInfo:
        """Link entity to main device container block."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=f"GeoZones {self._entity_id_slug}",
            manufacturer="ticstyle",
            model="GeoZones",
        )

    async def async_press(self) -> None:
        """Trigger reprocess and dispatcher signals when pressed."""
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            src = entry.data[CONF_SOURCE_TRACKER]
            source_file = entry.data.get("geojson_source", "")
            use_custom = entry.data.get("use_custom_zones", True)
            slug = src.split(".")[-1]

            path = await fetch_and_process_geojson(
                self.hass, source_file, slug, use_custom
            )
            if path:
                async_dispatcher_send(self.hass, f"{DOMAIN}_reload_{entry.entry_id}")
