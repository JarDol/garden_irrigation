"""Switch: globalny wyłącznik/pauza całego podlewania (tryb urlopowy itp.)."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GardenIrrigationCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator: GardenIrrigationCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        IrrigationPausedSwitch(coordinator, entry),
        DynamicMadEnabledSwitch(coordinator, entry),
    ])


def _device_info(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Ogród - Inteligentne Nawadnianie",
        manufacturer="DIY",
        model="Garden Irrigation",
    )


class IrrigationPausedSwitch(CoordinatorEntity, SwitchEntity):
    """Włączony = całe podlewanie wstrzymane (tryb urlopowy, prace ogrodowe,
    zamknięta woda itp.) - blokuje zatwierdzanie ręczne, approve_all,
    sekwencję przed wschodem i tryb automatyczny, dopóki nie zostanie wyłączony."""

    _attr_icon = "mdi:pause-circle-outline"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_irrigation_paused"
        self._attr_name = "Wstrzymaj całe podlewanie"
        self._attr_suggested_object_id = "garden_irrigation_irrigation_paused"
        self.entity_id = f"switch.{self._attr_suggested_object_id}"
        self._attr_device_info = _device_info(entry)

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get("irrigation_paused"))

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_paused(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_paused(False)


class DynamicMadEnabledSwitch(CoordinatorEntity, SwitchEntity):
    """Włączony (domyślnie) = próg MAD jest co noc korygowany oficjalnym
    wzorem FAO-56 na podstawie wczorajszego ETc (przy upale próg niższy,
    minimalny odstęp między podlewaniami automatycznie pomijany przy ETc
    > 5 mm/dzień). Wyłączenie przywraca sztywny, bazowy próg MAD z wybranych
    roślin/kalibracji, bez żadnej dziennej korekty."""

    _attr_icon = "mdi:thermometer-lines"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_dynamic_mad_enabled"
        self._attr_name = "Dynamiczna korekta MAD (FAO-56)"
        self._attr_suggested_object_id = "garden_irrigation_dynamic_mad_enabled"
        self.entity_id = f"switch.{self._attr_suggested_object_id}"
        self._attr_device_info = _device_info(entry)

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get("dynamic_mad_enabled", True))

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_dynamic_mad_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_dynamic_mad_enabled(False)
