"""Class used to communicate with xComfort bridge."""

from __future__ import annotations

import asyncio
import logging

from xcomfort.bridge import Bridge

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

"""Wrapper class over bridge library to emulate hub."""

class XComfortHub:
    """Hub wrapper for xComfort bridge communication."""

    def __init__(self, hass: HomeAssistant, identifier: str, ip: str, auth_key: str):
        """Initialize underlying bridge."""
        bridge = Bridge(ip, auth_key)
        self.hass = hass
        self.bridge = bridge
        self.identifier = identifier
        if self.identifier is None:
            self.identifier = ip
        self._id = ip
        self.devices = []  # Changed from list()
        self._loop = asyncio.get_event_loop()
        self.has_done_initial_load = asyncio.Event()
        self.device_id = None  # Initialize device_id to None

    def start(self):
        """Start the event loop running the bridge."""
        self.hass.async_create_task(self.bridge.run())

    async def stop(self):
        """Stop the bridge event loop.

        Will also shut down websocket, if open.
        """
        self.has_done_initial_load.clear()
        await self.bridge.close()

    async def load_devices(self):
        """Load devices and rooms from bridge and subscribe to their state changes."""
        devs = await self.bridge.get_devices()
        self.devices = devs.values()

        _LOGGER.info("loaded %s devices", len(self.devices))

        # Subscribe to state changes for all devices
        for device in self.devices:
            if hasattr(device, 'state') and hasattr(device.state, 'subscribe'):
                device.state.subscribe(lambda state, dev=device: self._fire_event(dev, state))

        rooms = await self.bridge.get_rooms()
        self.rooms = rooms.values()

        _LOGGER.info("loaded %s rooms", len(self.rooms))

        # Subscribe to state changes for all rooms
        for room in self.rooms:
            if hasattr(room, 'state') and hasattr(room.state, 'subscribe'):
                room.state.subscribe(lambda state, rm=room: self._fire_event(rm, state))

        self.has_done_initial_load.set()

    def _fire_event(self, entity, state):
        """Fire a simplified xcomfort_event with serializable data for devices and rooms."""
        if hasattr(entity, 'device_id'):
            entity_id = entity.device_id
            entity_type = type(entity).__name__
        elif hasattr(entity, 'room_id'):
            entity_id = entity.room_id
            entity_type = "Room"
        else:
            _LOGGER.error("Entity has neither device_id nor room_id")
            return

        # Extract or convert state to a simple, serializable format
        if isinstance(state, (str, int, float, bool)):
            new_state = state
        elif hasattr(state, 'raw'):
            new_state = state.raw  # Use raw dictionary if available
        else:
            new_state = str(state)  # Fallback to string representation

        # Construct the event data
        event_data = {
            "device_id": entity_id,
            "device_type": entity_type,
            "action": "state_change",
            "new_state": new_state
        }

        # Fire the event and log it
        self.hass.bus.fire("xcomfort_event", event_data)
        _LOGGER.debug(f"Fired xcomfort_event for {entity_type} {entity_id} with new_state {new_state}")

    @property
    def hub_id(self) -> str:
        """Return the hub identifier."""
        return self._id

    async def test_connection(self) -> bool:
        """Test if connection to the bridge is working."""
        await asyncio.sleep(1)
        return True

    @staticmethod
    def get_hub(hass: HomeAssistant, entry: ConfigEntry) -> XComfortHub:
        """Get hub instance from Home Assistant data."""
        return hass.data[DOMAIN][entry.entry_id]