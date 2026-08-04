# custom_components/geozones/utils.py
"""Utility functions for processing, sorting, and validating GeoJSON boundaries."""

import json
import logging
import math
import os
from typing import Any

import aiofiles  # type: ignore[import-untyped]
import aiohttp
from homeassistant.core import HomeAssistant

from .const import (
    CUSTOM_ZONES_FILENAME,
    MAX_VERTICES,
    MAX_ZONES,
    PROPERTIES_TO_KEEP,
    STORAGE_DIR,
)

_LOGGER = logging.getLogger(__name__)


def get_all_geojson_files(hass: HomeAssistant) -> list[str]:
    """Scan storage directory and return all user-provided GeoJSON or JSON files."""
    target_dir = hass.config.path(STORAGE_DIR)
    os.makedirs(target_dir, exist_ok=True)
    found_files: list[str] = []

    try:
        for filename in sorted(os.listdir(target_dir)):
            # Skip system generated output files
            if filename.startswith("geozones_"):
                continue

            if filename.lower().endswith((".geojson", ".json")):
                found_files.append(f"/{STORAGE_DIR}/{filename}")
    except OSError as err:
        _LOGGER.error(
            "Failed scanning directory %s for file assets list: %s", target_dir, err
        )

    return found_files


async def async_ensure_custom_zones_file(hass: HomeAssistant) -> str:
    """Ensure shared custom zones file exists in storage folder."""
    target_dir = hass.config.path(STORAGE_DIR)
    os.makedirs(target_dir, exist_ok=True)
    custom_path = os.path.join(target_dir, CUSTOM_ZONES_FILENAME)

    if not os.path.exists(custom_path):
        initial_data = {"type": "FeatureCollection", "features": []}
        try:
            async with aiofiles.open(custom_path, mode="w", encoding="utf-8") as file:
                await file.write(json.dumps(initial_data, indent=2))
        except OSError as err:
            _LOGGER.error(
                "Failed creating initial custom zones file %s: %s", custom_path, err
            )

    return custom_path


async def async_get_custom_zone_names(hass: HomeAssistant) -> list[str]:
    """Retrieve the list of custom zone names from the shared custom zones file."""
    custom_path = await async_ensure_custom_zones_file(hass)
    try:
        async with aiofiles.open(custom_path, mode="r", encoding="utf-8") as file:
            content = await file.read()
            data = json.loads(content)
    except (OSError, json.JSONDecodeError):
        return []

    features = data.get("features", [])
    names: list[str] = []
    for f in features:
        props = f.get("properties", {}) or {}
        name = props.get("name")
        if name and isinstance(name, str):
            names.append(name)

    return sorted(names)


def _generate_circle_polygon(
    lat: float, lon: float, radius: float = 50.0, num_points: int = 32
) -> list[list[float]]:
    """Generate an array of coordinates forming a circular polygon around a point."""
    ring: list[list[float]] = []
    lat_rad = math.radians(lat)
    lat_delta = radius / 111320.0
    lon_delta = (
        radius / (111320.0 * math.cos(lat_rad))
        if math.cos(lat_rad) != 0
        else radius / 111320.0
    )

    for i in range(num_points):
        angle = (2.0 * math.pi * i) / num_points
        p_lat = lat + (lat_delta * math.sin(angle))
        p_lon = lon + (lon_delta * math.cos(angle))
        ring.append([round(p_lon, 6), round(p_lat, 6)])

    # Close exterior boundary ring
    ring.append(ring[0])
    return ring


