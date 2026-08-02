"""Przyciski: zatwierdź i uruchom strefę / zatwierdź wszystkie / pomiń."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GardenIrrigationCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator: GardenIrrigationCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[ButtonEntity] = [ApproveAllButton(coordinator, entry), RunSequenceButton(coordinator, entry)]
    for zid, zone in coordinator.zones.items():
        entities.append(ApproveZoneButton(coordinator, entry, zid, zone))
        entities.append(SkipZoneButton(coordinator, entry, zid, zone))
    async_add_entities(entities)


def _device_info(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Ogród - Inteligentne Nawadnianie",
        manufacturer="DIY",
        model="Garden Irrigation",
    )


class ApproveZoneButton(CoordinatorEntity, ButtonEntity):
    _attr_icon = "mdi:check-circle-outline"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry, zid: int, zone: dict) -> None:
        super().__init__(coordinator)
        self._zid = zid
        self._attr_unique_id = f"{entry.entry_id}_zone{zid}_approve"
        self._attr_name = f"{zone['name']} - zatwierdź i uruchom"
        self._attr_suggested_object_id = f"garden_irrigation_{zone['slug']}_approve_and_run"
        self.entity_id = f"button.{self._attr_suggested_object_id}"
        self._attr_device_info = _device_info(entry)

    async def async_press(self) -> None:
        await self.coordinator.async_approve_zone(self._zid)


class SkipZoneButton(CoordinatorEntity, ButtonEntity):
    _attr_icon = "mdi:close-circle-outline"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry, zid: int, zone: dict) -> None:
        super().__init__(coordinator)
        self._zid = zid
        self._attr_unique_id = f"{entry.entry_id}_zone{zid}_skip"
        self._attr_name = f"{zone['name']} - pomiń dzisiaj"
        self._attr_suggested_object_id = f"garden_irrigation_{zone['slug']}_skip_today"
        self.entity_id = f"button.{self._attr_suggested_object_id}"
        self._attr_device_info = _device_info(entry)

    async def async_press(self) -> None:
        await self.coordinator.async_skip_zone(self._zid)


class ApproveAllButton(CoordinatorEntity, ButtonEntity):
    _attr_icon = "mdi:check-all"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_approve_all"
        self._attr_name = "Zatwierdź wszystkie oczekujące strefy"
        self._attr_suggested_object_id = "garden_irrigation_approve_all"
        self.entity_id = f"button.{self._attr_suggested_object_id}"
        self._attr_device_info = _device_info(entry)

    async def async_press(self) -> None:
        await self.coordinator.async_approve_all()


class RunSequenceButton(CoordinatorEntity, ButtonEntity):
    _attr_icon = "mdi:weather-sunset-up"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_run_sequence_sunrise"
        self._attr_name = "Zaplanuj sekwencję przed wschodem słońca"
        self._attr_suggested_object_id = "garden_irrigation_schedule_sunrise_sequence"
        self.entity_id = f"button.{self._attr_suggested_object_id}"
        self._attr_device_info = _device_info(entry)

    async def async_press(self) -> None:
        await self.coordinator.async_run_sequence_before_sunrise()
