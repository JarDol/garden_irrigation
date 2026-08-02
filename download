"""Binary sensory: wykrywanie pauzy podlewania spowodowanej padającym deszczem."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ZONE_STATUS_PAUSED_RAIN
from .coordinator import GardenIrrigationCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator: GardenIrrigationCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[BinarySensorEntity] = [AnyZonePausedRainSensor(coordinator, entry)]
    for zid, zone in coordinator.zones.items():
        entities.append(ZonePausedRainSensor(coordinator, entry, zid, zone))
    async_add_entities(entities)


def _device_info(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Ogród - Inteligentne Nawadnianie",
        manufacturer="DIY",
        model="Garden Irrigation",
    )


class ZonePausedRainSensor(CoordinatorEntity, BinarySensorEntity):
    """True, gdy TA KONKRETNA strefa jest właśnie wstrzymana, bo zaczęło padać
    w trakcie jej podlewania (integracja czeka, czy to tylko krótki opad)."""

    _attr_device_class = BinarySensorDeviceClass.MOISTURE
    _attr_icon = "mdi:weather-pouring"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry, zid: int, zone: dict) -> None:
        super().__init__(coordinator)
        self._zid = zid
        self._attr_unique_id = f"{entry.entry_id}_zone{zid}_paused_rain"
        self._attr_name = f"{zone['name']} - wstrzymane z powodu deszczu"
        self._attr_suggested_object_id = f"garden_irrigation_{zone['slug']}_rain_paused"
        self.entity_id = f"binary_sensor.{self._attr_suggested_object_id}"
        self._attr_device_info = _device_info(entry)

    @property
    def is_on(self) -> bool:
        zstate = self.coordinator.data["zones"].get(str(self._zid), {})
        return zstate.get("status") == ZONE_STATUS_PAUSED_RAIN

    @property
    def extra_state_attributes(self):
        zstate = self.coordinator.data["zones"].get(str(self._zid), {})
        return {"powod": zstate.get("skip_reason")}


class AnyZonePausedRainSensor(CoordinatorEntity, BinarySensorEntity):
    """True, gdy JAKAKOLWIEK strefa jest aktualnie wstrzymana z powodu deszczu
    padającego w trakcie podlewania - wygodne do jednego automatycznego
    powiadomienia zamiast pilnowania każdej strefy osobno."""

    _attr_device_class = BinarySensorDeviceClass.MOISTURE
    _attr_icon = "mdi:weather-pouring"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_any_paused_rain"
        self._attr_name = "Podlewanie wstrzymane z powodu deszczu"
        self._attr_suggested_object_id = "garden_irrigation_any_zone_rain_paused"
        self.entity_id = f"binary_sensor.{self._attr_suggested_object_id}"
        self._attr_device_info = _device_info(entry)

    @property
    def _paused_zones(self) -> list[str]:
        names = []
        for zid, zstate in self.coordinator.data["zones"].items():
            if zstate.get("status") == ZONE_STATUS_PAUSED_RAIN:
                zone = self.coordinator.zones.get(int(zid))
                names.append(zone["name"] if zone else zid)
        return names

    @property
    def is_on(self) -> bool:
        return len(self._paused_zones) > 0

    @property
    def extra_state_attributes(self):
        return {"wstrzymane_strefy": self._paused_zones}
