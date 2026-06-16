"""Binary sensor entities for Effira OPTi."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)

from .const import DOMAIN
from .entity import EffiraBaseEntity


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Effira binary sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([EffiraOnlineBinarySensor(coordinator, config_entry)])


class EffiraOnlineBinarySensor(EffiraBaseEntity, BinarySensorEntity):
    """Whether the heat pump is online according to the Effira API."""

    _attr_name = "Effira Online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{self.coordinator.asset_id}_online"

    @property
    def icon(self):
        if self.is_on is True:
            return "mdi:heat-pump"
        if self.is_on is False:
            return "mdi:heat-pump-off"
        return "mdi:heat-pump"

    @property
    def is_on(self):
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("online")
