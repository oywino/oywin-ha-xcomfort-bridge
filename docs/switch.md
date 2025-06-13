# Enhancing switch.py for xComfort Smartstikk Support

---

# Overview

This document explains updates to switch.py in oywino/oywin-ha-xcomfort-bridge, a Home Assistant integration for xComfort devices. Starting from javydekoning/ha-xcomfort-bridge, we improved support for Smartstikk (Switching Actuator) devices, fixing their integration into Home Assistant. 

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

The updated switch.py now provides smartsticks (outlets) as 'switch' entities to Home Assistant provided the setting in the xComfort App for such entities is set to 'Appliance'. If set to 'Light' then the outlet appears in Home Assistant as 'light'

#### Why It Matters

- Smartstikk devices now appear correctly in HA with proper device linking, unlike the original where they were missing or mislinked.

## Here’s a summary of the functional enhancements and differences in switch.py version 0.4.0 compared to switch.py version 0.3.8:

- **Improved Device Filtering**:  
  switch.py v0.4.0 filters devices by checking if they are instances of the Switch class, replacing the less precise "Smartstikk" name check in switch.py v0.3.8. This ensures more accurate identification of switch devices.
- **Refined State Handling**:  
  The updated version uses SwitchState alongside DeviceState and dictionary states, tailoring state management specifically to switches. This contrasts with the earlier version which used LightState and broader logic, making switch.py v0.4.0 more focused and streamlined.
- **Subscription Cleanup**:  
  Version 0.4.0 of switch.py adds async_will_remove_from_hass to dispose of subscriptions when the entity is removed, enhancing resource management and preventing memory leaks.
- **Simplified Code**:  
  By aligning state handling with switch-specific types, switch.py v0.4.0 reduces complexity compared to the more generalized approach in the earlier version, improving maintainability.

These changes reflect a refactoring effort to enhance precision, robustness, and efficiency in the switch integration for Home Assistant.
