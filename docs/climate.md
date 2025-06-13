Functional Enhancements in climate.py v0.4.0

The `climate.py` version 0.4.0 introduces several key functional enhancements over `climate.py`version 0.3.8, primarily focusing on improved robustness, maintainability, and event handling within the Home Assistant xComfort climate integration.

Key enhancements include:

1. **Improved State Initialization**: The `__init__` method now initializes the `_state` attribute directly from the `room.state.value` if available, ensuring the climate entity has an immediate initial state upon creation.

2. **Centralized State Update Logic**: A new private method, `_update_attributes_from_state`, has been added. This method centralizes the logic for updating the `rctpreset`, `temperature`, and `currentsetpoint` attributes, making state updates more robust by handling both object and dictionary formats for the state data.

3. **Robust Event Handling**: The `async_added_to_hass` method has been refactored to listen for a centralized `xcomfort_event` on the Home Assistant event bus, instead of directly subscribing to `_room.state` changes. This provides a more flexible and reliable mechanism for receiving state updates.

4. **Dedicated Event Processing**: A new `_handle_event` method has been introduced to process the `xcomfort_event` events. This method filters events relevant to the specific room and action (state_change) and then uses the `_update_attributes_from_state` method to update the entity's attributes, leading to cleaner and more maintainable code.

5. **Enhanced Preset Mode Setting**: The `async_set_preset_mode` method now uses `elif` statements for better logical flow and includes a warning for unsupported preset modes, improving error handling.

6. **Safer Property Access**: The `current_humidity` and `hvac_action` properties have been made more resilient to missing state data. They now include checks for `_state is None` and safely access attributes using `getattr` or dictionary `get` methods, preventing potential errors and crashes when state information is incomplete or unavailable.

In summary, the changes in `climate.py` v0.4.0 aim to make the xComfort climate integration more stable, reliable, and easier to manage by improving how state is initialized, updated, and how events are handled.
