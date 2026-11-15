from __future__ import annotations
import json
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

PLATFORMS = ["sensor"]
JS_BASE_URL = "/rolling_weather/rolling-weather-card.js"


def _get_version() -> str:
    try:
        manifest_path = Path(__file__).parent / "manifest.json"
        with open(manifest_path, encoding="utf-8") as f:
            return json.load(f).get("version", "1.0.0")
    except Exception:
        return "1.0.0"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    js_path = Path(__file__).parent / "www" / "rolling-weather-card.js"
    
    # Append version as a cache buster (e.g., /rolling_weather/rolling-weather-card.js?v=1.0.2)
    version = _get_version()
    js_url_with_cache_buster = f"{JS_BASE_URL}?v={version}"

    await hass.http.async_register_static_paths([
        StaticPathConfig(JS_BASE_URL, str(js_path), cache_headers=False)
    ])
    add_extra_js_url(hass, js_url_with_cache_buster)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)