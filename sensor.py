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
from homeassistant.core import HomeAssistant, Event
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
                    _LOGGER.debug("Adding energy sensor for room %s", room.name)
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
        self._state = self._room.state.value  # Set initial state

    async def async_added_to_hass(self) -> None:
        """Listen for xcomfort_event when added to Home Assistant."""
        self.hass.bus.async_listen("xcomfort_event", self._handle_event)

    def _handle_event(self, event: Event):
        """Handle xcomfort_event and update state if relevant."""
        if (event.data.get("device_id") == self._room.room_id and
            event.data.get("device_type") == "Room"):
            self._state = event.data.get("new_state")
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
        self._state = self._room.state.value  # Set initial state
        self._updateTime = time.monotonic()
        self._consumption = 0.0  # Initialize as float

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()
        savedstate = await self.async_get_last_sensor_data()
        if savedstate and savedstate.native_value is not None:
            try:
                self._consumption = float(savedstate.native_value)
            except (ValueError, TypeError):
                _LOGGER.warning(f"Invalid restored value for {self._attr_unique_id}, defaulting to 0.0")
                self._consumption = 0.0
        else:
            self._consumption = 0.0  # Default to 0.0 if no valid state
        self.hass.bus.async_listen("xcomfort_event", self._handle_event)

    def _handle_event(self, event: Event):
        """Handle xcomfort_event and update state if relevant."""
        if (event.data.get("device_id") == self._room.room_id and
            event.data.get("device_type") == "Room"):
            self._state = event.data.get("new_state")
            self.async_write_ha_state()

    def calculate(self):
        """Calculate energy consumption since last update."""
        if self._state is None or not hasattr(self._state, 'power'):
            _LOGGER.debug(f"Skipping calculation for {self._attr_unique_id}: state or power unavailable")
            return
        now = time.monotonic()
        timediff = math.floor(now - self._updateTime)  # number of seconds since last update
        power = self._state.power
        if power is not None:
            self._consumption += (power / 3600 / 1000 * timediff)  # Calculate in kWh
            self._updateTime = now
        else:
            _LOGGER.debug(f"Power is None for {self._attr_unique_id}, skipping calculation")

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
        if self._state is None:
            return None
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
        self._state = self._device.state.value if self._device.state is not None else None  # Set initial state value

    async def async_added_to_hass(self) -> None:
        """Listen for xcomfort_event when added to Home Assistant."""
        self.hass.bus.async_listen("xcomfort_event", self._handle_event)

    def _handle_event(self, event: Event):
        """Handle xcomfort_event and update state if relevant."""
        if (event.data.get("device_id") == self._device.device_id and
            event.data.get("device_type") == "RcTouch"):
            self._state = event.data.get("new_state")
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
        if self._state is None:
            return None
        elif isinstance(self._state, dict):
            return self._state.get("humidity")
        elif hasattr(self._state, "humidity"):
            return self._state.humidity
        elif isinstance(self._state, (int, float)):
            return self._state
        else:
            _LOGGER.error(f"Unexpected state type for {self._attr_unique_id}: {type(self._state)}")
            return None

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
        initial_state = self._device.state
        self._state = "on" if initial_state else "off" if initial_state is not None else None

    async def async_added_to_hass(self) -> None:
        """Listen for xcomfort_event when added to Home Assistant."""
        self.hass.bus.async_listen("xcomfort_event", self._handle_event)

    def _handle_event(self, event: Event):
        """Handle xcomfort_event and update state if relevant."""
        if (event.data.get("device_id") == self._device.device_id and
            event.data.get("device_type") == "Rocker"):
            new_state = event.data.get("new_state")
            self._state = "on" if new_state else "off" if new_state is not None else None
            self.async_write_ha_state()

    @property
    def native_value(self) -> str | None:
        """Return the current state of the Rocker as a string."""
        return self._state

    @property
    def device_info(self) -> dict:
        """Return device information for the Rocker."""
        return {
            "identifiers": {(DOMAIN, self._device.device_id)},
            "name": self._device.name,
            "manufacturer": "Eaton",
            "model": "Rocker",
        }

    @property
    def should_poll(self) -> bool:
        """Disable polling since we use event listeners."""
        return False