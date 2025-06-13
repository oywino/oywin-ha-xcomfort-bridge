# v2
"""Support for xComfort lights.

Version: 2024.05.18.1
"""

from functools import cached_property
import logging
from math import ceil

from xcomfort.devices import Light

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .hub import XComfortHub

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up xComfort light devices."""
    hub = XComfortHub.get_hub(hass, entry)

    async def _wait_for_hub_then_setup():
        await hub.has_done_initial_load.wait()

        devices = hub.devices

        _LOGGER.debug("Found %s xcomfort devices", len(devices))

        lights = []
        for device in devices:
            if isinstance(device, Light):
                _LOGGER.debug("Adding %s", device)
                light = HASSXComfortLight(hass, hub, device)
                lights.append(light)

        _LOGGER.debug("Added %s lights", len(lights))
        async_add_entities(lights)

    entry.async_create_task(hass, _wait_for_hub_then_setup())

class HASSXComfortLight(LightEntity):
    """Entity class for xComfort lights."""

    def __init__(self, hass: HomeAssistant, hub: XComfortHub, device: Light):
        """Initialize the light entity."""
        self.hass = hass
        self.hub = hub

        self._device = device
        self._name = device.name
        # Set initial state from device, if available
        self._state = device.state.value if device.state is not None else None
        self.device_id = device.device_id
        self._unique_id = f"light_{DOMAIN}_{hub.identifier}-{device.device_id}"
        self._color_mode = ColorMode.BRIGHTNESS if self._device.dimmable else ColorMode.ONOFF
        self._device_subscription = None

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        _LOGGER.debug("Added to hass %s", self._name)
        # Subscribe directly to device's state (RxPy)
        def _on_device_state(new_state):
            if new_state is not None and new_state != self._state:
                self._state = new_state
                _LOGGER.debug("State updated via RxPy subscription %s : %s", self._name, self._state)
                self.async_write_ha_state()
        self._device_subscription = self._device.state.subscribe(_on_device_state)

    async def async_will_remove_from_hass(self):
        if self._device_subscription is not None:
            self._device_subscription.dispose()
            self._device_subscription = None

    def _get_state_value(self, key, default=None):
        """Helper method to get state values from either a dictionary or object."""
        if self._state is None:
            return default
        if isinstance(self._state, dict):
            return self._state.get(key, default)
        elif hasattr(self._state, key):
            return getattr(self._state, key)
        else:
            return default

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "Eaton",
            "model": "XXX",
            "sw_version": "Unknown",
            "via_device": self.hub.device_id,
        }

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique ID."""
        return self._unique_id

    @property
    def should_poll(self) -> bool:
        """Return if the entity should be polled for state updates."""
        return False

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        if not self.is_on:
            return None
        dimmvalue = self._get_state_value("dimmvalue", 0)
        return int(255.0 * dimmvalue / 99.0)

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._get_state_value("switch", False)

    @property
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        return self._color_mode

    @cached_property
    def supported_color_modes(self) -> set[ColorMode] | set[str] | None:
        """Return a set of supported color modes."""
        return {self._color_mode}

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        _LOGGER.debug("async_turn_on %s : %s", self._name, kwargs)
        if ATTR_BRIGHTNESS in kwargs and self._device.dimmable:
            br = ceil(kwargs[ATTR_BRIGHTNESS] * 99 / 255.0)
            _LOGGER.debug("async_turn_on br %s : %s", self._name, br)
            await self._device.dimm(br)
            # Update state immediately for responsiveness
            self._state = {"switch": True, "dimmvalue": br}
        else:
            await self._device.switch(True)
            self._state = {"switch": True}
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        _LOGGER.debug("async_turn_off %s : %s", self._name, kwargs)
        await self._device.switch(False)
        self._state = {"switch": False}
        self.async_write_ha_state()