from __future__ import annotations
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

DOMAIN = "rolling_weather"


class RollingWeatherConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(
                title="Rolling 7-Day Weather",
                data=user_input,
            )

        schema = vol.Schema({
            vol.Required("weather_entity", default="weather.forecast_home"): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="weather")
            ),
        })
        return self.async_show_form(step_id="user", data_schema=schema)