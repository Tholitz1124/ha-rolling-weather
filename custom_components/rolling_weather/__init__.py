from __future__ import annotations
import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, Event, HomeAssistant
from homeassistant.loader import async_get_integration

_LOGGER = logging.getLogger(__name__)

DOMAIN = "rolling_weather"
PLATFORMS = ["sensor"]
JS_BASE_URL = "/rolling_weather/rolling-weather-card.js"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    js_path = Path(__file__).parent / "www" / "rolling-weather-card.js"

    integration = await async_get_integration(hass, DOMAIN)
    version = str(integration.version or "1.0.0")
    versioned_url = f"{JS_BASE_URL}?v={version}"

    await hass.http.async_register_static_paths([
        StaticPathConfig(JS_BASE_URL, str(js_path), cache_headers=False)
    ])

    async def _sync_lovelace_resource(_event: Event | None = None) -> None:
        lovelace = hass.data.get("lovelace")
        if lovelace is None:
            _LOGGER.warning("Lovelace not found in hass.data; falling back to add_extra_js_url")
            add_extra_js_url(hass, versioned_url)
            return

        mode = getattr(lovelace, "resource_mode", getattr(lovelace, "mode", None))
        if mode != "storage":
            _LOGGER.info("Lovelace is in '%s' mode; falling back to add_extra_js_url", mode)
            add_extra_js_url(hass, versioned_url)
            return

        resources = lovelace.resources
        if not resources.loaded:
            await resources.async_load()

        existing = next(
            (item for item in resources.async_items() if item.get("url", "").startswith(JS_BASE_URL)),
            None,
        )
        if existing is None:
            await resources.async_create_item({"res_type": "module", "url": versioned_url})
            _LOGGER.info("Created Lovelace resource: %s", versioned_url)
        elif existing.get("url") != versioned_url:
            await resources.async_update_item(
                existing["id"], {"res_type": "module", "url": versioned_url}
            )
            _LOGGER.info("Updated Lovelace resource to: %s", versioned_url)

    if hass.state is CoreState.running:
        await _sync_lovelace_resource()
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _sync_lovelace_resource)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)