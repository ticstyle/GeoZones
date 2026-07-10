"""Platform tracking entity binding structures for GeoZones state evaluation mappings."""

import json
import logging
import os
from typing import Any

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, STATE_UNKNOWN
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import ATTR_CONTAINING_ZONES, CONF_SOURCE_TRACKER, STORAGE_DIR
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


class GeoZoneTrackerEntity(TrackerEntity):
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

        # Explicitly hardcode target entity path signature mapping format requirements
        self.entity_id = f"device_tracker.geozones_{entity_id_slug}"
        self._attr_name = f"GeoZones {entity_id_slug}"
        self._attr_unique_id = f"geozones_{entity_id_slug}"

        self._current_zone: str = STATE_UNKNOWN
        self._containing_zones: list[str] = []

    async def async_added_to_hass(self) -> None:
        """Configure runtime callbacks to catch data state updates from source targets."""

        @callback
        def _async_source_changed_helper(event: Event) -> None:
            """Intercept changes, evaluate coordinates alignment arrays, and enqueue entity updates."""
            new_state = event.data.get("new_state")
            if new_state is None:
                return

            self.hass.async_create_task(self.async_update_geojson_tracking(new_state))

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._source_tracker], _async_source_changed_helper
            )
        )

        # Trigger immediate run-once initialization pass during boot execution cycles
        initial_state = self.hass.states.get(self._source_tracker)
        if initial_state:
            await self.async_update_geojson_tracking(initial_state)

    async def async_update_geojson_tracking(self, source_state: Any) -> None:
        """Parse underlying spatial geometries and match point intersections sequentially."""
        lat = source_state.attributes.get(ATTR_LATITUDE)
        lon = source_state.attributes.get(ATTR_LONGITUDE)

        if lat is None or lon is None:
            self._current_zone = STATE_UNKNOWN
            self._containing_zones = []
            self.async_write_ha_state()
            return

        target_path = os.path.join(
            self.hass.config.path(STORAGE_DIR), f"geozones_{self._entity_id_slug}.json"
        )

        if not os.path.exists(target_path):
            _LOGGER.warning(
                "Expected geojson working asset structure missing at: %s", target_path
            )
            self._current_zone = STATE_UNKNOWN
            self._containing_zones = []
            self.async_write_ha_state()
            return

        try:
            # Parse localized JSON document
            with open(target_path, encoding="utf-8") as file:
                data = json.load(file)
        except Exception as err:
            _LOGGER.error("Failed to read spatial asset registry records: %s", err)
            return

        features = data.get("features", [])
        matched_zones: list[str] = []

        # Rely on structural order sorting array alignment rules from utility transformations
        for feature in features:
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
            # The smallest zone is the first match down the file path layout order hierarchy
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
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose calculated nested array layout arrays safely to environment parameters."""
        return {
            ATTR_CONTAINING_ZONES: self._containing_zones,
            "source_entity_id": self._source_tracker,
        }

    @property
    def source_type(self) -> SourceType:
        """Return the framework processing source input classification type standard."""
        return SourceType.GPS
