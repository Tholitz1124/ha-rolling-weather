from __future__ import annotations
from datetime import timedelta
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, Event, HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.helpers.restore_state import RestoreEntity

_LOGGER = logging.getLogger(__name__)

PAST_SLOTS = [
    "day_minus_6",
    "day_minus_5",
    "day_minus_4",
    "day_minus_3",
    "day_minus_2",
    "day_minus_1",
]

FUTURE_SLOTS = [
    "today",
    "day_plus_1",
    "day_plus_2",
    "day_plus_3",
    "day_plus_4",
    "day_plus_5",
    "day_plus_6",
]

SLOTS = PAST_SLOTS + FUTURE_SLOTS

# Maps Open-Meteo WMO weather codes to Home Assistant weather condition strings
WMO_TO_HA_CONDITION: dict[int, str] = {
    0: "sunny",
    1: "sunny",
    2: "partlycloudy",
    3: "cloudy",
    45: "fog",
    48: "fog",
    51: "rainy",
    53: "rainy",
    55: "rainy",
    56: "snowy-rainy",
    57: "snowy-rainy",
    61: "rainy",
    63: "rainy",
    65: "pouring",
    66: "snowy-rainy",
    67: "snowy-rainy",
    71: "snowy",
    73: "snowy",
    75: "snowy",
    77: "snowy",
    80: "rainy",
    81: "rainy",
    82: "pouring",
    85: "snowy",
    86: "snowy",
    95: "lightning",
    96: "lightning-rainy",
    99: "lightning-rainy",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    weather_entity = entry.data["weather_entity"]
    async_add_entities([RollingWeatherSensor(hass, entry.entry_id, weather_entity)], True)


class RollingWeatherSensor(RestoreEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Rolling 7 Day Weather"
    _attr_icon = "mdi:weather-partly-cloudy"

    def __init__(self, hass: HomeAssistant, entry_id: str, weather_entity: str) -> None:
        self.hass = hass
        self._weather_entity = weather_entity
        self._attr_unique_id = f"{entry_id}_rolling_7_day"
        self._data: dict[str, str | None] = {slot: None for slot in SLOTS}

    @property
    def native_value(self) -> str | None:
        return self._data.get("today")

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        return dict(self._data)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        # Restore persisted history across reboots
        if (last_state := await self.async_get_last_state()) is not None:
            for slot in SLOTS:
                val = last_state.attributes.get(slot)
                if val and val != "unknown":
                    self._data[slot] = val

        async def _initial_sync(_event: Event | None = None) -> None:
            await self._async_backfill_missing_past_days()

            # If the weather entity isn't registered yet, wait for it to appear
            if self.hass.states.get(self._weather_entity) is None:
                _LOGGER.debug(
                    "Waiting for %s to become available before fetching forecast",
                    self._weather_entity,
                )
                unsub = None

                @callback
                def _on_weather_ready(event: Event) -> None:
                    if unsub:
                        unsub()
                    self.hass.async_create_task(self._async_fetch_forecast())

                unsub = async_track_state_change_event(
                    self.hass, [self._weather_entity], _on_weather_ready
                )
                self.async_on_remove(unsub)
                self.async_write_ha_state()
                return

            await self._async_fetch_forecast()

        if self.hass.state is CoreState.running:
            await _initial_sync()
        else:
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _initial_sync)

        # Shift days at 00:01:00 daily
        self.async_on_remove(
            async_track_time_change(
                self.hass, self._async_midnight_shift, hour=0, minute=1, second=0
            )
        )

        # Refresh today + future forecast every hour
        self.async_on_remove(
            async_track_time_interval(
                self.hass, self._async_hourly_update, timedelta(hours=1)
            )
        )

    @callback
    async def _async_midnight_shift(self, _now) -> None:
        self._data["day_minus_6"] = self._data.get("day_minus_5")
        self._data["day_minus_5"] = self._data.get("day_minus_4")
        self._data["day_minus_4"] = self._data.get("day_minus_3")
        self._data["day_minus_3"] = self._data.get("day_minus_2")
        self._data["day_minus_2"] = self._data.get("day_minus_1")

        weather_state = self.hass.states.get(self._weather_entity)
        fallback = weather_state.state if weather_state else None
        self._data["day_minus_1"] = self._data.get("today") or fallback

        await self._async_backfill_missing_past_days()
        await self._async_fetch_forecast()

    @callback
    async def _async_hourly_update(self, _now) -> None:
        await self._async_fetch_forecast()

    def _resolve_coordinates(self) -> tuple[float | None, float | None]:
        """Check selected weather entity attributes first, then fall back to hass.config."""
        weather_state = self.hass.states.get(self._weather_entity)
        if weather_state is not None:
            attrs = weather_state.attributes
            lat = attrs.get("latitude") if attrs.get("latitude") is not None else attrs.get("lat")
            lon = attrs.get("longitude") if attrs.get("longitude") is not None else attrs.get("lon")
            if lat is not None and lon is not None:
                try:
                    return float(lat), float(lon)
                except (TypeError, ValueError):
                    _LOGGER.debug(
                        "Invalid coordinates on %s (%s, %s); falling back to Home Assistant config",
                        self._weather_entity,
                        lat,
                        lon,
                    )

        return self.hass.config.latitude, self.hass.config.longitude

    async def _async_backfill_missing_past_days(self) -> None:
        """Populate only missing past slots using Open-Meteo historical daily codes."""
        missing_slots = [
            slot for slot in PAST_SLOTS if not self._data.get(slot) or self._data.get(slot) == "unknown"
        ]
        if not missing_slots:
            return

        lat, lon = self._resolve_coordinates()
        if lat is None or lon is None:
            _LOGGER.warning(
                "No coordinates found on %s or Home Assistant config; skipping Open-Meteo backfill",
                self._weather_entity,
            )
            return

        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&daily=weather_code&past_days=6&forecast_days=1&timezone=auto"
        )

        try:
            session = async_get_clientsession(self.hass)
            async with session.get(url, timeout=15) as resp:
                resp.raise_for_status()
                payload = await resp.json()

            codes = payload.get("daily", {}).get("weather_code", [])
            # Open-Meteo returns indices 0..5 for [day_minus_6 .. day_minus_1] and index 6 for today
            for idx, slot in enumerate(PAST_SLOTS):
                if (not self._data.get(slot) or self._data.get(slot) == "unknown") and len(codes) > idx:
                    code = codes[idx]
                    if code is not None:
                        self._data[slot] = WMO_TO_HA_CONDITION.get(int(code), "cloudy")
        except Exception as err:
            _LOGGER.warning("Failed to backfill past weather from Open-Meteo: %s", err)

    async def _async_fetch_forecast(self) -> None:
        """Fetch today and future daily conditions from the configured HA weather entity."""
        try:
            response = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"entity_id": self._weather_entity, "type": "daily"},
                blocking=True,
                return_response=True,
            )
            forecast = response.get(self._weather_entity, {}).get("forecast", [])
            for idx, key in enumerate(FUTURE_SLOTS):
                if len(forecast) > idx:
                    self._data[key] = forecast[idx].get("condition")
        except Exception as err:
            _LOGGER.warning("Failed to fetch daily forecast from %s: %s", self._weather_entity, err)

        self.async_write_ha_state()