"""Sensor entities for Effira OPTi."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ADDRESS, DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Effira sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [
            EffiraStatusSensor(coordinator, config_entry),
            EffiraOnlineSensor(coordinator, config_entry),
            EffiraTempSensor(coordinator, config_entry),
            EffiraPlannedControlSensor(coordinator, config_entry),
            EffiraDailyConsumptionSensor(coordinator, config_entry),
            EffiraPreviousHourConsumptionSensor(coordinator, config_entry),
        ]
    )


class EffiraBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for Effira coordinator-backed sensors."""

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


class EffiraStatusSensor(EffiraBaseSensor):
    """Last action reported by the heat pump."""

    @property
    def unique_id(self):
        return f"{self.coordinator.asset_id}_status"

    @property
    def name(self):
        return "Effira Last Action"

    @property
    def state(self):
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("last_action")

    @property
    def extra_state_attributes(self):
        return {
            "asset_id": self.coordinator.asset_id,
            "asset_name": self.coordinator.asset_name,
            "client_id": self.coordinator.client_id,
            "sensor_id": self.coordinator.sensor_id,
            "source": (self.coordinator.data or {}).get("last_action_source"),
        }


class EffiraOnlineSensor(EffiraBaseSensor):
    """Whether the heat pump is online according to the Effira API."""

    @property
    def unique_id(self):
        return f"{self.coordinator.asset_id}_online"

    @property
    def name(self):
        return "Effira Online"

    @property
    def state(self):
        if self.coordinator.data is None:
            return None
        online = self.coordinator.data.get("online")
        if online is True:
            return "online"
        if online is False:
            return "offline"
        return None


class EffiraTempSensor(EffiraBaseSensor):
    """Latest measured temperature as reported by the Effira system."""

    @property
    def unique_id(self):
        return f"{self.coordinator.asset_id}_temp"

    @property
    def name(self):
        return "Effira Temperature"

    @property
    def native_unit_of_measurement(self):
        return "°C"

    @property
    def device_class(self):
        return SensorDeviceClass.TEMPERATURE

    @property
    def state(self):
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("temp")


class EffiraPlannedControlSensor(EffiraBaseSensor):
    """Current planned control state from the operation planner."""

    @property
    def unique_id(self):
        return f"{self.coordinator.asset_id}_planned_control"

    @property
    def name(self):
        return "Effira Planned Control"

    @property
    def state(self):
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("planned_state")

    @property
    def extra_state_attributes(self):
        if self.coordinator.data is None:
            return {}
        return {
            "reason": self.coordinator.data.get("planned_reason"),
            "mode": self.coordinator.data.get("planned_mode"),
            "priority": self.coordinator.data.get("planned_priority"),
        }


class EffiraDailyConsumptionSensor(EffiraBaseSensor):
    """Current day's heat pump consumption."""

    @property
    def unique_id(self):
        return f"{self.coordinator.asset_id}_daily_heatpump_consumption"

    @property
    def name(self):
        return "Effira Daily Heatpump Consumption"

    @property
    def native_unit_of_measurement(self):
        return "kWh"

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def state(self):
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("daily_heatpump_consumption")


class EffiraPreviousHourConsumptionSensor(EffiraBaseSensor):
    """Previous hour's heat pump consumption."""

    @property
    def unique_id(self):
        return f"{self.coordinator.asset_id}_previous_hour_heatpump_consumption"

    @property
    def name(self):
        return "Effira Previous Hour Heatpump Consumption"

    @property
    def native_unit_of_measurement(self):
        return "kWh"

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def state(self):
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("previous_hour_heatpump_consumption")
