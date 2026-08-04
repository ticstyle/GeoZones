# custom_components/geozones/dashboard.py
"""Lovelace dashboard orchestration module for GeoZones."""

import logging
import os

import aiofiles  # type: ignore[import-untyped]
from homeassistant.components.frontend import (
    async_register_built_in_panel,
    async_remove_panel,
)
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.dashboard import LovelaceYAML
from homeassistant.core import HomeAssistant

from .const import CONF_SOURCE_TRACKER, DOMAIN

_LOGGER = logging.getLogger(__name__)
DASHBOARD_REL_PATH = "custom_components/geozones/geozones_dashboard.yaml"
LOCAL_LOGO_URL = "/geozones_static/logo.png"


async def async_generate_dashboard_yaml(hass: HomeAssistant) -> str:
    """Generate and write the Lovelace dashboard YAML configuration file."""
    dashboard_path = hass.config.path(DASHBOARD_REL_PATH)
    os.makedirs(os.path.dirname(dashboard_path), exist_ok=True)

    entities_yaml_lines: list[str] = []
    entries = hass.config_entries.async_entries(DOMAIN)

    if entries:
        first_entry = entries[0]
        first_tracker = first_entry.data.get(CONF_SOURCE_TRACKER, "")

        if first_tracker:
            first_slug = first_tracker.split(".")[-1]
            entities_yaml_lines.append(
                f"          - entity: select.geozones_{first_slug}_custom_zones\n"
                "            name: Select Custom Zone"
            )
            entities_yaml_lines.append("          - type: divider")

        for entry in entries:
            source_tracker = entry.data.get(CONF_SOURCE_TRACKER, "")
            if not source_tracker:
                continue
            slug = source_tracker.split(".")[-1]
            entities_yaml_lines.append(
                f"          - entity: button.geozones_{slug}_mark_location\n"
                f"            name: Mark Current Location for {slug}"
            )

        if first_tracker:
            first_slug = first_tracker.split(".")[-1]
            entities_yaml_lines.extend(
                [
                    "          - type: divider",
                    (
                        f"          - entity: button.geozones_{first_slug}_remove_zone\n"
                        "            name: Remove Selected Zone"
                    ),
                    (
                        f"          - entity: button.geozones_{first_slug}_reload\n"
                        "            name: Reload Layer"
                    ),
                ]
            )

    if not entities_yaml_lines:
        entities_block = "          - entity: device_tracker.geozones"
    else:
        entities_block = "\n".join(entities_yaml_lines)

    yaml_content = f"""title: GeoZones
views:
  - title: Overview
    path: overview
    icon: mdi:map-marker-radius
    type: masonry
    cards:
      - type: markdown
        title: "📍 Active Tracking Overview"
        content: |
          <div align="center" style="margin-bottom: 16px;">
            <img src="{LOCAL_LOGO_URL}" width="130" alt="GeoZones Logo">
          </div>

          {{%- set trackers = states.device_tracker | selectattr('entity_id', 'search', '^device_tracker\\\\.geozones_') | list -%}}
          {{%- if trackers | length > 0 -%}}
          {{%- for t in trackers %}}
          ### 📱 {{{{ t.name }}}}
          * **Current Zone:** `{{{{ t.state }}}}`
          * **Source Target:** `{{{{ state_attr(t.entity_id, 'source_entity_id') or t.entity_id }}}}`

          **Active inside zones:**
          {{%- set zones = state_attr(t.entity_id, 'containing_zones') -%}}
          {{%- if zones and zones | length > 0 -%}}
          {{%- for zone in zones %}}
          - {{{{ zone }}}}
          {{%- endfor -%}}
          {{%- else %}}
          *Not inside any custom zones.*
          {{%- endif %}}

          {{%- if not loop.last %}}
          ---
          {{%- endif %}}
          {{%- endfor -%}}
          {{%- else %}}
          *No active GeoZones trackers detected.*
          {{%- endif -%}}

      - type: entities
        title: "⚙️ Custom Zone Manager"
        show_header_toggle: false
        entities:
{entities_block}

      - type: markdown
        title: "🗺️ All Available Zones"
        content: |
          {{%- set ns = namespace(zones=[]) -%}}
          {{%- set trackers = states.device_tracker | selectattr('entity_id', 'search', '^device_tracker\\\\.geozones_') | list -%}}
          {{%- for t in trackers -%}}
            {{%- set lz = state_attr(t.entity_id, 'loaded_zones') or state_attr(t.entity_id, 'available_zones') or state_attr(t.entity_id, 'all_zones') or state_attr(t.entity_id, 'zones') or [] -%}}
            {{%- set ns.zones = ns.zones + lz -%}}
          {{%- endfor -%}}
          {{%- set unique_zones = ns.zones | unique | sort -%}}
          {{%- if unique_zones | length > 0 -%}}
          Total loaded zones across all active files: **{{{{ unique_zones | length }}}}**

          {{%- for z in unique_zones %}}
          - {{{{ z }}}}
          {{%- endfor -%}}
          {{%- else %}}
          *No loaded zones available across active trackers.*
          {{%- endif -%}}
"""

    async with aiofiles.open(dashboard_path, mode="w", encoding="utf-8") as file:
        await file.write(yaml_content)

    return DASHBOARD_REL_PATH


async def async_setup_dashboard(hass: HomeAssistant) -> None:
    """Set up and register the GeoZones sidebar panel dashboard."""
    brand_dir = hass.config.path("custom_components/geozones/brand")
    if os.path.exists(brand_dir):
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    url_path="/geozones_static",
                    path=brand_dir,
                    cache_headers=True,
                )
            ]
        )

    rel_path = await async_generate_dashboard_yaml(hass)

    if "lovelace" in hass.data and hasattr(hass.data["lovelace"], "dashboards"):
        hass.data["lovelace"].dashboards["geozones"] = LovelaceYAML(
            hass, "geozones", {"mode": "yaml", "filename": rel_path}
        )

    async_register_built_in_panel(
        hass,
        component_name="lovelace",
        sidebar_title="GeoZones",
        sidebar_icon="mdi:map-marker-path",
        frontend_url_path="geozones",
        config={
            "mode": "yaml",
            "title": "GeoZones",
            "icon": "mdi:map-marker-path",
        },
        require_admin=False,
    )


async def async_remove_dashboard(hass: HomeAssistant) -> None:
    """Remove the GeoZones sidebar panel dashboard."""
    async_remove_panel(hass, "geozones")
    if "lovelace" in hass.data and hasattr(hass.data["lovelace"], "dashboards"):
        hass.data["lovelace"].dashboards.pop("geozones", None)
