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

The updated switch.py now provides smartsticks (outlets) as 'switch' entities to Home Assistant provided the setting in the xComfort App for such entities is set to 'Appliance'. If set to 'Light' then the outlet appears in Home Assistant as 'light'

#### Why It Matters

- Smartstikk devices now appear correctly in HA with proper device linking, unlike the original where they were missing or mislinked.
