"""Config flow for Effira OPTi.

Current implementation: manual API key entry (key_id + key_secret).

TODO (Kenny): replace step_user with OAuth 2.0 flow via Cognito so users
can log in with their Effira account instead of pasting API keys manually.
OAuth endpoints:
  authorize: https://easyserv-enduser-unstable.auth.eu-north-1.amazoncognito.com/oauth2/authorize
  token:     https://easyserv-enduser-unstable.auth.eu-north-1.amazoncognito.com/oauth2/token
  client_id: 4fmn375d1uhammpa9j3rld9kum
  scope:     enduser/access
"""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    DOMAIN,
    CONF_KEY_ID,
    CONF_KEY_SECRET,
    CONF_ASSET_ID,
    CONF_NORDPOOL_ENTITY,
    CONF_GOODWE_ENTITY,
    CONF_CHEAP_PRICE_SEK,
    CONF_SOLAR_EXPORT_W,
    DEFAULT_NORDPOOL_ENTITY,
    DEFAULT_GOODWE_ENTITY,
    DEFAULT_CHEAP_PRICE_SEK,
    DEFAULT_SOLAR_EXPORT_W,
)

STEP_USER_SCHEMA = vol.Schema({
    vol.Required(CONF_KEY_ID): str,
    vol.Required(CONF_KEY_SECRET): str,
    vol.Required(CONF_ASSET_ID): str,
    vol.Optional(CONF_NORDPOOL_ENTITY, default=DEFAULT_NORDPOOL_ENTITY): str,
    vol.Optional(CONF_GOODWE_ENTITY, default=DEFAULT_GOODWE_ENTITY): str,
    vol.Optional(CONF_CHEAP_PRICE_SEK, default=DEFAULT_CHEAP_PRICE_SEK): vol.Coerce(float),
    vol.Optional(CONF_SOLAR_EXPORT_W, default=DEFAULT_SOLAR_EXPORT_W): vol.Coerce(float),
})


class EffiraConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the Effira config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            # TODO: validate credentials against API before saving
            return self.async_create_entry(
                title=f"Effira OPTi ({user_input[CONF_ASSET_ID][:8]}...)",
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return EffiraOptionsFlow(config_entry)


class EffiraOptionsFlow(config_entries.OptionsFlow):
    """Handle options (thresholds etc.) without re-entering credentials."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data = self.config_entry.data
        schema = vol.Schema({
            vol.Optional(CONF_NORDPOOL_ENTITY, default=data.get(CONF_NORDPOOL_ENTITY, DEFAULT_NORDPOOL_ENTITY)): str,
            vol.Optional(CONF_GOODWE_ENTITY, default=data.get(CONF_GOODWE_ENTITY, DEFAULT_GOODWE_ENTITY)): str,
            vol.Optional(CONF_CHEAP_PRICE_SEK, default=data.get(CONF_CHEAP_PRICE_SEK, DEFAULT_CHEAP_PRICE_SEK)): vol.Coerce(float),
            vol.Optional(CONF_SOLAR_EXPORT_W, default=data.get(CONF_SOLAR_EXPORT_W, DEFAULT_SOLAR_EXPORT_W)): vol.Coerce(float),
        })

        return self.async_show_form(step_id="init", data_schema=schema)
