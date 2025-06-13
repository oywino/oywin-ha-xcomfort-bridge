Functional Enhancements in light.py version 0.4.0 vs light.py version 0.3.8:

The `light.py` version 0.4.0 introduces a significant functional enhancement over `light.py` version 0.3.8 by changing the state update mechanism from direct RxPy subscriptions to a centralized Home Assistant event bus. This aligns with a more robust and scalable event-driven architecture for the xComfort integration.

Key enhancements include:

1. **Transition to Centralized Event Handling**: The `async_added_to_hass` method in `light.py.git` no longer subscribes directly to the device's state using RxPy (`self._device.state.subscribe`). Instead, it now listens for a centralized `xcomfort_event` on the Home Assistant event bus (`self.hass.bus.async_listen("xcomfort_event", self._handle_event)`). This is a crucial architectural change that centralizes event management within the `hub.py` file, as seen in the previous comparison.

2. **Dedicated Event Handler Method**: A new private method, `_handle_event`, has been introduced in `light.py` version 0.4.0. This method is responsible for processing the `xcomfort_event` events. It filters events based on `device_id` and `device_type` to ensure that only relevant state changes for the specific light entity are processed. This promotes cleaner code and better separation of concerns.

3. **Removal of RxPy Subscription Management**: Consequently, the `_device_subscription` attribute and the `async_will_remove_from_hass` method (which was responsible for disposing of the RxPy subscription) have been removed from `light.py` version 0.4.0. This simplifies the lifecycle management of the light entity as the subscription is now handled by the centralized `hub.py`.

4. **Improved State Update Triggering**: Instead of `self.async_write_ha_state()` being called directly within the RxPy subscription callback, `self.schedule_update_ha_state()` is now called within the `_handle_event` method. This is a more appropriate way to schedule Home Assistant state updates from an event handler.

In summary, the changes in `light.py` version 0.4.0 reflect a strategic shift towards a more centralized and efficient event handling system within the xComfort Home Assistant integration. By moving state update responsibilities to the `hub.py` and utilizing the Home Assistant event bus, the `light` entity becomes more streamlined, less coupled, and benefits from a more unified approach to state management.
