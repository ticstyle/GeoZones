"""Utility functions for processing, sorting, and validating GeoJSON boundaries."""

import json
import logging
import math
import os
from typing import Any

import aiofiles  # type: ignore[import-untyped]
import aiohttp

from homeassistant.core import HomeAssistant

from .const import MAX_VERTICES, MAX_ZONES, PROPERTIES_TO_KEEP, STORAGE_DIR

_LOGGER = logging.getLogger(__name__)


def _calculate_polygon_area(coordinates: list[Any]) -> float:
    """Calculate the spherical area of a polygon in square meters using ray-rings."""
    if not coordinates:
        return 0.0

    def ring_area(ring: list[list[float]]) -> float:
        # Earth's authalic radius in meters
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

    # GeoJSON spec dictates coordinates[0] is always the exterior boundary ring
    outer_area = ring_area(coordinates[0])
    
    # Coordinates[1:] are interior rings representing hollow holes to subtract
    for hole in coordinates[1:]:
        outer_area -= ring_area(hole)
        
    return max(0.0, outer_area)


async def fetch_and_process_geojson(
    hass: HomeAssistant, source: str, entity_id_slug: str
) -> str | None:
    """Download or read a GeoJSON file, validate, sort, and save it locally."""
    content: str = ""

    # Handle web URLs vs local files gracefully
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
        except Exception as err:
            _LOGGER.error("Error downloading GeoJSON file from %s: %s", source, err)
            return None
    else:
        # Assume it is a local path file
        if not os.path.exists(source):
            _LOGGER.error("Local GeoJSON file path does not exist: %s", source)
            return None
        try:
            async with aiofiles.open(source, mode="r", encoding="utf-8") as file:
                content = await file.read()
        except Exception as err:
            _LOGGER.error("Failed to read local GeoJSON file %s: %s", source, err)
            return None

    try:
        geojson_data = json.loads(content)
    except json.JSONDecodeError as err:
        _LOGGER.error("Invalid JSON format encountered: %s", err)
        return None

    # Replicate cleanup and explosion logic from custom standalone tool
    features = geojson_data.get("features", [])
    if not isinstance(features, list):
        _LOGGER.error("GeoJSON missing a valid structural list of features")
        return None

    root_properties = {k: v for k, v in geojson_data.items() if k != "features"}

    # Step 1: Check for missing area data, calculate if necessary, and merge object arrays by name
    combined_objects: dict[str, dict[str, Any]] = {}
    for feature in features:
        if "properties" not in feature or feature["properties"] is None:
            feature["properties"] = {}
            
        props = feature["properties"]
        name = props.get("name")
        geom = feature.get("geometry", {}) or {}
        geom_type = geom.get("type")
        coords = geom.get("coordinates", [])

        # Automatically intercept and generate missing area stats dynamically
        if "area" not in props or props["area"] is None or props["area"] == 0:
            calculated_area = 0.0
            if geom_type == "Polygon":
                calculated_area = _calculate_polygon_area(coords)
            elif geom_type == "MultiPolygon":
                for poly_coords in coords:
                    calculated_area += _calculate_polygon_area(poly_coords)
            
            _LOGGER.debug("Generated dynamic area calculation for zone %s: %s m²", name, calculated_area)
            props["area"] = calculated_area

        if not name or not geom:
            fallback_id = f"__namnlös_{id(feature)}__"
            combined_objects[fallback_id] = feature
            continue

        if name not in combined_objects:
            combined_objects[name] = {
                "type": "Feature",
                "properties": dict(props),
                "geometry": {"type": geom_type, "coordinates": json.loads(json.dumps(coords))},
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

    # Step 2: Explode MultiPolygons out into dedicated single Polygons
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

    # Step 3: Sort elements ascending by area attribute configuration
    final_features.sort(key=lambda f: (f.get("properties") or {}).get("area", 0))

    # Step 4: Strict limits verification pass
    total_zones = len(final_features)
    total_vertices = 0

    cleaned_features: list[dict[str, Any]] = []
    for feature in final_features:
        geom = feature.get("geometry", {}) or {}
        geom_type = geom.get("type")
        coords = geom.get("coordinates", [])

        # Count coordinate elements to evaluate vertex bounds
        if geom_type == "Polygon":
            for ring in coords:
                total_vertices += len(ring)

        old_props = feature.get("properties", {}) or {}
        clean_props: dict[str, Any] = {}

        if "name" in old_props and "name" in PROPERTIES_TO_KEEP:
            clean_props["name"] = (
                "" if str(old_props["name"]).startswith("__namnlös_") else old_props["name"]
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

    # Ensure output destination target space is created inside config directory
    target_dir = hass.config.path(STORAGE_DIR)
    os.makedirs(target_dir, exist_ok=True)
    target_path = os.path.join(target_dir, f"geozones_{entity_id_slug}.json")

    # Output back to formatted local JSON document structure asynchronously
    output_data = {**root_properties, "features": cleaned_features}
    try:
        async with aiofiles.open(target_path, mode="w", encoding="utf-8") as file:
            await file.write(json.dumps(output_data, ensure_ascii=False, indent=2))
        return target_path
    except Exception as err:
        _LOGGER.error("Failed writing cleaned output file matrix to path: %s", err)
        return None


def point_in_polygon(lon: float, lat: float, polygon_coordinates: list[Any]) -> bool:
    """Ray-casting algorithm to determine if point coordinates fall within exterior ring boundaries."""
    if not polygon_coordinates:
        return False

    # Extract the exterior ring path array sequence
    exterior_ring = polygon_coordinates[0]
    inside = False
    num_points = len(exterior_ring)

    if num_points < 3:
        return False

    p1x, p1y = exterior_ring[0]
    for i in range(num_points + 1):
        p2x, p2y = exterior_ring[i % num_points]
        if lat > min(p1y, p2y):
            if lat <= max(p1y, p2y):
                if lon <= max(p1x, p2x):
                    if p1y != p2y:
                        x_intersection = (lat - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or lon <= x_intersection:
                        inside = not inside
        p1x, p1y = p2x, p2y

    return inside
    