async def async_add_custom_zone(
    hass: HomeAssistant, name: str, lat: float, lon: float, radius: float = 50.0
) -> str:
    """Add a new custom zone into the shared custom zones file with deduplication."""
    custom_path = await async_ensure_custom_zones_file(hass)
    try:
        async with aiofiles.open(custom_path, mode="r", encoding="utf-8") as file:
            content = await file.read()
            data = json.loads(content)
    except (OSError, json.JSONDecodeError):
        data = {"type": "FeatureCollection", "features": []}

    features = data.get("features", [])
    existing_names = {
        f.get("properties", {}).get("name")
        for f in features
        if f.get("properties") and f["properties"].get("name")
    }

    final_name = name
    if final_name in existing_names:
        counter = 1
        candidate = f"{name} ({counter})"
        while candidate in existing_names:
            counter += 1
            candidate = f"{name} ({counter})"
        final_name = candidate

    ring_coords = _generate_circle_polygon(lat, lon, radius)
    area = round(math.pi * radius * radius, 2)
    perimeter = round(2.0 * math.pi * radius, 4)

    new_feature = {
        "type": "Feature",
        "properties": {
            "name": final_name,
            "area": area,
            "perimeter": perimeter,
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [ring_coords],
        },
    }

    features.append(new_feature)
    data["features"] = features

    async with aiofiles.open(custom_path, mode="w", encoding="utf-8") as file:
        await file.write(json.dumps(data, indent=2, ensure_ascii=False))

    return final_name


async def async_remove_custom_zone(hass: HomeAssistant, name: str) -> bool:
    """Remove a zone from the shared custom zones file by name."""
    custom_path = await async_ensure_custom_zones_file(hass)
    try:
        async with aiofiles.open(custom_path, mode="r", encoding="utf-8") as file:
            content = await file.read()
            data = json.loads(content)
    except (OSError, json.JSONDecodeError):
        return False

    features = data.get("features", [])
    original_count = len(features)
    new_features = [f for f in features if f.get("properties", {}).get("name") != name]

    if len(new_features) == original_count:
        return False

    data["features"] = new_features
    async with aiofiles.open(custom_path, mode="w", encoding="utf-8") as file:
        await file.write(json.dumps(data, indent=2, ensure_ascii=False))

    return True


async def async_rename_custom_zone(
    hass: HomeAssistant, name: str, new_name: str
) -> bool:
    """Rename a custom zone inside the shared custom zones file with deduplication."""
    custom_path = await async_ensure_custom_zones_file(hass)
    try:
        async with aiofiles.open(custom_path, mode="r", encoding="utf-8") as file:
            content = await file.read()
            data = json.loads(content)
    except (OSError, json.JSONDecodeError):
        return False

    features = data.get("features", [])
    target_feature = None

    for f in features:
        if f.get("properties", {}).get("name") == name:
            target_feature = f
            break

    if not target_feature:
        return False

    other_names = {
        f.get("properties", {}).get("name")
        for f in features
        if f is not target_feature
        and f.get("properties")
        and f["properties"].get("name")
    }

    final_new_name = new_name
    if final_new_name in other_names:
        counter = 1
        candidate = f"{new_name} ({counter})"
        while candidate in other_names:
            counter += 1
            candidate = f"{new_name} ({counter})"
        final_new_name = candidate

    target_feature["properties"]["name"] = final_new_name
    data["features"] = features

    async with aiofiles.open(custom_path, mode="w", encoding="utf-8") as file:
        await file.write(json.dumps(data, indent=2, ensure_ascii=False))

    return True


def _calculate_polygon_area(coordinates: list[Any]) -> float:
    """Calculate the spherical area of a polygon in square meters using ray-rings."""
    if not coordinates:
        return 0.0

    def ring_area(ring: list[list[float]]) -> float:
        earth_radius = 6378137.0
        total = 0.0
        num_points = len(ring)

        if num_points < 3:
            return 0.0

        for i in range(num_points - 1):
            p1 = ring[i]
            p2 = ring[i + 1]
            total += (math.radians(p2[0]) - math.radians(p1[0])) * (
                2.0 + math.sin(math.radians(p1[1])) + math.sin(math.radians(p2[1]))
            )
        return abs(total * earth_radius * earth_radius / 2.0)

    outer_area = ring_area(coordinates[0])

    for hole in coordinates[1:]:
        outer_area -= ring_area(hole)

    return max(0.0, outer_area)


