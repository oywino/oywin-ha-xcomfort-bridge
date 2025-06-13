# v2 corrected
"""Support for xComfort Bridge cover shades.

Version: 2024.05.18.1
"""
import logging

from xcomfort.devices import Shade

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .hub import XComfortHub

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up the xComfort Bridge covers from a config entry."""
    hub = XComfortHub.get_hub(hass, entry)
    
    if hub is not None:
        await hub.has_done_initial_load.wait()
        
        devices = hub.devices

        shades = []
        for device in devices:
            if isinstance(device, Shade):
                shade = HASSXComfortShade(hass, hub, device)
                shades.append(shade)

        async_add_entities(shades)

class HASSXComfortShade(CoverEntity):
    """Representation of an xComfort Bridge cover device."""

    def __init__(self, hass: HomeAssistant, hub: XComfortHub, device: Shade):
        """Initialize the cover device."""
        self.hass = hass
        self.hub = hub

        self._device = device
        self._name = device.name
        # Set initial state from device, if available
        self._state = device.state.value if device.state is not None else None
        self.device_id = device.device_id
        self._unique_id = f"shade_{DOMAIN}_{hub.identifier}-{device.device_id}"
        self._device_subscription = None
        self._event_subscription = None

    @property
    def device_class(self):
        """Return the class of this device."""
        return CoverDeviceClass.SHADE

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        def _on_device_state(new_state):
            if new_state is not None:
                self._state = new_state
                self.async_write_ha_state()
        self._device_subscription = self._device.state.subscribe(_on_device_state)

        # Subscribe to xcomfort_event for this device
        @callback
        def handle_xcomfort_event(event):
            event_data = event.data
            if (event_data.get("device_id") == self.device_id and 
                event_data.get("device_type") == "Shade" and 
                event_data.get("action") == "state_change"):
                new_state = event_data.get("new_state")
                if new_state and isinstance(new_state, dict):
                    self._state = new_state
                    self.async_write_ha_state()

        self._event_subscription = self.hass.bus.async_listen("xcomfort_event", handle_xcomfort_event)

    async def async_will_remove_from_hass(self):
        """Run when entity is removed from hass."""
        if self._device_subscription is not None:
            self._device_subscription.dispose()
            self._device_subscription = None
        if self._event_subscription is not None:
            self._event_subscription()
            self._event_subscription = None

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        position = self.current_cover_position
        if position is None:
            return None
        # In Home Assistant, position 0 means fully closed
        return position == 0

    @property
    def device_info(self):
        """Return device information about this entity."""
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
        """Return the display name of this cover."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique ID."""
        return self._unique_id

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state."""
        return False

    @property
    def supported_features(self):
        """Flag supported features."""
        supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
        if self._device.supports_go_to:
            supported_features |= CoverEntityFeature.SET_POSITION
        return supported_features

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        await self._device.move_up()

    async def async_close_cover(self, **kwargs):
        """Close cover."""
        await self._device.move_down()

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        await self._device.move_stop()

    def update(self):
        """Update the entity."""
        pass

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        if self._state is None:
            return None
        # Handle both dictionary (from events) and object (from device.state.value)
        if isinstance(self._state, dict):
            position = self._state.get("shPos")
        else:
            position = getattr(self._state, "position", None)
        if position is None:
            return None
        # Invert for Home Assistant: xComfort 0 is open, 100 is closed; HA 0 is closed, 100 is open
        return 100 - position

    async def async_set_cover_position(self, **kwargs) -> None:
        """Move the cover to a specific position."""
        if (position := kwargs.get(ATTR_POSITION)) is not None:
            # Invert for xComfort: HA 0 is closed (xComfort 100), HA 100 is open (xComfort 0)
            xcomfort_position = 100 - position
            await self._device.move_to_position(xcomfort_position)