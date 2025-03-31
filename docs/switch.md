# Documentation: Enhancing switch.py for xComfort Smartstikk Support

---

# Overview

This document explains updates to switch.py in oywino/oywin-ha-xcomfort-bridge, a Home Assistant integration for xComfort devices. Starting from javydekoning/ha-xcomfort-bridge, we improved support for Smartstikk (Switching Actuator) devices, fixing their integration into Home Assistant. This guide assumes you know basic IT/IoT concepts and can follow simple Python, but not much more.

#### Prerequisites

- Home Assistant installed (2025.x recommended).
- xComfort Bridge on your network with Smartstikk devices.
- GitHub Desktop or basic Git skills to clone/pull files.

#### Original switch.py (javydekoning)

The original file from javydekoning/ha-xcomfort-bridge handled basic xComfort switches but didn’t fully support Smartstikk devices:

- Identified switches via Rockers (wall switches), not actuators like Smartstikk.
- Used static via_device="xcomfort_hub", causing device linking issues in HA.
- Lacked state updates for Smartstikk appliances.

#### Updated switch.py (oywino)

Here’s the current version with key changes highlighted. You can copy this into custom_components/xcomfort_bridge/switch.py in your HA setup.

```python
  1  """Support for xComfort Bridge switches."""
  2  import logging
  3  
  4  from xcomfort.devices import DeviceState, Light, LightState, Rockers
  5  
  6  from homeassistant.components.switch import SwitchEntity
  7  from homeassistant.config_entries import ConfigEntry
  8  from homeassistant.core import HomeAssistant
  9  from homeassistant.helpers import device_registry as dr  # Added for device linking
 10  from homeassistant.helpers.entity_platform import AddEntitiesCallback
 11  
 12  from .const import DOMAIN
 13  from .hub import XComfortHub
 14  
 15  _LOGGER = logging.getLogger(__name__)
 16  
 17  async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
 18      """Set up xComfort switches from a config entry."""
 19      hub = XComfortHub.get_hub(hass, entry)
 20      hub.config_entry = entry  # Added: Stores config entry for device linking
 21      
 22      if hub is not None:
 23          await hub.has_done_initial_load.wait()
 24          devices = hub.devices
 25  
 26          switches = []
 27          for device in devices:
 28              # Original: Only Rockers (wall switches) were added
 29              if isinstance(device, Rockers):
 30                  switch = HASSXComfortSwitch(hass, hub, device)
 31                  switches.append(switch)
 32              # Added: Support Smartstikk actuators (appliances)
 33              elif "Smartstikk" in device.name and not isinstance(device, Light):
 34                  appliance = HASSXComfortAppliance(hass, hub, device)
 35                  switches.append(appliance)
 36                  _LOGGER.debug("Adding Smartstikk (Appliance): %s (ID: %s)", device.name, device.device_id)
 37  
 38          _LOGGER.debug("Added %s switches", len(switches))
 39          async_add_entities(switches)
 40  
 41  class HASSXComfortSwitch(SwitchEntity):
 42      """Representation of an xComfort Rocker switch."""
 43      def __init__(self, hass: HomeAssistant, hub: XComfortHub, device: Rockers):
 44          self.hass = hass
 45          self.hub = hub
 46          self._device = device
 47          self._name = device.name
 48          self._state = None
 49          self.device_id = device.device_id
 50          self._unique_id = f"switch_{DOMAIN}_{hub.identifier}-{device.device_id}"
 51  
 52      @property
 53      def device_info(self):
 54          """Return device info for Home Assistant."""
 55          # Changed: Uses config entry ID instead of static string
 56          return {"identifiers": {(DOMAIN, self._unique_id)}, "name": self._name, "manufacturer": "Eaton",
 57                  "model": "Rocker", "via_device": (DOMAIN, self.hub.config_entry.entry_id)}
 58  
 59      # Rest unchanged: is_on, async_turn_on/off, etc.
 60  
 61  class HASSXComfortAppliance(SwitchEntity):
 62      """Representation of an xComfort Smartstikk appliance."""
 63      # Added: New class for Smartstikk devices
 64      def __init__(self, hass: HomeAssistant, hub: XComfortHub, device):
 65          self.hass = hass
 66          self.hub = hub
 67          self._device = device
 68          self._name = device.name
 69          self._state = None
 70          self.device_id = device.device_id
 71          self._unique_id = f"switch_{DOMAIN}_{hub.identifier}-{device.device_id}"
 72  
 73      async def async_added_to_hass(self):
 74          """Run when entity is added to Home Assistant."""
 75          if self._device.state is not None:
 76              self._device.state.subscribe(lambda state: self._state_change(state))
 77  
 78      def _state_change(self, state):
 79          """Handle state updates from the hub."""
 80          self._state = state.switch if isinstance(state, DeviceState) else state
 81          _LOGGER.debug("Final processed state for %s: %s", self._name, self._state)
 82          self.schedule_update_ha_state()
 83  
 84      @property
 85      def device_info(self):
 86          """Return device info for Home Assistant."""
 87          # Added: Links Smartstikk to hub via config entry
 88          return {"identifiers": {(DOMAIN, self._unique_id)}, "name": self._name, "manufacturer": "Eaton",
 89                  "model": "Smartstikk", "via_device": (DOMAIN, self.hub.config_entry.entry_id)}
 90  
 91      @property
 92      def is_on(self) -> bool | None:
 93          """Return if the switch is on."""
 94          return self._state
 95  
 96      async def async_turn_on(self, **kwargs):
 97          """Turn the switch on."""
 98          await self._device.turn_on()
 99  
100      async def async_turn_off(self, **kwargs):
101          """Turn the switch off."""
102          await self._device.turn_off()
103  
104      @property
105      def name(self):
106          """Return the display name."""
107          return self._name
108  
109      @property
110      def unique_id(self):
111          """Return a unique ID."""
112          return self._unique_id
113  
114      @property
115      def should_poll(self) -> bool:
116          """No polling needed."""
117          return False
```

