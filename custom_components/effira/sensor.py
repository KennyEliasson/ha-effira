"""Sensor entities for Effira OPTi."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([
        EffiraStatusSensor(coordinator, config_entry),
        EffiraSolarSensor(coordinator, config_entry),
        EffiraPriceSensor(coordinator, config_entry),
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
    """Shows last plan submission status."""

    @property
    def unique_id(self):
        return f"{self._config_entry.entry_id}_status"

    @property
    def name(self):
        return "Effira Plan Status"

    @property
    def state(self):
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("status")

    @property
    def extra_state_attributes(self):
        if self.coordinator.data is None:
            return {}
        data = self.coordinator.data
        plan = data.get("plan", [])
        return {
            "submitted_at": data.get("submitted_at"),
            "periods": len(plan),
            "plan": plan,
        }


class EffiraSolarSensor(EffiraBaseSensor):
    """Shows current solar export as seen by the plan logic."""

    @property
    def unique_id(self):
        return f"{self._config_entry.entry_id}_solar"

    @property
    def name(self):
        return "Effira Solar Export"

    @property
    def native_unit_of_measurement(self):
        return "W"

    @property
    def state(self):
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("solar_export_w")


class EffiraPriceSensor(EffiraBaseSensor):
    """Shows current NordPool price as seen by the plan logic."""

    @property
    def unique_id(self):
        return f"{self._config_entry.entry_id}_price"

    @property
    def name(self):
        return "Effira Current Price"

    @property
    def native_unit_of_measurement(self):
        return "SEK/kWh"

    @property
    def state(self):
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("current_price")
