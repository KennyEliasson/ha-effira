"""Effira OPTi integration for Home Assistant."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import (
    ACTION_BOOST,
    ACTION_NORMAL,
    ACTION_STOP,
    CONF_ASSET_ID,
    DOMAIN,
    SERVICE_BOOST,
    SERVICE_CLEAR_PLAN,
    SERVICE_NORMAL,
    SERVICE_REFRESH,
    SERVICE_SET_MANUAL_PLAN,
    SERVICE_SET_MANUAL_PLAN_FROM_NOW,
    SERVICE_STOP,
)
from .coordinator import EffiraCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["binary_sensor", "sensor"]

SERVICE_TARGET_SCHEMA = vol.Schema({vol.Optional(CONF_ASSET_ID): cv.string})
SERVICE_SET_MANUAL_PLAN_SCHEMA = SERVICE_TARGET_SCHEMA.extend(
    {
        vol.Required("action"): vol.In([ACTION_BOOST, ACTION_NORMAL, ACTION_STOP]),
        vol.Required("start"): cv.datetime,
        vol.Required("end"): cv.datetime,
    }
)
SERVICE_SET_MANUAL_PLAN_FROM_NOW_SCHEMA = SERVICE_TARGET_SCHEMA.extend(
    {
        vol.Required("action"): vol.In([ACTION_BOOST, ACTION_NORMAL, ACTION_STOP]),
        vol.Required("duration_minutes"): vol.All(vol.Coerce(int), vol.Range(min=15, max=1440)),
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Effira from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    coordinator = EffiraCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    if not hass.services.has_service(DOMAIN, SERVICE_BOOST):
        _register_services(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an Effira config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    if unload_ok and not hass.data[DOMAIN]:
        for service in (
            SERVICE_BOOST,
            SERVICE_STOP,
            SERVICE_NORMAL,
            SERVICE_CLEAR_PLAN,
            SERVICE_SET_MANUAL_PLAN,
            SERVICE_SET_MANUAL_PLAN_FROM_NOW,
            SERVICE_REFRESH,
        ):
            hass.services.async_remove(DOMAIN, service)

    return unload_ok


def _register_services(hass: HomeAssistant) -> None:
    """Register integration-wide services."""

    async def handle_action(call: ServiceCall, action: str) -> None:
        coordinator = _get_target_coordinator(hass, call)
        try:
            await coordinator.async_action(action)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

    async def handle_clear_plan(call: ServiceCall) -> None:
        coordinator = _get_target_coordinator(hass, call)
        await coordinator.async_clear_plan()

    async def handle_set_manual_plan(call: ServiceCall) -> None:
        coordinator = _get_target_coordinator(hass, call)
        try:
            await coordinator.async_set_manual_plan(
                action=call.data["action"],
                start=call.data["start"],
                end=call.data["end"],
            )
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

    async def handle_set_manual_plan_from_now(call: ServiceCall) -> None:
        coordinator = _get_target_coordinator(hass, call)
        try:
            await coordinator.async_set_manual_plan_from_now(
                action=call.data["action"],
                duration_minutes=call.data["duration_minutes"],
            )
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

    async def handle_refresh(call: ServiceCall) -> None:
        coordinator = _get_target_coordinator(hass, call)
        await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        SERVICE_BOOST,
        lambda call: handle_action(call, ACTION_BOOST),
        schema=SERVICE_TARGET_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP,
        lambda call: handle_action(call, ACTION_STOP),
        schema=SERVICE_TARGET_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_NORMAL,
        lambda call: handle_action(call, ACTION_NORMAL),
        schema=SERVICE_TARGET_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_PLAN,
        handle_clear_plan,
        schema=SERVICE_TARGET_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_MANUAL_PLAN,
        handle_set_manual_plan,
        schema=SERVICE_SET_MANUAL_PLAN_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_MANUAL_PLAN_FROM_NOW,
        handle_set_manual_plan_from_now,
        schema=SERVICE_SET_MANUAL_PLAN_FROM_NOW_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH,
        handle_refresh,
        schema=SERVICE_TARGET_SCHEMA,
    )


def _get_target_coordinator(hass: HomeAssistant, call: ServiceCall) -> EffiraCoordinator:
    """Resolve which Effira asset a service call targets."""
    coordinators = list(hass.data.get(DOMAIN, {}).values())
    if not coordinators:
        raise HomeAssistantError("No Effira assets are configured.")

    target_asset_id = call.data.get(CONF_ASSET_ID)
    if target_asset_id:
        for coordinator in coordinators:
            if coordinator.asset_id == target_asset_id:
                return coordinator
        raise HomeAssistantError(f"Effira asset '{target_asset_id}' is not configured.")

    if len(coordinators) == 1:
        return coordinators[0]

    raise HomeAssistantError(
        "Multiple Effira assets are configured. Specify asset_id in the service call."
    )
