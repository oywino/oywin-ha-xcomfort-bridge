"""Support for XComfort Bridge."""

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import CONF_AUTH_KEY, CONF_IDENTIFIER, DOMAIN
from .hub import XComfortHub

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Boilerplate setup."""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Connect to bridge and load devices."""
    config = entry.data
    _LOGGER.debug("Config entry data: %s", config)  # Log config data for debugging

    identifier = str(config.get(CONF_IDENTIFIER))
    ip = str(config.get(CONF_IP_ADDRESS))
    auth_key = str(config.get(CONF_AUTH_KEY))

    # Check if required config values are present
    if not identifier or not ip or not auth_key:
        _LOGGER.error("Missing required configuration: identifier, ip, or auth_key")
        return False

    hub = XComfortHub(hass, identifier=identifier, ip=ip, auth_key=auth_key)
    _LOGGER.debug("Hub initialized with identifier: %s, ip: %s", identifier, ip)  # Log hub initialization

    hass.data[DOMAIN][entry.entry_id] = hub

    try:
        entry.async_create_background_task(hass, hub.bridge.run(), f"XComfort/{identifier}")
        _LOGGER.debug("Background task for bridge.run() created")  # Log task creation
    except Exception as e:
        _LOGGER.error("Failed to create background task for bridge.run(): %s", e)
        return False

    try:
        entry.async_create_task(hass, hub.load_devices())
        _LOGGER.debug("Task for load_devices() created")  # Log task creation
    except Exception as e:
        _LOGGER.error("Failed to create task for load_devices(): %s", e)
        return False

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug("Platforms loaded: %s", PLATFORMS)  # Log platform loading

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Disconnect from bridge and remove loaded devices."""
    hub = XComfortHub.get_hub(hass, entry)
    await hub.stop()

    unload_ok = all(
        await asyncio.gather(
            *[hass.config_entries.async_forward_entry_unload(entry, platform) for platform in PLATFORMS]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok