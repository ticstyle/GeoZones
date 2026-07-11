# GeoZones

<p align="center">
  <img src="https://github.com/ticstyle/GeoZones/blob/main/custom_components/geozones/brand/logo.png" alt="GeoZones Logo" width="800" />
</p>

![](https://img.shields.io/github/v/release/ticstyle/GeoZones?style=for-the-badge&color=blue)
![](https://img.shields.io/badge/Home%20Assistant-Custom%20Integration-blue?style=for-the-badge&logo=home-assistant)
[![Hassfest](https://img.shields.io/github/actions/workflow/status/ticstyle/GeoZones/validate.yml?branch=main&job=hassfest&label=Hassfest&style=for-the-badge)](https://github.com/ticstyle/GeoZones/actions/workflows/validate.yml)
[![HACS Validation](https://img.shields.io/github/actions/workflow/status/ticstyle/GeoZones/validate.yml?branch=main&job=hacs&label=HACS&style=for-the-badge)](https://github.com/ticstyle/GeoZones/actions/workflows/validate.yml)
[![Ruff](https://img.shields.io/github/actions/workflow/status/ticstyle/GeoZones/validate.yml?branch=main&job=ruff&label=Ruff&style=for-the-badge)](https://github.com/ticstyle/GeoZones/actions/workflows/validate.yml)
[![Mypy](https://img.shields.io/github/actions/workflow/status/ticstyle/GeoZones/validate.yml?branch=main&job=mypy&label=Mypy&style=for-the-badge)](https://github.com/ticstyle/GeoZones/actions/workflows/validate.yml)
![](https://img.shields.io/github/license/ticstyle/GeoZones?style=for-the-badge)
![](https://img.shields.io/github/downloads/ticstyle/GeoZones/total?style=for-the-badge&color=green)
![](https://img.shields.io/github/issues/ticstyle/GeoZones?style=for-the-badge&color=orange)

An asynchronous Home Assistant custom integration for advanced device tracker localization using local or remote GeoJSON layers. It cleanly processes nested, complex geometries—automatically prioritizing your smallest physical zones over larger overlapping spaces.

To add this integration, please add the custom repository `https://github.com/ticstyle/GeoZones/` to HACS in your Home Assistant setup.

## 🌐 Supported Languages
This integration is written and maintained exclusively in **English**. All entity states, attributes, configuration dialogues, and logging diagnostic files use English standards.

## ✨ Features
* **Smallest-Area Priority Hierarchy:** Automatically parses your GeoJSON data, exploding any complex `MultiPolygon` arrays into clean individual polygons. It then automatically sorts them from smallest to largest area, ensuring that nested sub-zones (like a small store inside a large shopping district) match first.
* **In-Memory RAM Caching:** Files are read into memory exactly once at startup or after update sequences. This prevents slow disk I/O reads or loop bottlenecks during high-frequency real-time GPS coordinate telemetry updates.
* **Nightly Auto-Sync Sweeps:** Every night at exactly **02:37 AM**, the integration wakes up to redownload, validate, and resort all mapped GeoJSON configurations, ensuring your local spatial assets stay up to date.
* **Strict Validation Guardrails:** Protects your core engine loops by scanning structural constraints. If a processed workspace target exceeds **2,500 individual zones** or **250,000 vertices**, the layout drops safely and flags error reports into your system logs.

## 🚀 Installation

[![](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ticstyle&repository=GeoZones&category=Integration)

Via [HACS](https://hacs.xyz/) or manually copy the `geozones` folder from the [latest release](https://github.com/ticstyle/GeoZones/releases/latest) to the `custom_components` folder inside your Home Assistant configuration directory.

## ⚙️ Configuration

[![](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=geozones)

Add the integration via the Home Assistant User Interface. The configuration step can be run multiple times to spin up separate mirrored entity layers for different tracking devices.

During setup, you will be prompted to provide:
1. **Source Device Tracker:** An existing `device_tracker` entity from your registry map records.
2. **GeoJSON Source:** A web URL destination path link (starting with `http://` or `https://`) or a direct path location pointing to a local file asset.

---

## 📊 Available Entities
When parsing your selected source tracker (e.g., `device_tracker.iphone_stoffe`), the integration registers a mirrored tracking device entry containing a custom identifier map:

| Entity ID | Name in UI | State Example | Description |
| :--- | :--- | :--- | :--- |
| `device_tracker.geozones_iphone_stoffe` | GeoZones iphone_stoffe | `Coffee Shop` | The current matching zone name, prioritizing the smallest area structure. Returns `not_home` when outside polygon footprints. |

### Entity Attributes
The generated tracker entity exposes rich metadata parameters to analyze tracking boundaries:

* `source_entity_id`: The underlying device tracker entity being monitored.
* `containing_zones`: A nested string array listing **all overlapping zones** that the device is currently inside, sorted sequentially from smallest to largest area footprints.

---

## 💡 Lovelace Dashboard Example

Because calculated parameters are exposed cleanly to the event bus, you can easily design contextual dashboards using native Markdown tools without complicated layout configurations.

```yaml
type: markdown
title: GeoZones Multi-Tracking
content: >
  Your current Location: **{{ states('device_tracker.geozones_phone') }}**

  {% if state_attr('device_tracker.geozones_phone', 'containing_zones')
  %}
    And here are all the zone boundaries you are inside:
    {% for zone in state_attr('device_tracker.geozones_phone', 'containing_zones') %}
      - {{ zone }}
    {% endfor %}
  {% else %}
    Currently outside known custom perimeter zones.
  {% endif %}

