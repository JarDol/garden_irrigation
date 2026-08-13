"""Garden Irrigation - własna integracja HA do inteligentnego nawadniania ogrodu."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_MINUTES,
    ATTR_PLANT_KEYS,
    ATTR_ZONE_ID,
    DOMAIN,
    SERVICE_APPROVE_ALL,
    SERVICE_APPROVE_ZONE,
    SERVICE_CANCEL_NEW_PLANTING,
    SERVICE_RUN_SEQUENCE_BEFORE_SUNRISE,
    SERVICE_RUN_ZONE,
    SERVICE_SKIP_ZONE,
    SERVICE_START_NEW_PLANTING,
)
from .coordinator import GardenIrrigationCoordinator

PLATFORMS = ["sensor", "button", "binary_sensor", "switch"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    coordinator = GardenIrrigationCoordinator(hass, entry)
    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    async def _handle_approve_zone(call: ServiceCall) -> None:
        await coordinator.async_approve_zone(int(call.data[ATTR_ZONE_ID]))

    async def _handle_approve_all(call: ServiceCall) -> None:
        await coordinator.async_approve_all()

    async def _handle_skip_zone(call: ServiceCall) -> None:
        await coordinator.async_skip_zone(int(call.data[ATTR_ZONE_ID]))

    async def _handle_run_zone(call: ServiceCall) -> None:
        await coordinator.async_run_zone(
            int(call.data[ATTR_ZONE_ID]), int(call.data.get(ATTR_MINUTES, 10))
        )

    async def _handle_run_sequence(call: ServiceCall) -> None:
        await coordinator.async_run_sequence_before_sunrise()

    async def _handle_start_new_planting(call: ServiceCall) -> None:
        await coordinator.async_start_new_planting(
            int(call.data[ATTR_ZONE_ID]), list(call.data[ATTR_PLANT_KEYS])
        )

    async def _handle_cancel_new_planting(call: ServiceCall) -> None:
        await coordinator.async_cancel_new_planting(int(call.data[ATTR_ZONE_ID]))

    hass.services.async_register(
        DOMAIN, SERVICE_APPROVE_ZONE, _handle_approve_zone,
        schema=vol.Schema({vol.Required(ATTR_ZONE_ID): cv.positive_int}),
    )
    hass.services.async_register(DOMAIN, SERVICE_APPROVE_ALL, _handle_approve_all)
    hass.services.async_register(
        DOMAIN, SERVICE_SKIP_ZONE, _handle_skip_zone,
        schema=vol.Schema({vol.Required(ATTR_ZONE_ID): cv.positive_int}),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_RUN_ZONE, _handle_run_zone,
        schema=vol.Schema(
            {vol.Required(ATTR_ZONE_ID): cv.positive_int, vol.Optional(ATTR_MINUTES, default=10): cv.positive_int}
        ),
    )
    hass.services.async_register(DOMAIN, SERVICE_RUN_SEQUENCE_BEFORE_SUNRISE, _handle_run_sequence)
    hass.services.async_register(
        DOMAIN, SERVICE_START_NEW_PLANTING, _handle_start_new_planting,
        schema=vol.Schema(
            {
                vol.Required(ATTR_ZONE_ID): cv.positive_int,
                vol.Required(ATTR_PLANT_KEYS): vol.All(cv.ensure_list, [cv.string]),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CANCEL_NEW_PLANTING, _handle_cancel_new_planting,
        schema=vol.Schema({vol.Required(ATTR_ZONE_ID): cv.positive_int}),
    )

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator: GardenIrrigationCoordinator | None = hass.data[DOMAIN].pop(entry.entry_id, None)
        if coordinator:
            for unsub in coordinator._unsub_listeners:
                unsub()
            if coordinator._auto_trigger_unsub:
                coordinator._auto_trigger_unsub()
    return unloaded
