"""Climate platform for xComfort integration with Home Assistant."""
import logging

from xcomfort.bridge import RctMode, RctState, Room
from xcomfort.connection import Messages

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    PRESET_COMFORT,
    PRESET_ECO,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .hub import XComfortHub

SUPPORT_FLAGS = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up the xComfort climate platform.

    Args:
        hass: Home Assistant instance
        entry: Config entry
        async_add_entities: Callback to add entities

    """
    hub = XComfortHub.get_hub(hass, entry)

    async def _wait_for_hub_then_setup():
        await hub.has_done_initial_load.wait()

        rooms = hub.rooms

        _LOGGER.debug("Found %d xcomfort rooms", len(rooms))

        rcts = []
        for room in rooms:
            if room.state.value is not None:
                if room.state.value.setpoint is not None:
                    rct = HASSXComfortRcTouch(hass, hub, room)
                    rcts.append(rct)

        _LOGGER.debug("Added %d rc touch units", len(rcts))
        async_add_entities(rcts)

    entry.async_create_task(hass, _wait_for_hub_then_setup())

class HASSXComfortRcTouch(ClimateEntity):
    """Representation of an xComfort RC Touch climate device."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.AUTO]
    _attr_supported_features = SUPPORT_FLAGS

    def __init__(self, hass: HomeAssistant, hub: XComfortHub, room: Room):
        """Initialize the climate device.

        Args:
            hass: Home Assistant instance
            hub: XComfort hub instance
            room: Room instance from xComfort

        """
        self.hass = hass
        self.hub = hub
        self._room = room
        self._name = room.name
        # Initialize state from room.state.value if available
        self._state = room.state.value if room.state else None

        # Default values
        self.rctpreset = RctMode.Comfort
        self.rctstate = RctState.Idle
        self.temperature = 20.0
        self.currentsetpoint = 20.0

        self._unique_id = f"climate_{DOMAIN}_{hub.identifier}-{room.room_id}"

        # Set initial values from state if available
        if self._state is not None:
            self._update_attributes_from_state(self._state)

    def _update_attributes_from_state(self, state):
        """Update internal attributes from the state.

        Args:
            state: The state object or dictionary

        """
        # Handle state as object or dictionary
        if hasattr(state, "raw") and state.raw is not None:
            raw = state.raw
        else:
            raw = state if isinstance(state, dict) else {}

        # Update preset mode
        if "currentMode" in raw:
            self.rctpreset = RctMode(raw["currentMode"])
        elif "mode" in raw:
            self.rctpreset = RctMode(raw["mode"])

        # Update temperature and setpoint
        self.temperature = getattr(state, "temperature", self.temperature) if hasattr(state, "temperature") else raw.get("temperature", self.temperature)
        self.currentsetpoint = getattr(state, "setpoint", self.currentsetpoint) if hasattr(state, "setpoint") else raw.get("setpoint", self.currentsetpoint)

        _LOGGER.debug("Attributes updated for %s: preset=%s, temp=%s, setpoint=%s",
                      self._name, self.rctpreset, self.temperature, self.currentsetpoint)

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        _LOGGER.debug("Added to hass %s", self._name)
        if self._state is None:
            _LOGGER.debug("Initial state is null for %s", self._name)
        
        # Listen for centralized events
        self.async_on_remove(
            self.hass.bus.async_listen("xcomfort_event", self._handle_event)
        )

    async def _handle_event(self, event):
        """Handle xcomfort_event events from the hub.

        Args:
            event: The event object

        """
        data = event.data
        if (data.get("device_type") == "Room" and 
            data.get("device_id") == self._room.room_id and 
            data.get("action") == "state_change"):
            # Update state from event
            self._state = data.get("new_state")
            if self._state is not None:
                self._update_attributes_from_state(self._state)
                self.schedule_update_ha_state()
            _LOGGER.debug("Event handled for %s: %s", self._name, data)

    async def async_set_preset_mode(self, preset_mode):
        """Set new preset mode.

        Args:
            preset_mode: The new preset mode to set

        """
        _LOGGER.debug("Set Preset mode %s", preset_mode)

        if preset_mode == "Cool":
            mode = RctMode.Cool
        elif preset_mode == PRESET_ECO:
            mode = RctMode.Eco
        elif preset_mode == PRESET_COMFORT:
            mode = RctMode.Comfort
        else:
            _LOGGER.warning("Unsupported preset mode: %s", preset_mode)
            return

        if self.rctpreset != mode:
            await self._room.set_mode(mode)
            self.rctpreset = mode
            self.schedule_update_ha_state()

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature.

        Args:
            **kwargs: Keyword arguments containing the new temperature

        """
        _LOGGER.debug("Set temperature %s", kwargs)

        # TODO: Move everything below into Room class in xcomfort-python library.
        # Latest implementation in the base library is broken, so everything moved here
        # To facilitate easier debugging inside HA.
        # Also consider changing the `mode` object on RoomState class to be just a number,
        # at current it is an object(possibly due to erroneous parsing of the 300/310-messages)
        setpoint = kwargs["temperature"]
        setpointrange = self._room.bridge.rctsetpointallowedvalues[RctMode(self.rctpreset)]

        setpoint = min(setpointrange.Max, setpoint)
        setpoint = max(setpoint, setpointrange.Min)

        payload = {
            "roomId": self._room.room_id,
            "mode": self.rctpreset.value,
            "state": self._room.state.value.rctstate.value,
            "setpoint": setpoint,
            "confirmed": False,
        }
        await self._room.bridge.send_message(Messages.SET_HEATING_STATE, payload)
        self._room.modesetpoints[self.rctpreset] = setpoint
        self.currentsetpoint = setpoint

    @property
    def device_info(self):
        """Return device information about this entity."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self._name,
            "manufacturer": "Eaton",
            "model": "RC Touch",
            "via_device": self.hub.device_id,  # Changed from self.hub.hub_id
        }

    @property
    def name(self):
        """Return the display name of this climate entity."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        The xComfort integration pushes state updates, so polling is not needed.
        """
        return False

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.temperature

    @property
    def hvac_mode(self):
        """Return current HVAC mode."""
        return HVACMode.AUTO

    @property
    def current_humidity(self):
        """Return the current humidity."""
        if self._state is None:
            return None
        if isinstance(self._state, dict):
            humidity = self._state.get("humidity")
        else:
            humidity = getattr(self._state, "humidity", None)
        return int(humidity) if humidity is not None else None

    @property
    def hvac_action(self):
        """Return the current running HVAC action."""
        if self._state is None:
            return HVACAction.IDLE
        power = self._state.get("power", 0) if isinstance(self._state, dict) else getattr(self._state, "power", 0)
        if power > 0:
            return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        if self._state is None:
            return 40.0
        return self._room.bridge.rctsetpointallowedvalues[self.rctpreset].Max

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        if self._state is None:
            return 5.0
        return self._room.bridge.rctsetpointallowedvalues[self.rctpreset].Min

    @property
    def target_temperature(self):
        """Returns the setpoint from RC touch, e.g. target_temperature."""
        return self.currentsetpoint

    @property
    def preset_modes(self):
        """Return available preset modes."""
        return ["Cool", PRESET_ECO, PRESET_COMFORT]

    @property
    def preset_mode(self):
        """Return the current preset mode."""
        if self.rctpreset == RctMode.Cool:
            return "Cool"
        if self.rctpreset == RctMode.Eco:
            return PRESET_ECO
        if self.rctpreset == RctMode.Comfort:
            return PRESET_COMFORT
        _LOGGER.warning("Unexpected preset mode: %s", self.rctpreset)
        return None