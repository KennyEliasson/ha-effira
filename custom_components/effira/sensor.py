"""Sensor entities for Effira OPTi."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass

from .const import DOMAIN
from .entity import EffiraBaseEntity


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Effira sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [
            EffiraStatusSensor(coordinator, config_entry),
            EffiraTempSensor(coordinator, config_entry),
            EffiraPlannedControlSensor(coordinator, config_entry),
            EffiraDailyConsumptionSensor(coordinator, config_entry),
            EffiraPreviousHourConsumptionSensor(coordinator, config_entry),
        ]
    )


class EffiraBaseSensor(EffiraBaseEntity, SensorEntity):
    """Base class for Effira coordinator-backed sensors."""


class EffiraStatusSensor(EffiraBaseSensor):
    """Last action reported by the heat pump."""

    _attr_name = "Effira Last Action"

    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{self.coordinator.asset_id}_status"

    @property
    def native_value(self):
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


class EffiraTempSensor(EffiraBaseSensor):
    """Latest measured temperature as reported by the Effira system."""

    _attr_name = "Effira Temperature"
    _attr_native_unit_of_measurement = "°C"
    _attr_device_class = SensorDeviceClass.TEMPERATURE

    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{self.coordinator.asset_id}_temp"

    @property
    def native_value(self):
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("temp")


class EffiraPlannedControlSensor(EffiraBaseSensor):
    """Current planned control state from the operation planner."""

    _attr_name = "Effira Planned Control"

    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{self.coordinator.asset_id}_planned_control"

    @property
    def native_value(self):
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

    _attr_name = "Effira Heat Pump Consumption Today"
    _attr_icon = "mdi:calendar-today"
    _attr_native_unit_of_measurement = "kWh"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{self.coordinator.asset_id}_daily_heatpump_consumption"

    @property
    def native_value(self):
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("daily_heatpump_consumption")


class EffiraPreviousHourConsumptionSensor(EffiraBaseSensor):
    """Previous hour's heat pump consumption."""

    _attr_name = "Effira Heat Pump Consumption Previous Hour"
    _attr_icon = "mdi:clock-time-three-outline"
    _attr_native_unit_of_measurement = "kWh"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = (
            f"{self.coordinator.asset_id}_previous_hour_heatpump_consumption"
        )

    @property
    def native_value(self):
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("previous_hour_heatpump_consumption")
