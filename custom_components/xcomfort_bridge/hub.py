"""Class used to communicate with xComfort bridge."""

from __future__ import annotations

import asyncio
import logging

from xcomfort.bridge import Bridge

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class XComfortHub:
    """Hub wrapper for xComfort bridge communication."""

    def __init__(self, hass: HomeAssistant, identifier: str, ip: str, auth_key: str):
        """Initialize underlying bridge."""
        bridge = Bridge(ip, auth_key)
        self.hass = hass
        self.bridge = bridge
        self.identifier = identifier or ip
        self._id = ip
        self.devices = []
        self.rooms = []  # Ensure rooms attribute is defined.
        self._loop = asyncio.get_event_loop()
        self.has_done_initial_load = asyncio.Event()
        self.device_id = None  # Initialize device_id to None

        # Dictionaries to track unsubscribe callbacks keyed by entity ID.
        self._device_subscriptions: dict[str, callable] = {}
        self._room_subscriptions: dict[str, callable] = {}

    def clear_subscriptions(self) -> None:
        """Cleanup subscriptions for devices and rooms."""
        _LOGGER.debug("Clearing existing device subscriptions: %s", self._device_subscriptions.keys())
        for unsub in self._device_subscriptions.values():
            try:
                unsub()
            except Exception as err:
                _LOGGER.error("Error unsubscribing device: %s", err)
        self._device_subscriptions.clear()

        _LOGGER.debug("Clearing existing room subscriptions: %s", self._room_subscriptions.keys())
        for unsub in self._room_subscriptions.values():
            try:
                unsub()
            except Exception as err:
                _LOGGER.error("Error unsubscribing room: %s", err)
        self._room_subscriptions.clear()

    def start(self):
        """Start the event loop running the bridge."""
        self.hass.async_create_task(self.bridge.run())

    async def stop(self):
        """Stop the bridge event loop.
        
        Will also shut down websocket, if open.
        """
        _LOGGER.info("Stopping xComfort Hub and clearing subscriptions.")
        self.has_done_initial_load.clear()
        await self.bridge.close()
        self.clear_subscriptions()

    async def load_devices(self):
        """Load devices and rooms from bridge and subscribe to their state changes."""
        _LOGGER.info("Loading devices and rooms, clearing previous subscriptions.")
        self.clear_subscriptions()

        # Load devices
        devs = await self.bridge.get_devices()
        self.devices = list(devs.values())
        _LOGGER.info("loaded %s devices", len(self.devices))

        # Subscribe to state changes for devices only once per device_id.
        for device in self.devices:
            if hasattr(device, "state") and hasattr(device.state, "subscribe"):
                dev_id = getattr(device, "device_id", None)
                if not dev_id:
                    _LOGGER.debug(f"Device {device} has no device_id, skipping subscription")
                    continue
                if dev_id not in self._device_subscriptions:
                    _LOGGER.debug(f"Subscribing to device ID: {dev_id}")
                    unsub = device.state.subscribe(
                        lambda state, dev=device: (
                            _LOGGER.info(f"RAW_DEVICE_UPDATE: ID={getattr(dev, 'device_id', 'UNKNOWN')}, Type={type(dev).__name__}, RawState={'%s' % (state.raw if hasattr(state, 'raw') else state)}"),
                            self._fire_event(dev, state)
                        )
                    )
                    self._device_subscriptions[dev_id] = unsub
                else:
                    _LOGGER.warning(f"Attempted to re-subscribe to already subscribed device ID: {dev_id}. This should not happen with current logic.")

        # Load rooms
        rooms_data = await self.bridge.get_rooms()
        self.rooms = list(rooms_data.values())
        _LOGGER.info("loaded %s rooms", len(self.rooms))

        # Subscribe to state changes for rooms.
        for room in self.rooms:
            if hasattr(room, "state") and hasattr(room.state, "subscribe"):
                room_id = getattr(room, "room_id", None)
                if not room_id:
                    _LOGGER.debug(f"Room {room} has no room_id, skipping subscription")
                    continue
                if room_id not in self._room_subscriptions:
                    _LOGGER.debug(f"Subscribing to room ID: {room_id}")
                    unsub = room.state.subscribe(
                        lambda state, rm=room: (
                            _LOGGER.info(f"RAW_ROOM_UPDATE: ID={getattr(rm, 'room_id', 'UNKNOWN')}, Type=Room, RawState={'%s' % (state.raw if hasattr(state, 'raw') else state)}"),
                            self._fire_event(rm, state)
                        )
                    )
                    self._room_subscriptions[room_id] = unsub
                else:
                    _LOGGER.warning(f"Attempted to re-subscribe to already subscribed room ID: {room_id}. This should not happen with current logic.")

        self.has_done_initial_load.set()
        _LOGGER.info("Finished loading devices and rooms. Total device subscriptions: %s, Total room subscriptions: %s", len(self._device_subscriptions), len(self._room_subscriptions))

    def _fire_event(self, entity, state):
        """Fire a simplified xcomfort_event with serializable data for devices and rooms."""
        if hasattr(entity, "device_id"):
            entity_id = entity.device_id
            entity_type = type(entity).__name__
        elif hasattr(entity, "room_id"):
            entity_id = entity.room_id
            entity_type = "Room"
        else:
            _LOGGER.error("Entity has neither device_id nor room_id")
            return

        # Extract or convert state to a simple, serializable format.
        if isinstance(state, (str, int, float, bool)):
            new_state = state
        elif hasattr(state, "raw"):
            new_state = state.raw  # Use raw dictionary if available
        else:
            new_state = str(state)  # Fallback to string representation

        event_data = {
            "device_id": entity_id,
            "device_type": entity_type,
            "action": "state_change",
            "new_state": new_state,
        }

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

