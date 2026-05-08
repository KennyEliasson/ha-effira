"""Sensor entities for Effira OPTi."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([
        EffiraStatusSensor(coordinator, config_entry),
    ])


class EffiraBaseSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator)
        self._config_entry = config_entry

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._config_entry.entry_id)},
            "name": "Effira OPTi",
            "manufacturer": "Effira Energy",
            "model": "OPTi",
        }


class EffiraStatusSensor(EffiraBaseSensor):
    """Current override mode — 'auto' means no manual override active."""

    @property
    def unique_id(self):
        return f"{self._config_entry.entry_id}_status"

    @property
    def name(self):
        return "Effira Status"

    @property
    def state(self):
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("last_action", "auto")

    @property
    def extra_state_attributes(self):
        if self.coordinator.data is None:
            return {}
        data = self.coordinator.data
        return {
            "connected": data.get("connected", False),
            "last_action_at": data.get("last_action_at"),
        }
