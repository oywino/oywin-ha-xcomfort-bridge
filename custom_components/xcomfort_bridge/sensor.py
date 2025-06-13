# v8
"""Support for Xcomfort sensors."""

from __future__ import annotations

import logging
import math
import time
from typing import Any

from xcomfort.bridge import Room

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .hub import XComfortHub

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    hub = XComfortHub.get_hub(hass, entry)

    async def _wait_for_hub_then_setup():
        await hub.has_done_initial_load.wait()
        rooms = hub.rooms
        sensors = []
        for room in rooms:
            if room.state.value is not None:
                if _safe_get(room.state.value, "power") is not None:
                    sensors.append(XComfortPowerSensor(hub, room))
                if _safe_get(room.state.value, "temperature") is not None:
                    sensors.append(XComfortEnergySensor(hub, room))
        async_add_entities(sensors)

    hass.async_create_task(_wait_for_hub_then_setup())

def _safe_get(state: Any, key: str):
    if state is None:
        return None
    if hasattr(state, key):
        return getattr(state, key)
    if isinstance(state, dict):
        return state.get(key)
    return None

class XComfortPowerSensor(SensorEntity):
    """Power sensor for a specific room with RxPy subscription."""

    def __init__(self, hub: XComfortHub, room: Room):
        self._attr_device_class = SensorEntityDescription(
            key="current_consumption",
            device_class=SensorDeviceClass.ENERGY,
            native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
            state_class=SensorStateClass.MEASUREMENT,
            name="Current consumption",
        )
        self.hub = hub
        self._room = room
        self._attr_name = self._room.name
        self._attr_unique_id = f"energy_{self._room.room_id}"
        self._state = self._room.state.value
        self._room_subscription = None

    async def async_added_to_hass(self) -> None:
        def _on_room_state(new_state):
            if new_state is not None and _safe_get(new_state, "power") != _safe_get(self._state, "power"):
                self._state = new_state
                self.async_write_ha_state()
        self._room_subscription = self._room.state.subscribe(_on_room_state)

    async def async_will_remove_from_hass(self):
        if self._room_subscription is not None:
            self._room_subscription.dispose()
            self._room_subscription = None

    @property
    def device_class(self):
        return SensorDeviceClass.ENERGY

    @property
    def native_unit_of_measurement(self):
        return UnitOfEnergy.WATT_HOUR

    @property
    def native_value(self):
        return _safe_get(self._state, "power")

class XComfortEnergySensor(RestoreSensor):
    """Energy sensor for a specific room with RxPy subscription."""

    _attr_state_class = SensorStateClass.TOTAL

    def __init__(self, hub: XComfortHub, room: Room):
        self._attr_device_class = SensorEntityDescription(
            key="energy_used",
            device_class=SensorDeviceClass.ENERGY,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            state_class=SensorStateClass.TOTAL_INCREASING,
            name="Energy consumption",
        )
        self.hub = hub
        self._room = room
        self._attr_name = self._room.name
        self._attr_unique_id = f"energy_kwh_{self._room.room_id}"
        self._state = self._room.state.value
        self._updateTime = time.monotonic()
        self._consumption = 0.0
        self._room_subscription = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        savedstate = await self.async_get_last_sensor_data()
        if savedstate and savedstate.native_value is not None:
            try:
                self._consumption = float(savedstate.native_value)
            except (ValueError, TypeError):
                self._consumption = 0.0
        else:
            self._consumption = 0.0

        def _on_room_state(new_state):
            if new_state is not None and _safe_get(new_state, "power") != _safe_get(self._state, "power"):
                self._state = new_state
                self.async_write_ha_state()
        self._room_subscription = self._room.state.subscribe(_on_room_state)

    async def async_will_remove_from_hass(self):
        if self._room_subscription is not None:
            self._room_subscription.dispose()
            self._room_subscription = None

    def calculate(self):
        if self._state is None:
            return
        power = _safe_get(self._state, "power")
        if power is None:
            return
        now = time.monotonic()
        timediff = math.floor(now - self._updateTime)
        self._consumption += (power / 3600 / 1000 * timediff)
        self._updateTime = now

    @property
    def device_class(self):
        return SensorDeviceClass.ENERGY

    @property
    def native_unit_of_measurement(self):
        return UnitOfEnergy.KILO_WATT_HOUR

    @property
    def native_value(self):
        self.calculate()
        return self._consumption