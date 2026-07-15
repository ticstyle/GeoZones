"""Platform tracking entity binding structures for GeoZones state evaluation mappings."""

import json
import logging
import os
from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_GPS_ACCURACY,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_state_change_event,
)
from homeassistant.helpers.restore_state import RestoreEntity  # Added for state recovery

from .const import (
    ATTR_CONTAINING_ZONES,
    CONF_HOME_SSIDS,
    CONF_HOME_ZONE,
    CONF_MAX_GPS_ACCURACY,
    CONF_SOURCE_TRACKER,
    CONF_WIFI_SSID_SENSOR,
    DOMAIN,
    STORAGE_DIR,
)
from .utils import point_in_polygon

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Initialize custom platform wrapper entities using input configuration rules."""
    source_tracker = entry.data[CONF_SOURCE_TRACKER]
    entity_id_slug = source_tracker.split(".")[-1]

    async_add_entities(
        [GeoZoneTrackerEntity(hass, entry, source_tracker, entity_id_slug)], True
    )


class GeoZoneTrackerEntity(TrackerEntity, RestoreEntity):
    """Mirror tracker representation monitoring underlying geographic region containment changes."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        source_tracker: str,
        entity_id_slug: str,
    ) -> None:
        """Construct mirror platform wrapper state tracking layer instances."""
        self.hass = hass
        self._entry = entry
        self._source_tracker = source_tracker
        self._entity_id_slug = entity_id_slug

        self._attr_name = f"GeoZones {entity_id_slug}"
        self._attr_unique_id = f"geozones_{entity_id_slug}"
        self._attr_suggested_object_id = f"geozones_{entity_id_slug}"

        self._current_zone: str = STATE_UNKNOWN
        self._containing_zones: list[str] = []

        # Load options-flow configurations dynamically with clean typed parameters
        self._max_gps_accuracy: int = entry.data.get(CONF_MAX_GPS_ACCURACY, 50)
        self._wifi_ssid_sensor: str | None = entry.data.get(CONF_WIFI_SSID_SENSOR)
        self._home_ssids: list[str] = entry.data.get(CONF_HOME_SSIDS, [])
        self._home_zone_entity_id: str = entry.data.get(CONF_HOME_ZONE, "zone.home")

        # This holds our sorted features structure directly in RAM memory
        self._geojson_features: list[dict[str, Any]] = []

    def _get_home_zone_name(self) -> str:
        """Retrieve the friendly name of the configured home zone entity."""
        zone_state = self.hass.states.get(self._home_zone_entity_id)
        if zone_state:
            return zone_state.name
        # Fall back to structured formatting of the object ID if state isn't loaded yet
        return self._home_zone_entity_id.split(".")[-1].replace("_", " ").title()

    def _load_features_from_disk(self) -> list[dict[str, Any]]:
        """Read and parse the file structure inside an executor thread context."""
        target_path = os.path.join(
            self.hass.config.path(STORAGE_DIR), f"geozones_{self._entity_id_slug}.json"
        )
        if not os.path.exists(target_path):
            return []
        try:
            with open(target_path, encoding="utf-8") as file:
                data = json.load(file)
                return data.get("features", [])
        except Exception as err:
            _LOGGER.error("Failed to read spatial asset registry records: %s", err)
            return []

    async def async_added_to_hass(self) -> None:
        """Configure runtime callbacks to catch data state updates from source targets."""
        await super().async_added_to_hass()

        # Load initial layout matrix file straight into system RAM cache arrays
        self._geojson_features = await self.hass.async_add_executor_job(
            self._load_features_from_disk
        )

        # Restore previous state if it exists to prevent startup "unknown" states
        if last_state := await self.async_get_last_state():
            self._current_zone = last_state.state
            self._containing_zones = last_state.attributes.get(ATTR_CONTAINING_ZONES, [])

        entities_to_track = [self._source_tracker]
        if self._wifi_ssid_sensor:
            entities_to_track.append(self._wifi_ssid_sensor)

        @callback
        def _async_state_changed_helper(event: Event[EventStateChangedData]) -> None:
            """Intercept coordinate or connection shifts and evaluate bounds instantly."""
            entity_id = event.data["entity_id"]

            # Re-evaluate from tracker coordinate source if Wi-Fi state changes
            if entity_id == self._wifi_ssid_sensor:
                tracker_state = self.hass.states.get(self._source_tracker)
                self._evaluate_location(tracker_state)
                return

            new_state = event.data.get("new_state")
            if new_state is None:
                return
            self._evaluate_location(new_state)

        # Hook state change event listener to track coordinates and connection sensor
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, entities_to_track, _async_state_changed_helper
            )
        )

        # Listen for the nightly refresh completion to reload memory cache arrays
        async def _handle_reload_signal() -> None:
            self._geojson_features = await self.hass.async_add_executor_job(
                self._load_features_from_disk
            )
            initial_state = self.hass.states.get(self._source_tracker)
            self._evaluate_location(initial_state)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_reload_{self._entry.entry_id}",
                _handle_reload_signal,
            )
        )

        # Force a startup state mapping synchronization check pass execution cycle
        initial_state = self.hass.states.get(self._source_tracker)
        self._evaluate_location(initial_state)

    @callback
    def _evaluate_location(self, source_state: Any | None) -> None:
        """Parse underlying geometries from cache, check accuracy, and manage anchors."""

        # Step 1: Handle Wi-Fi anchor priority first
        if self._wifi_ssid_sensor:
            wifi_state = self.hass.states.get(self._wifi_ssid_sensor)
            if wifi_state and wifi_state.state in self._home_ssids:
                home_name = self._get_home_zone_name()
                self._current_zone = home_name
                self._containing_zones = [home_name]
                self.async_write_ha_state()
                return

        # If the source tracker is offline or temporarily unavailable,
        # we preserve our restored state rather than wiping it to STATE_UNKNOWN.
        if source_state is None or source_state.state in (STATE_UNKNOWN, "unavailable"):
            if self._current_zone == STATE_UNKNOWN:
                self._containing_zones = []
                self.async_write_ha_state()
            return

        lat = source_state.attributes.get(ATTR_LATITUDE)
        lon = source_state.attributes.get(ATTR_LONGITUDE)

        if lat is None or lon is None:
            # Only set to unknown if we don't have coordinates and no wifi active
            self._current_zone = STATE_UNKNOWN
            self._containing_zones = []
            self.async_write_ha_state()
            return

        # Step 2: Validate GPS accuracy threshold is within acceptable bounds
        accuracy = source_state.attributes.get(ATTR_GPS_ACCURACY)
        if accuracy is not None and accuracy > self._max_gps_accuracy:
            _LOGGER.debug(
                "Ignored location update for %s due to low accuracy: %sm (Threshold: %sm)",
                self._entity_id_slug,
                accuracy,
                self._max_gps_accuracy,
            )
            return

        matched_zones: list[str] = []

        # Read directly from RAM memory arrays – lightning fast calculations
        for feature in self._geojson_features:
            geom = feature.get("geometry", {}) or {}
            props = feature.get("properties", {}) or {}
            geom_type = geom.get("type")
            coords = geom.get("coordinates", [])
            zone_name = props.get("name", "Unnamed Zone")

            if geom_type == "Polygon" and point_in_polygon(
                float(lon), float(lat), coords
            ):
                matched_zones.append(zone_name)

        if matched_zones:
            self._current_zone = matched_zones[0]
            self._containing_zones = matched_zones
        else:
            self._current_zone = "not_home"
            self._containing_zones = []

        self.async_write_ha_state()

    @property
    def state(self) -> str:
        """Return the current localized tracking description label context text."""
        return self._current_zone

    @property
    def in_zones(self) -> list[str]:
        """Return the custom geo-spatial zones the entity is currently matching within."""
        return self._containing_zones

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose calculated nested array layouts safely to environment parameters."""
        return {
            ATTR_CONTAINING_ZONES: self._containing_zones,
            "source_entity_id": self._source_tracker,
            "max_gps_accuracy": self._max_gps_accuracy,
        }

    @property
    def source_type(self) -> SourceType:
        """Return the framework processing source input classification type standard."""
        return SourceType.GPS

    @property
    def device_info(self) -> DeviceInfo:
        """Link this tracking entity to a clean, distinct parent device container block."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=self._attr_name,
            manufacturer="ticstyle",
            model="GeoZones",
        )