async def fetch_and_process_geojson(
    hass: HomeAssistant,
    source: str,
    entity_id_slug: str,
    use_custom_zones: bool = True,
) -> str | None:
    """Download or read a GeoJSON file, validate, sort, and save it locally."""
    content: str = ""

    if source.startswith(("http://", "https://")):
        try:
            async with aiohttp.ClientSession() as session:
                timeout = aiohttp.ClientTimeout(total=10)
                async with session.get(source, timeout=timeout) as response:
                    if response.status != 200:
                        _LOGGER.error(
                            "Failed to download GeoJSON from %s: HTTP %s",
                            source,
                            response.status,
                        )
                        return None
                    content = await response.text()
        except (aiohttp.ClientError, TimeoutError, OSError) as err:
            _LOGGER.error("Error downloading GeoJSON file from %s: %s", source, err)
            return None
    else:
        local_path = (
            source
            if os.path.isabs(source) and os.path.exists(source)
            else hass.config.path(source.lstrip("/"))
        )

        if os.path.basename(local_path).startswith("geozones_"):
            _LOGGER.error(
                "Rejected attempt to loop an internal system-generated output file as source: %s",
                local_path,
            )
            return None

        if not os.path.exists(local_path):
            _LOGGER.error("Local GeoJSON file path does not exist: %s", local_path)
            return None
        try:
            async with aiofiles.open(local_path, mode="r", encoding="utf-8") as file:
                content = await file.read()
        except (OSError, json.JSONDecodeError) as err:
            _LOGGER.error("Failed to read local GeoJSON file %s: %s", local_path, err)
            return None

    try:
        geojson_data = json.loads(content)
    except json.JSONDecodeError as err:
        _LOGGER.error("Invalid JSON format encountered: %s", err)
        return None

    features = geojson_data.get("features", [])
    if not isinstance(features, list):
        _LOGGER.error("GeoJSON missing a valid structural list of features")
        return None

    if use_custom_zones:
        custom_path = await async_ensure_custom_zones_file(hass)
        try:
            async with aiofiles.open(custom_path, mode="r", encoding="utf-8") as file:
                c_content = await file.read()
                c_data = json.loads(c_content)
                c_features = c_data.get("features", [])
                if isinstance(c_features, list):
                    features.extend(c_features)
        except (OSError, json.JSONDecodeError) as err:
            _LOGGER.warning("Could not merge custom zones into source: %s", err)

    root_properties = {k: v for k, v in geojson_data.items() if k != "features"}

    combined_objects: dict[str, dict[str, Any]] = {}
    for feature in features:
        if "properties" not in feature or feature["properties"] is None:
            feature["properties"] = {}

        props = feature["properties"]
        name = props.get("name")
        geom = feature.get("geometry", {}) or {}
        geom_type = geom.get("type")
        coords = geom.get("coordinates", [])

        if "area" not in props or props["area"] is None or props["area"] == 0:
            calculated_area = 0.0
            if geom_type == "Polygon":
                calculated_area = _calculate_polygon_area(coords)
            elif geom_type == "MultiPolygon":
                for poly_coords in coords:
                    calculated_area += _calculate_polygon_area(poly_coords)

            _LOGGER.debug(
                "Generated dynamic area calculation for zone %s: %s m²",
                name,
                calculated_area,
            )
            props["area"] = calculated_area

        if not name or not geom:
            fallback_id = f"__namnlös_{id(feature)}__"
            combined_objects[fallback_id] = feature
            continue

        if name not in combined_objects:
            combined_objects[name] = {
                "type": "Feature",
                "properties": dict(props),
                "geometry": {
                    "type": geom_type,
                    "coordinates": json.loads(json.dumps(coords)),
                },
            }
        else:
            existing_feature = combined_objects[name]
            existing_geom = existing_feature["geometry"]

            if existing_geom["type"] == "Polygon":
                existing_geom["type"] = "MultiPolygon"
                existing_geom["coordinates"] = [existing_geom["coordinates"]]

            if geom_type == "Polygon":
                existing_geom["coordinates"].append(coords)
            elif geom_type == "MultiPolygon":
                existing_geom["coordinates"].extend(coords)

            if "area" in props and "area" in existing_feature["properties"]:
                existing_feature["properties"]["area"] += props["area"]
            if "perimeter" in props and "perimeter" in existing_feature["properties"]:
                existing_feature["properties"]["perimeter"] += props["perimeter"]

    final_features: list[dict[str, Any]] = []
    for feature in combined_objects.values():
        geom = feature.get("geometry", {}) or {}
        props = feature.get("properties", {}) or {}

        if geom.get("type") == "MultiPolygon":
            for sub_coords in geom.get("coordinates", []):
                exploded_feature = {
                    "type": "Feature",
                    "properties": dict(props),
                    "geometry": {"type": "Polygon", "coordinates": sub_coords},
                }
                final_features.append(exploded_feature)
        else:
            final_features.append(feature)

    final_features.sort(key=lambda f: (f.get("properties") or {}).get("area", 0))

    total_zones = len(final_features)
    total_vertices = 0

    cleaned_features: list[dict[str, Any]] = []
    for feature in final_features:
        geom = feature.get("geometry", {}) or {}
        geom_type = geom.get("type")
        coords = geom.get("coordinates", [])

        if geom_type == "Polygon":
            for ring in coords:
                total_vertices += len(ring)

        old_props = feature.get("properties", {}) or {}
        clean_props: dict[str, Any] = {}

        if "name" in old_props and "name" in PROPERTIES_TO_KEEP:
            clean_props["name"] = (
                ""
                if str(old_props["name"]).startswith("__namnlös_")
                else old_props["name"]
            )
        if "area" in old_props and "area" in PROPERTIES_TO_KEEP:
            clean_props["area"] = round(old_props["area"], 2)

        for prop in PROPERTIES_TO_KEEP:
            if prop not in clean_props and prop in old_props:
                val = old_props[prop]
                if prop == "perimeter" and isinstance(val, (int, float)):
                    val = round(val, 4)
                clean_props[prop] = val

        ordered_feature = {
            "type": feature.get("type", "Feature"),
            "properties": clean_props,
            "geometry": geom,
        }
        cleaned_features.append(ordered_feature)

    if total_zones > MAX_ZONES or total_vertices > MAX_VERTICES:
        _LOGGER.error(
            "GeoJSON validation structural failure for entry %s! "
            "Zones: %s (Max: %s), Vertices: %s (Max: %s)",
            entity_id_slug,
            total_zones,
            MAX_ZONES,
            total_vertices,
            MAX_VERTICES,
        )
        return None

    target_dir = hass.config.path(STORAGE_DIR)
    os.makedirs(target_dir, exist_ok=True)
    target_path = os.path.join(target_dir, f"geozones_{entity_id_slug}.json")

    output_data = {**root_properties, "features": cleaned_features}
    try:
        async with aiofiles.open(target_path, mode="w", encoding="utf-8") as file:
            await file.write(json.dumps(output_data, ensure_ascii=False, indent=2))
        return target_path
    except OSError as err:
        _LOGGER.error("Failed writing cleaned output file matrix to path: %s", err)
        return None


def point_in_polygon(lon: float, lat: float, polygon_coordinates: list[Any]) -> bool:
    """Ray-casting algorithm to determine if point coordinates fall within exterior ring boundaries."""
    if not polygon_coordinates:
        return False

    exterior_ring = polygon_coordinates[0]
    inside = False
    num_points = len(exterior_ring)

    if num_points < 3:
        return False

    p1x, p1y = exterior_ring[0]
    for i in range(num_points + 1):
        p2x, p2y = exterior_ring[i % num_points]
        if min(p1y, p2y) < lat <= max(p1y, p2y) and lon <= max(p1x, p2x):
            if p1y != p2y:
                x_intersection = (lat - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
            if p1x == p2x or lon <= x_intersection:
                inside = not inside
        p1x, p1y = p2x, p2y

    return inside
