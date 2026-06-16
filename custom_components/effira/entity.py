"""Shared entity helpers for Effira OPTi."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ADDRESS, DOMAIN


class EffiraBaseEntity(CoordinatorEntity):
    """Base class for Effira coordinator-backed entities."""

    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator)
        self._config_entry = config_entry

    @property
    def device_info(self):
        address = self._config_entry.data.get(CONF_ADDRESS) or {}
        return {
            "identifiers": {(DOMAIN, self.coordinator.asset_id)},
            "name": self.coordinator.device_name,
            "manufacturer": "Effira Energy",
            "model": "OPTi",
            "serial_number": self.coordinator.client_id or self.coordinator.asset_id,
            "suggested_area": address.get("city"),
        }
