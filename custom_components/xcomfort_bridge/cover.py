"""Support for xComfort Bridge cover shades."""
import logging

from xcomfort.devices import Shade

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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

        shades = []  # Changed from list()
        for device in devices:
            if isinstance(device, Shade):
                shade = HASSXComfortShade(hass, hub, device)
                shades.append(shade)

        _LOGGER.debug("Added %s shades", len(shades))  # Changed from f-string
        async_add_entities(shades)

class HASSXComfortShade(CoverEntity):
    """Representation of an xComfort Bridge cover device."""

    def __init__(self, hass: HomeAssistant, hub: XComfortHub, device: Shade):
        """Initialize the cover device.

        Args:
            hass: The Home Assistant instance
            hub: The xComfort Bridge hub
            device: The shade device

        """
        self.hass = hass
        self.hub = hub

        self._device = device
        self._name = device.name
        # Set initial state from device, if available
        self._state = device.state.value if device.state is not None else None
        self.device_id = device.device_id

        self._unique_id = f"shade_{DOMAIN}_{hub.identifier}-{device.device_id}"

    @property
    def device_class(self):
        """Return the class of this device."""
        return CoverDeviceClass.SHADE

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        _LOGGER.debug("Added to hass %s", self._name)  # Changed from f-string
        # Listen for centralized xcomfort events
        self.hass.bus.async_listen("xcomfort_event", self._handle_event)

    def _handle_event(self, event):
        """Handle centralized xcomfort_event and update state if relevant."""
        event_data = event.data
        if (event_data.get("device_id") == self.device_id and
                event_data.get("device_type") == "Shade"):
            self._state = event_data.get("new_state")
            _LOGGER.debug("State updated via event %s : %s", self._name, self._state)
            self.schedule_update_ha_state()

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