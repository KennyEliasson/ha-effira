"""Config flow for Effira OPTi."""

from __future__ import annotations

import logging

import requests
import voluptuous as vol
from homeassistant import config_entries

from .api import fetch_access_token_from_credentials, fetch_assets, format_asset_label
from .const import (
    CONF_ADDRESS,
    CONF_ASSET_ID,
    CONF_ASSET_NAME,
    CONF_CLIENT_ID,
    CONF_KEY_ID,
    CONF_KEY_SECRET,
    CONF_SENSOR_ID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class EffiraConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for API-key-based Effira setup."""

    VERSION = 1

    def __init__(self) -> None:
        self._key_id: str | None = None
        self._key_secret: str | None = None
        self._assets: list[dict] = []

    async def async_step_user(self, user_input=None):
        """Handle the initial setup step."""
        errors = {}

        if user_input is not None:
            key_id = user_input[CONF_KEY_ID].strip()
            key_secret = user_input[CONF_KEY_SECRET].strip()
            try:
                assets = await self.hass.async_add_executor_job(
                    _fetch_assets_from_api_key, key_id, key_secret
                )
            except requests.HTTPError as err:
                _LOGGER.warning("Effira API key validation failed: %s", err)
                errors["base"] = "invalid_auth"
            except Exception as err:
                _LOGGER.exception("Failed to fetch Effira assets: %s", err)
                errors["base"] = "cannot_fetch_assets"
            else:
                if not assets:
                    return self.async_abort(reason="no_assets")

                self._key_id = key_id
                self._key_secret = key_secret
                self._assets = assets

                if len(assets) == 1:
                    return await self._create_entry_for_asset(assets[0])

                return await self.async_step_pick_asset()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_KEY_ID): str,
                    vol.Required(CONF_KEY_SECRET): str,
                }
            ),
            errors=errors,
        )

    async def async_step_pick_asset(self, user_input=None):
        """Let the user choose which asset to configure."""
        if user_input is not None:
            asset = next(
                (asset for asset in self._assets if asset["assetId"] == user_input[CONF_ASSET_ID]),
                None,
            )
            if asset is not None:
                return await self._create_entry_for_asset(asset)

        options = {asset["assetId"]: format_asset_label(asset) for asset in self._assets}
        return self.async_show_form(
            step_id="pick_asset",
            data_schema=vol.Schema({vol.Required(CONF_ASSET_ID): vol.In(options)}),
        )

    async def _create_entry_for_asset(self, asset):
        """Create a config entry for the selected asset."""
        asset_id = asset["assetId"]
        await self.async_set_unique_id(asset_id)
        self._abort_if_unique_id_configured()

        title = format_asset_label(asset)
        return self.async_create_entry(
            title=title,
            data=_build_entry_data(asset, self._key_id, self._key_secret),
        )


def _fetch_assets_from_api_key(key_id: str, key_secret: str) -> list[dict]:
    """Validate an API key and return available assets."""
    access_token = fetch_access_token_from_credentials(key_id, key_secret)
    return fetch_assets(access_token)


def _build_entry_data(asset: dict, key_id: str, key_secret: str) -> dict:
    """Build config entry data for the selected asset."""
    address = asset.get("address") or {}
    sensors = asset.get("sensors") or []
    first_sensor = sensors[0] if sensors else {}

    return {
        CONF_KEY_ID: key_id,
        CONF_KEY_SECRET: key_secret,
        CONF_ASSET_ID: asset["assetId"],
        CONF_ASSET_NAME: asset.get("name"),
        CONF_ADDRESS: address,
        CONF_CLIENT_ID: asset.get("clientId"),
        CONF_SENSOR_ID: first_sensor.get("sensorId"),
    }
