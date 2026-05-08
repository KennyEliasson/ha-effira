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

from .const import DOMAIN, CONF_KEY_ID, CONF_KEY_SECRET, CONF_ASSET_ID

STEP_USER_SCHEMA = vol.Schema({
    vol.Required(CONF_KEY_ID): str,
    vol.Required(CONF_KEY_SECRET): str,
    vol.Required(CONF_ASSET_ID): str,
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
