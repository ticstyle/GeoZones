# GeoZones

<p align="center">
  <img src="https://github.com/ticstyle/GeoZones/blob/main/custom_components/geozones/brand/logo.png" alt="GeoZones Logo" width="800" />
</p>

![Latest Release](https://img.shields.io/github/v/release/ticstyle/GeoZones?color=blue&label=Release)
![Last Updated](https://img.shields.io/github/last-commit/ticstyle/GeoZones?path=hacs.json&label=Maintained)
![Issues](https://img.shields.io/github/issues/ticstyle/GeoZones?color=orange&label=Issues)
![](https://img.shields.io/badge/Home%20Assistant-Custom%20Integration-blue?logo=home-assistant)
![](https://img.shields.io/badge/dynamic/json?url=https://raw.githubusercontent.com/ticstyle/GeoZones/main/hacs.json&query=%24.homeassistant&suffix=%2B&label=Home%20Assistant&logo=homeassistant)

![License](https://img.shields.io/github/license/ticstyle/GeoZones?label=License)
[![Hassfest](https://img.shields.io/github/actions/workflow/status/ticstyle/GeoZones/pipeline.yml?branch=main&job=hassfest&label=Hassfest)](https://github.com/ticstyle/GeoZones/actions/workflows/pipeline.yml)
[![HACS Validation](https://img.shields.io/github/actions/workflow/status/ticstyle/GeoZones/pipeline.yml?branch=main&job=hacs&label=HACS)](https://github.com/ticstyle/GeoZones/actions/workflows/pipeline.yml)
[![Ruff / Format](https://img.shields.io/github/actions/workflow/status/ticstyle/GeoZones/pipeline.yml?branch=main&job=sync_and_format&label=Ruff%20%2F%20Format)](https://github.com/ticstyle/GeoZones/actions/workflows/pipeline.yml)
[![Mypy](https://img.shields.io/github/actions/workflow/status/ticstyle/GeoZones/pipeline.yml?branch=main&job=mypy&label=Mypy)](https://github.com/ticstyle/GeoZones/actions/workflows/pipeline.yml)
![Installs](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=Known%20installs&url=https%3A%2F%2Fanalytics.home-assistant.io%2Fcustom_integrations.json&query=%24.geozones.total)


An asynchronous Home Assistant custom integration for advanced device tracker localization using local or remote GeoJSON layers. It cleanly processes nested, complex geometries—automatically prioritizing your smallest physical zones over larger overlapping ones.

To add this integration, please add the custom repository `https://github.com/ticstyle/GeoZones/` to HACS in your Home Assistant setup.

## 🌐 Supported Languages
This integration is written and maintained exclusively in **English**. All entity states, attributes, configuration dialogues, and logging diagnostic files use English standards.

## ✨ Features
* **Smallest-Area Priority Hierarchy:** Automatically parses your GeoJSON data, exploding any complex `MultiPolygon` arrays into clean individual polygons. It then automatically sorts them from smallest to largest area, ensuring that nested sub-zones (like a small store inside a large shopping district) match first.
* **Smart Wi-Fi SSID Localizing:** Pairs with your device's native companion app network sensor. It features an intelligent keyword matching algorithm that automatically ignores hardware BSSID/MAC addresses, isolates your true network SSID, and binds your tracking state instantly to home when connected to a designated Wi-Fi network.
* **GPS Jitter & Accuracy Filtering:** Configure a customized maximum GPS accuracy threshold (defaults to 50 meters) to ignore sloppy coordinate drift, preventing false-positive zone updates during weak signal telemetry events.
* **In-Memory RAM Caching:** Files are read into memory exactly once at startup or after update sequences. This prevents slow disk I/O reads or loop bottlenecks during high-frequency real-time GPS coordinate telemetry updates.
* **Nightly Auto-Sync Sweeps:** Every night at exactly **02:37 AM**, the integration wakes up to redownload, validate, and resort all mapped GeoJSON configurations, ensuring your local spatial assets stay up to date.
* **Strict Validation Guardrails:** Protects your core engine loops by scanning structural constraints. If a processed workspace target exceeds **2,500 individual zones** or **250,000 vertices**, the layout drops safely and flags error reports into your system logs.

## 🚀 Installation

[![](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ticstyle&repository=GeoZones&category=Integration)

Via [HACS](https://hacs.xyz/) or manually copy the `geozones` folder from the [latest release](https://github.com/ticstyle/GeoZones/releases/latest) to the `custom_components` folder inside your Home Assistant configuration directory.

## ⚙️ Configuration

[![](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=geozones)

Add and adjust the integration via the Home Assistant User Interface. The setup step can be run multiple times to spin up separate mirrored entity layers for different tracking devices, and existing entries can be fully tweaked on the fly using the native **Reconfigure** and **Options** flow.

During setup or reconfiguration, you will be prompted to provide:
1. **Source Device Tracker:** An existing `device_tracker` entity from your registry map records.
2. **GeoJSON Source:** A web URL destination path link (starting with `http://` or `https://`) or a direct path location pointing to a local file asset.
3. **Max GPS Accuracy:** High-frequency GPS telemetry filter distance threshold in meters (default: `50`).
4. **Wi-Fi SSID Sensor (Optional):** The parent sensor tracking your device's connected SSID (automatically matched during setup).
5. **Home SSIDs (Optional):** A customizable list of network names that designate your Home wireless network profile.
6. **Home Zone (Optional):** The target zone representing your primary residence (default: `zone.home`).

---

## 📊 Available Entities
When parsing your selected source tracker (e.g., `device_tracker.iphone_stoffe`), the integration registers a mirrored tracking device entry containing a custom identifier map:

| Entity ID | Name in UI | State Example | Description |
| :--- | :--- | :--- | :--- |
| `device_tracker.geozones_my_phone` | GeoZones my_phone | `Coffee Shop` | The current matching zone name, prioritizing the smallest area structure. Returns `not_home` when outside polygon footprints. |

### Entity Attributes
The generated tracker entity exposes rich metadata parameters to analyze tracking boundaries:

* `source_entity_id`: The underlying device tracker entity being monitored.
* `containing_zones`: A nested string array listing **all overlapping zones** that the device is currently inside, sorted sequentially from smallest to largest area footprints.

---

## 🗺️ Creating & Editing Zone Files (Recommended Tool)

To visually draw, edit, or customize your geographic zones, we recommend using [Krata Maps](https://krata.app/) — a clean, free, browser-based GeoJSON editor.

---

### 1. Draw Your Zones in Krata
1. Open [krata.app](https://krata.app/) in your web browser.
2. Use the **Draw Polygon** tool to draw shapes around your desired areas (e.g., home, neighborhood, office, school).
3. Click on each drawn shape in the left pane and give it a name:
   *(Don't worry about calculating surface area — GeoZones automatically calculates polygon areas and orders overlapping boundaries for you!)*
4. Click **Export** and choose **export as .geojson** to download the file (e.g., `my_zones.geojson` or `my_zones.json`).

---

### 2. Save the File to Home Assistant
Upload your exported file into your Home Assistant `/config/geozones/` directory using your preferred method:
* **File Editor Add-on:** Navigate to `geozones/` and click **Upload File**.
* **Studio Code Server / VS Code:** Drag and drop the file into the `geozones/` folder.
* **Samba Share / SSH:** Copy the file into `/config/geozones/`.

> 💡 **Tip:** If the `geozones` folder doesn't exist yet, simply installing the GeoZones integration creates it automatically!

---

### 3. Connect the File in GeoZones
1. In Home Assistant, go to **Settings** ➔ **Devices & Services** ➔ **Add Integration** ➔ **GeoZones**.
2. GeoZones will automatically detect your file inside `/config/geozones/` and pre-fill the path for you in the setup window!

---

## 💡 Lovelace Dashboard Example

Because calculated parameters are exposed cleanly to the event bus, you can easily design contextual dashboards using native Markdown tools without complicated layout configurations.

```yaml
type: markdown
title: GeoZones status
content: >-
  {% set trackers = states.device_tracker 
     | selectattr('entity_id', 'search', '^device_tracker\\.geozones_') 
     | list %}
  {% if trackers | length > 0 %}
   ### {% for tracker in trackers %}
      ### 📱 {{ tracker.name }}
      * **Current Zone:** `{{ tracker.state }}`
      * **Source Target:** `{{ state_attr(tracker.entity_id, 'source_entity_id') }}`
      
      **Active in these zones (from smallest to largest):**{% set zones = state_attr(tracker.entity_id, 'containing_zones') %}{% if zones and zones | length > 0 %}{% for zone in zones %}
        - {{ zone }}{% endfor %}
      {% else %}
        *Not inside any custom zones at the moment.*
      {% endif %}
      {% if not loop.last %}---{% endif %}
    {% endfor %}
  {% else %}No active GeoZones tracker mirrors detected in the system entity
  registry.

  {% endif %}
```
