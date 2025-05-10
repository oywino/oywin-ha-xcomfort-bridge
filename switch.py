"""Support for xComfort switches & Actuators."""
# by oywin
import logging

from xcomfort.devices import LightState, Light, DeviceState

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .hub import XComfortHub

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up xComfort switch devices."""
    # Pass the config entry to the hub during initialization
    hub = XComfortHub.get_hub(hass, entry)
    hub.config_entry = entry  # Store the config entry in the hub object

    async def _wait_for_hub_then_setup():
        """Wait for hub to complete initial load, then set up switch entities."""
        await hub.has_done_initial_load.wait()

        switches = []
        device_registry = dr.async_get(hass)
        for device in hub.devices:
            _LOGGER.debug("Device type: %s, ID: %s, Name: %s", type(device).__name__, device.device_id, device.name)
            if "Smartstikk" in device.name and not isinstance(device, Light):
                _LOGGER.debug("Adding Smartstikk (Appliance): %s", device)
                appliance = HASSXComfortAppliance(hass, hub, device)
                switches.append(appliance)
                device_registry.async_get_or_create(
                    config_entry_id=entry.entry_id,
                    identifiers={(DOMAIN, f"{device.device_id}")},
                    manufacturer="Eaton",
                    name=device.name,
                    model="Smartstikk",
                    via_device=(DOMAIN, entry.entry_id),
                )
                _LOGGER.debug("Registered device for Smartstikk: %s (ID: %s)", device.name, device.device_id)

        async_add_entities(switches)

    entry.async_create_task(hass, _wait_for_hub_then_setup())

class HASSXComfortAppliance(SwitchEntity):
    """Entity class for xComfort Smartstikk switches."""

    def __init__(self, hass: HomeAssistant, hub: XComfortHub, device) -> None:
        """Initialize the switch entity."""
        self.hass = hass
        self.hub = hub
        self._device = device
        self._attr_device_class = SwitchDeviceClass.OUTLET
        self._state = None
        self.device_id = device.device_id
        self._unique_id = f"switch_{DOMAIN}_{device.device_id}"

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        _LOGGER.debug("Subscribing to state updates for %s", self._device.name)
        self._device.state.subscribe(self._state_change)
        await self._fetch_initial_state()

    async def _fetch_initial_state(self) -> None:
        """Fetch initial state from the device."""
        _LOGGER.debug("Fetching initial state for %s", self._device.name)
        if hasattr(self._device, "state") and self._device.state.value is not None:
            self._state_change(self._device.state.value)
        else:
            _LOGGER.debug("No initial state available for %s", self._device.name)

    def _state_change(self, state) -> None:
        """Handle state changes from the device."""
        _LOGGER.debug("Raw state update for %s: %s", self._device.name, state)
        if isinstance(state, LightState):
            self._state = state.is_on
            _LOGGER.debug("Processed LightState for %s: %s", self._device.name, self._state)
        elif isinstance(state, DeviceState):
            state_dict = state.raw
            _LOGGER.debug("DeviceState raw dict for %s: %s", self._device.name, state_dict)
            if "switch" in state_dict:
                self._state = state_dict["switch"]
                _LOGGER.debug("Processed switch from DeviceState for %s: %s", self._device.name, self._state)
            elif "info" in state_dict and self._state is None:
                info_dict = {item["text"]: item["value"] for item in state_dict["info"] if "text" in item and "value" in item}
                _LOGGER.debug("Info dict for %s: %s", self._device.name, info_dict)
                if "1109" in info_dict:
                    self._state = info_dict["1109"] == "31"
                    _LOGGER.debug("Processed info state for %s: %s", self._device.name, self._state)
        elif isinstance(state, dict):
            if "switch" in state:
                self._state = state["switch"]
                _LOGGER.debug("Processed switch from dict for %s: %s", self._device.name, self._state)
            elif "info" in state and self._state is None:
                info_dict = {item["text"]: item["value"] for item in state["info"] if "text" in item and "value" in item}
                _LOGGER.debug("Info dict for %s: %s", self._device.name, info_dict)
                if "1109" in info_dict:
                    self._state = info_dict["1109"] == "31"
                    _LOGGER.debug("Processed info state for %s: %s", self._device.name, self._state)
        else:
            _LOGGER.debug("Unhandled state type for %s: %s", self._device.name, type(state))
        _LOGGER.debug("Final processed state for %s: %s", self._device.name, self._state)
        if self._state is not None:
            self.schedule_update_ha_state()

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        return self._state

    @property
    def name(self) -> str:
        """Return the display name of this switch."""
        return self._device.name

    @property
    def unique_id(self) -> str:
        """Return the unique ID."""
        return self._unique_id

    @property
    def should_poll(self) -> bool:
        """Return if the entity should be polled."""
        return False

    @property
    def device_info(self) -> dict:
        """Return device-specific attributes."""
        return {
            "identifiers": {(DOMAIN, f"{self.device_id}")},
            "name": self._device.name,
            "manufacturer": "Eaton",
            "model": "Smartstikk",
            "via_device": (DOMAIN, self.hub.config_entry.entry_id),
        }

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        try:
            _LOGGER.debug("Turning on %s (device_id: %s)", self._device.name, self.device_id)
            await self.hub.bridge.switch_device(self.device_id, {"switch": True})
        except Exception as e:
            _LOGGER.error("Failed to turn on %s: %s", self._device.name, str(e))
            raise

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        try:
            _LOGGER.debug("Turning off %s (device_id: %s)", self._device.name, self.device_id)
            await self.hub.bridge.switch_device(self.device_id, {"switch": False})
        except Exception as e:
            _LOGGER.error("Failed to turn off %s: %s", self._device.name, str(e))
            raise