#### Key Changes Explained

1. **Imports** (Line 5-11):
   
   - **What**: Added DeviceState, Light, LightState, device_registry as dr.
   - **Why**: DeviceState for Smartstikk states, Light/LightState to exclude dimmable devices, dr for HA device linking.
   - **How**: Imported from xcomfort.devices and HA helpers.

2. **Config Entry in Hub** (Line 20):
   
   - **What**: Added hub.config_entry = entry.
   - **Why**: Stores the HA config entry ID for use in device_info, replacing hardcoded IPs.
   - **How**: Sets it during setup so all entities can access it.

3. **Smartstikk Support** (Line 31-35):
   
   - **What**: Added a check for "Smartstikk" in device.name and created HASSXComfortAppliance.
   - **Why**: Original only handled Rockers; Smartstikk (actuators) were ignored.
   - **How**: Filters devices by name, excludes Light types, logs for debugging.

4. **Device Info Update** (Line 52, 87):
   
   - **What**: Changed via_device to (DOMAIN, self.hub.config_entry.entry_id).
   - **Why**: Links switches to the xComfort Bridge dynamically in HA’s device registry, fixing static ID issues.
   - **How**: Uses the stored config_entry ID instead of "xcomfort_hub".

5. **New Appliance Class** (Line 64-105):
   
   - **What**: Added HASSXComfortAppliance for Smartstikk devices.
   - **Why**: Provides on/off control and state updates for actuators, distinct from Rockers.
   - **How**: Subscribes to DeviceState changes, maps switch to is_on, adds async on/off methods.

#### How to Reproduce

1. Clone oywino/oywin-ha-xcomfort-bridge from GitHub.
2. Copy custom_components/xcomfort_bridge/ to your HA config/custom_components/.
3. Restart HA, configure xComfort Bridge via UI (IP, Auth-Key, Identifier).
4. Check logs for “Adding Smartstikk” messages and test switches (e.g., switch.smartstikk_gang).

#### Why It Matters

- Smartstikk devices now appear correctly in HA with proper device linking, unlike the original where they were missing or mislinked.
