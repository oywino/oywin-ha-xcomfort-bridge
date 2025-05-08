"""Support for Xcomfort sensors."""

from __future__ import annotations

import logging
import math
import time
from typing import cast

from xcomfort.bridge import Room
from xcomfort.devices import RcTouch, Rocker

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .hub import XComfortHub

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up xComfort sensor devices."""
    hub = XComfortHub.get_hub(hass, entry)

    async def _wait_for_hub_then_setup():
        await hub.has_done_initial_load.wait()

        rooms = hub.rooms
        devices = hub.devices

        _LOGGER.debug("Found %s xcomfort rooms", len(rooms))
        _LOGGER.debug("Found %s xcomfort devices", len(devices))

        sensors = []
        for room in rooms:
            if room.state.value is not None:
                if room.state.value.power is not None:
                    _LOGGER.debug("Adding power sensor for room %s", room.name)
                    sensors.append(XComfortPowerSensor(hub, room))

                if room.state.value.temperature is not None:
                    _LOGGER.debug("Adding temperature sensor for room %s", room.name)
                    sensors.append(XComfortEnergySensor(hub, room))

        for device in devices:
            if isinstance(device, RcTouch):
                _LOGGER.debug("Adding humidity sensor for device %s", device)
                sensors.append(XComfortHumiditySensor(hub, device))
            elif isinstance(device, Rocker):
                _LOGGER.debug("Adding Rocker sensor: %s", device)
                sensors.append(XComfortRockerSensor(hub, device))

        _LOGGER.debug("Added %s sensors", len(sensors))
        async_add_entities(sensors)

    entry.async_create_task(hass, _wait_for_hub_then_setup())

class XComfortPowerSensor(SensorEntity):
    """Entity class for xComfort power sensors."""

    def __init__(self, hub: XComfortHub, room: Room):
        """Initialize the power sensor entity.

        Args:
            hub: XComfortHub instance
            room: Room instance

        """
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
        self._state = None
        self._room.state.subscribe(lambda state: self._state_change(state))

    def _state_change(self, state):
        """Handle state changes from the device."""
        should_update = self._state is not None

        self._state = state
        if should_update:
            self.async_write_ha_state()

    @property
    def device_class(self):
        """Return the device class."""
        return SensorDeviceClass.ENERGY

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return UnitOfEnergy.WATT_HOUR

    @property
    def native_value(self):
        """Return the current value."""
        return self._state and self._state.power

class XComfortEnergySensor(RestoreSensor):
    """Entity class for xComfort energy sensors."""

    _attr_state_class = SensorStateClass.TOTAL

    def __init__(self, hub: XComfortHub, room: Room):
        """Initialize the energy sensor entity.

        Args:
            hub: XComfortHub instance
            room: Room instance

        """
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
        self._state = None
        self._room.state.subscribe(lambda state: self._state_change(state))
        self._updateTime = time.monotonic()
        self._consumption = 0

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()
        savedstate = await self.async_get_last_sensor_data()
        if savedstate:
            self._consumption = cast(float, savedstate.native_value)

    def _state_change(self, state):
        should_update = self._state is not None
        self._state = state
        if should_update:
            self.async_write_ha_state()

    def calculate(self):
        """Calculate energy consumption since last update."""
        now = time.monotonic()
        timediff = math.floor(now - self._updateTime)  # number of seconds since last update
        self._consumption += (
            self._state.power / 3600 / 1000 * timediff
        )  # Calculate, in kWh, energy consumption since last update.
        self._updateTime = now

    @property
    def device_class(self):
        """Return the device class."""
        return SensorDeviceClass.ENERGY

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return UnitOfEnergy.KILO_WATT_HOUR

    @property
    def native_value(self):
        """Return the current value."""
        self.calculate()
        return self._consumption

class XComfortHumiditySensor(SensorEntity):
    """Entity class for xComfort humidity sensors."""

    def __init__(self, hub: XComfortHub, device: RcTouch):
        """Initialize the humidity sensor entity.

        Args:
            hub: XComfortHub instance
            device: RcTouch device instance

        """
        self._attr_device_class = SensorEntityDescription(
            key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            name="Humidity",
        )
        self._device = device
        self._attr_name = self._device.name
        self._attr_unique_id = f"humidity_{self._device.name}_{self._device.device_id}"

        self.hub = hub
        self._state = None
        self._device.state.subscribe(lambda state: self._state_change(state))

    def _state_change(self, state):
        should_update = self._state is not None

        self._state = state
        if should_update:
            self.async_write_ha_state()

    @property
    def device_class(self):
        """Return the device class."""
        return SensorDeviceClass.HUMIDITY

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return PERCENTAGE

    @property
    def native_value(self):
        """Return the current value."""
        return self._state and self._state.humidity

class XComfortRockerSensor(SensorEntity):
    """Entity class for xComfort Rocker sensors."""

    def __init__(self, hub: XComfortHub, device: Rocker):
        """Initialize the Rocker sensor entity.

        Args:
            hub: XComfortHub instance
            device: Rocker device instance

        """
        self._hub = hub
        self._device = device
        self._attr_unique_id = f"rocker_{self._device.device_id}"
        self._attr_name = self._device.name_with_controlled
        self._state = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to state changes when added to Home Assistant."""
        self._device.state.subscribe(self._state_change)

    def _state_change(self, state) -> None:
        """Handle state changes from the Rocker device."""
        _LOGGER.debug(f"Rocker {self._device.device_id} state changed to {state}")
        self._state = "on" if state else "off"
        self.schedule_update_ha_state()
        _LOGGER.debug(f"Firing event {self._attr_unique_id} with data {{'on': {state}}}")
        self.hass.bus.fire(self._attr_unique_id, {"on": state})

    @property
    def native_value(self) -> str | None:
        """Return the current state of the Rocker as a string."""
        return self._state

    @property
    def device_info(self) -> dict:
        """Return device information for the Rocker.

        This property provides metadata about the device, such as its
        identifiers, name, manufacturer, and model. It helps Home Assistant
        associate the entity with the correct device in the device registry.

        Returns:
            A dictionary containing device information.
        """
        return {
            "identifiers": {(DOMAIN, self._device.device_id)},
            "name": self._device.name,
            "manufacturer": "Eaton",
            "model": "Rocker",
        }

    @property
    def should_poll(self) -> bool:
        """Disable polling since we use subscriptions.

        This property indicates that the entity does not need to be polled
        for updates because it receives state changes via subscriptions.

        Returns:
            False, indicating that polling is not required.
        """
        return False