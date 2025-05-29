"""The Almatel Balance integration."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from .const import DOMAIN, CONF_UPDATE_INTERVAL

class AlmatelConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="Almatel", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_UPDATE_INTERVAL, default=60): int,
            })
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        return AlmatelOptionsFlowHandler(config_entry)


class AlmatelOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Almatel."""

    def __init__(self, config_entry):
        self._config_entry = config_entry
        self._options = config_entry.options
        self._data = config_entry.data

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_UPDATE_INTERVAL,
                    default=self._options.get(CONF_UPDATE_INTERVAL, self._data.get(CONF_UPDATE_INTERVAL, 60))
                ): int
            })
        )
