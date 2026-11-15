from __future__ import annotations
from datetime import timedelta
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_change, async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity

_LOGGER = logging.getLogger(__name__)

SLOTS = [
    "day_minus_6",
    "day_minus_5",
    "day_minus_4",
    "day_minus_3",
    "day_minus_2",
    "day_minus_1",
    "today",
    "day_plus_1",
    "day_plus_2",
    "day_plus_3",
    "day_plus_4",
    "day_plus_5",
    "day_plus_6",
]


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

        if (last_state := await self.async_get_last_state()) is not None:
            for slot in SLOTS:
                if slot in last_state.attributes:
                    self._data[slot] = last_state.attributes[slot]

        await self._async_fetch_forecast()

        self.async_on_remove(
            async_track_time_change(
                self.hass, self._async_midnight_shift, hour=0, minute=1, second=0
            )
        )

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
        await self._async_fetch_forecast()

    @callback
    async def _async_hourly_update(self, _now) -> None:
        await self._async_fetch_forecast()

    async def _async_fetch_forecast(self) -> None:
        try:
            response = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"entity_id": self._weather_entity, "type": "daily"},
                blocking=True,
                return_response=True,
            )
            forecast = response.get(self._weather_entity, {}).get("forecast", [])
            future_keys = [
                "today",
                "day_plus_1",
                "day_plus_2",
                "day_plus_3",
                "day_plus_4",
                "day_plus_5",
                "day_plus_6",
            ]
            for idx, key in enumerate(future_keys):
                if len(forecast) > idx:
                    self._data[key] = forecast[idx].get("condition")
        except Exception as err:
            _LOGGER.warning("Failed to fetch daily forecast from %s: %s", self._weather_entity, err)

        self.async_write_ha_state()