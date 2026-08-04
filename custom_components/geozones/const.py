# custom_components/geozones/const.py
"""Constants for the GeoZones integration."""

from typing import Final

DOMAIN: Final = "geozones"

CONF_SOURCE_TRACKER: Final = "source_tracker"
CONF_GEOJSON_SOURCE: Final = "geojson_source"
CONF_MAX_GPS_ACCURACY: Final = "max_gps_accuracy"
CONF_WIFI_SSID_SENSOR: Final = "wifi_ssid_sensor"
CONF_HOME_SSIDS: Final = "home_ssids"
CONF_HOME_ZONE: Final = "home_zone"
CONF_USE_CUSTOM_ZONES: Final = "use_custom_zones"
CONF_SHOW_IN_SIDEBAR: Final = "show_in_sidebar"

DEFAULT_HOME_ZONE: Final = "zone.home"
DEFAULT_USE_CUSTOM_ZONES: Final = True
DEFAULT_SHOW_IN_SIDEBAR: Final = True
CUSTOM_ZONES_FILENAME: Final = "geozones_custom_zones.geojson"

ATTR_CONTAINING_ZONES: Final = "containing_zones"
STORAGE_DIR: Final = "geozones"

MAX_ZONES: Final = 2500
MAX_VERTICES: Final = 250000

PROPERTIES_TO_KEEP: Final = ["name", "area", "perimeter", "shape"]
