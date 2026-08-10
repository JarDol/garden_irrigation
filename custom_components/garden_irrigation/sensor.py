"""Sensory: dobowe ET0 oraz stan/rekomendacja podlewania per strefa."""
from __future__ import annotations

import math

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, ZONE_STATUS_PENDING
from .coordinator import GardenIrrigationCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator: GardenIrrigationCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        Et0Sensor(coordinator, entry),
        WeatherInputsSensor(coordinator, entry),
        SequenceStartSensor(coordinator, entry),
        TotalWaterTodaySensor(coordinator, entry),
        TotalWaterLastWateringSensor(coordinator, entry),
        TotalWaterMonthSensor(coordinator, entry),
        TotalWaterYearSensor(coordinator, entry),
    ]
    for zid, zone in coordinator.zones.items():
        entities.append(ZoneStatusSensor(coordinator, entry, zid, zone))
        entities.append(ZoneDeficitSensor(coordinator, entry, zid, zone))
        entities.append(ZoneSoilWaterSensor(coordinator, entry, zid, zone))
        entities.append(ZoneSoilWaterProjectedSensor(coordinator, entry, zid, zone))
        entities.append(ZoneProjectedDeficitSensor(coordinator, entry, zid, zone))
        entities.append(ZoneProjectedWateringSensor(coordinator, entry, zid, zone))
        entities.append(ZoneParametersSensor(coordinator, entry, zid, zone))
        entities.append(ZoneKcSensor(coordinator, entry, zid, zone))
        entities.append(ZoneMadSensor(coordinator, entry, zid, zone))
        entities.append(ZoneMinDaysSensor(coordinator, entry, zid, zone))
        entities.append(ZoneMaxRuntimeSensor(coordinator, entry, zid, zone))
        entities.append(ZoneAreaSensor(coordinator, entry, zid, zone))
        entities.append(ZoneRateSensor(coordinator, entry, zid, zone))
        entities.append(ZoneWaterTodaySensor(coordinator, entry, zid, zone))
        entities.append(ZoneWaterLastWateringSensor(coordinator, entry, zid, zone))
        entities.append(ZoneWaterMonthSensor(coordinator, entry, zid, zone))
        entities.append(ZoneWaterYearSensor(coordinator, entry, zid, zone))
    async_add_entities(entities)


def _device_info(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="DIY",
        model="Garden Irrigation",
    )


class Et0Sensor(CoordinatorEntity, SensorEntity):
    _attr_native_unit_of_measurement = "mm/d"
    _attr_icon = "mdi:weather-sunny"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_et0"
        self._attr_name = "Ewapotranspiracja referencyjna (ET0, wczoraj)"
        self._attr_suggested_object_id = "garden_irrigation_et0_yesterday"
        self.entity_id = f"sensor.{self._attr_suggested_object_id}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        return self.coordinator.data.get("et0_yesterday")


class WeatherInputsSensor(CoordinatorEntity, SensorEntity):
    """Konsoliduje WSZYSTKIE dane pogodowe, na podstawie których integracja
    liczy zapotrzebowanie - do weryfikacji, czy nic nie jest pomijane.
    Wartość główna to metoda użyta do wczorajszego ET0 (penman_monteith /
    hargreaves / brak_danych) - reszta (temperatura, wiatr, wilgotność,
    nasłonecznienie, opad prognozowany i zmierzony) w atrybutach."""

    _attr_icon = "mdi:weather-partly-rainy"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_weather_inputs"
        self._attr_name = "Dane wejściowe pogody"
        self._attr_suggested_object_id = "garden_irrigation_weather_inputs"
        self.entity_id = f"sensor.{self._attr_suggested_object_id}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        wczoraj = self.coordinator.data.get("et0_yesterday_inputs")
        if not wczoraj:
            return "brak_danych"
        return wczoraj.get("metoda", "brak_danych")

    @property
    def extra_state_attributes(self):
        return self.coordinator.weather_verification_data()


class ZoneStatusSensor(CoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:sprinkler"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry, zid: int, zone: dict) -> None:
        super().__init__(coordinator)
        self._zid = zid
        self._attr_unique_id = f"{entry.entry_id}_zone{zid}_status"
        self._attr_name = f"{zone['name']} - zalecane podlewanie"
        self._attr_suggested_object_id = f"garden_irrigation_{zone['slug']}_recommended_watering"
        self.entity_id = f"sensor.{self._attr_suggested_object_id}"
        self._attr_device_info = _device_info(entry)
        self._attr_native_unit_of_measurement = "min"

    @property
    def native_value(self):
        zstate = self.coordinator.data["zones"].get(str(self._zid), {})
        return zstate.get("pending_min", 0)

    @property
    def extra_state_attributes(self):
        zstate = self.coordinator.data["zones"].get(str(self._zid), {})
        return {
            "status": zstate.get("status"),
            "zalecana_ilosc_mm": zstate.get("pending_mm"),
            "wymaga_zatwierdzenia": zstate.get("status") == ZONE_STATUS_PENDING,
            "pominieto_z_powodu_prognozy": zstate.get("skip_reason"),
            "kandydat_na_wymuszenie_przed_upalem": bool(zstate.get("heat_candidate", False)),
            "wymuszone_przed_upalem": bool(zstate.get("forced_heat_watering", False)),
            "ostatnie_wymuszenie_przed_upalem": zstate.get("last_forced_heat_date"),
            "ostatnie_podlewanie_sposob_zakonczenia": zstate.get("completion_method"),
            "ostatnie_podlewanie_planowany_czas_min": zstate.get("planned_runtime_min"),
            "ostatnie_podlewanie_faktyczny_czas_min": zstate.get("actual_runtime_min"),
            "ostatnie_podlewanie_wydluzenie_min": zstate.get("runtime_extended_min"),
            "opad_podczas_biezacej_pauzy_mm": zstate.get("rain_during_current_pause_mm"),
        }


class ZoneDeficitSensor(CoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:water-percent"
    _attr_native_unit_of_measurement = "mm"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry, zid: int, zone: dict) -> None:
        super().__init__(coordinator)
        self._zid = zid
        self._attr_unique_id = f"{entry.entry_id}_zone{zid}_smd"
        self._attr_name = f"{zone['name']} - deficyt wody w glebie"
        self._attr_suggested_object_id = f"garden_irrigation_{zone['slug']}_soil_water_deficit"
        self.entity_id = f"sensor.{self._attr_suggested_object_id}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        zstate = self.coordinator.data["zones"].get(str(self._zid), {})
        smd = zstate.get("smd")
        return round(smd, 1) if smd is not None else None

    @property
    def extra_state_attributes(self):
        zone = self.coordinator.zones.get(self._zid, {})
        available_water_mm = zone.get("awc_mm_per_m", 0) * (zone.get("root_depth_mm", 0) / 1000)
        return {
            "gleba": zone.get("soil_key"),
            "rosliny": zone.get("plant_keys"),
            "wyliczone_kc": zone.get("kc"),
            "wyliczona_glebokosc_korzeni_mm": zone.get("root_depth_mm"),
            "zrodlo_glebokosci_korzeni": zone.get("root_depth_source_plant"),
            "glebokosc_wybrana_recznie": not zone.get("root_depth_auto", True),
            "wyliczony_prog_mad": zone.get("mad"),
            "dostepna_woda_w_strefie_korzeniowej_mm": round(available_water_mm, 1),
        }


class ZoneSoilWaterSensor(CoordinatorEntity, SensorEntity):
    """Ile wody FAKTYCZNIE jest teraz w strefie korzeniowej (mm) - odwrotność
    deficytu: dostępna_woda_w_strefie_korzeniowej - deficyt. Ta sama wartość,
    ten sam moment aktualizacji co główny sensor deficytu, tylko podana
    'od drugiej strony' - łatwiej odczytać na pierwszy rzut oka, ile realnie
    wody ma teraz roślina do dyspozycji, zamiast tylko ile jej brakuje."""

    _attr_icon = "mdi:water"
    _attr_native_unit_of_measurement = "mm"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry, zid: int, zone: dict) -> None:
        super().__init__(coordinator)
        self._zid = zid
        self._attr_unique_id = f"{entry.entry_id}_zone{zid}_soil_water"
        self._attr_name = f"{zone['name']} - woda w glebie"
        self._attr_suggested_object_id = f"garden_irrigation_{zone['slug']}_soil_water_level"
        self.entity_id = f"sensor.{self._attr_suggested_object_id}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        zone = self.coordinator.zones.get(self._zid, {})
        zstate = self.coordinator.data["zones"].get(str(self._zid), {})
        smd = zstate.get("smd")
        if smd is None:
            return None
        available_water_mm = zone.get("awc_mm_per_m", 0) * (zone.get("root_depth_mm", 0) / 1000)
        return round(max(0.0, available_water_mm - smd), 1)

    @property
    def extra_state_attributes(self):
        zone = self.coordinator.zones.get(self._zid, {})
        zstate = self.coordinator.data["zones"].get(str(self._zid), {})
        available_water_mm = zone.get("awc_mm_per_m", 0) * (zone.get("root_depth_mm", 0) / 1000)
        smd = zstate.get("smd") or 0.0
        current = max(0.0, available_water_mm - smd)
        pct = round((current / available_water_mm) * 100, 1) if available_water_mm else None
        return {
            "pojemnosc_calkowita_strefy_korzeniowej_mm": round(available_water_mm, 1),
            "procent_pojemnosci": pct,
            "info": "Dostępna woda w strefie korzeniowej minus aktualny deficyt - ile realnie wody ma teraz roślina.",
        }


class ZoneSoilWaterProjectedSensor(CoordinatorEntity, SensorEntity):
    """To samo co 'woda w glebie', ale na podstawie przewidywanego deficytu -
    rośnie/maleje płynnie w ciągu dnia (patrz sensor 'przewidywany deficyt
    wody'), czysto informacyjny, nie wpływa na żadną decyzję."""

    _attr_icon = "mdi:water"
    _attr_native_unit_of_measurement = "mm"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry, zid: int, zone: dict) -> None:
        super().__init__(coordinator)
        self._zid = zid
        self._attr_unique_id = f"{entry.entry_id}_zone{zid}_soil_water_projected"
        self._attr_name = f"{zone['name']} - woda w glebie (na żywo)"
        self._attr_suggested_object_id = f"garden_irrigation_{zone['slug']}_projected_soil_water_level"
        self.entity_id = f"sensor.{self._attr_suggested_object_id}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        zone = self.coordinator.zones.get(self._zid, {})
        zstate = self.coordinator.data["zones"].get(str(self._zid), {})
        smd = zstate.get("smd_projected")
        if smd is None:
            return None
        available_water_mm = zone.get("awc_mm_per_m", 0) * (zone.get("root_depth_mm", 0) / 1000)
        return round(max(0.0, available_water_mm - smd), 1)

    @property
    def extra_state_attributes(self):
        zone = self.coordinator.zones.get(self._zid, {})
        zstate = self.coordinator.data["zones"].get(str(self._zid), {})
        available_water_mm = zone.get("awc_mm_per_m", 0) * (zone.get("root_depth_mm", 0) / 1000)
        smd = zstate.get("smd_projected") or 0.0
        current = max(0.0, available_water_mm - smd)
        pct = round((current / available_water_mm) * 100, 1) if available_water_mm else None
        return {
            "pojemnosc_calkowita_strefy_korzeniowej_mm": round(available_water_mm, 1),
            "procent_pojemnosci": pct,
            "info": "Wartość rośnie/maleje płynnie w ciągu dnia - czysto informacyjna, nie wpływa na decyzję o podlewaniu.",
        }


class ZoneProjectedDeficitSensor(CoordinatorEntity, SensorEntity):
    """Podgląd deficytu wody, rosnący płynnie w ciągu dnia (rozkład dobowej
    straty ETc na przyrosty co cykl aktualizacji) - CZYSTO INFORMACYJNY,
    nie wpływa na żadną decyzję o podlewaniu. Główny sensor deficytu
    (bez '_przewidywany') pozostaje jedynym źródłem prawdy dla decyzji."""

    _attr_icon = "mdi:water-percent-alert"
    _attr_native_unit_of_measurement = "mm"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry, zid: int, zone: dict) -> None:
        super().__init__(coordinator)
        self._zid = zid
        self._attr_unique_id = f"{entry.entry_id}_zone{zid}_smd_projected"
        self._attr_name = f"{zone['name']} - przewidywany deficyt wody"
        self._attr_suggested_object_id = f"garden_irrigation_{zone['slug']}_projected_soil_water_deficit"
        self.entity_id = f"sensor.{self._attr_suggested_object_id}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        zstate = self.coordinator.data["zones"].get(str(self._zid), {})
        smd = zstate.get("smd_projected")
        return round(smd, 1) if smd is not None else None

    @property
    def extra_state_attributes(self):
        return {
            "info": "Wartość rośnie w ciągu dnia do wglądu - nie wpływa na decyzję o podlewaniu",
        }


class ZoneProjectedWateringSensor(CoordinatorEntity, SensorEntity):
    """Podgląd zalecanego czasu podlewania - ZAWSZE czysta funkcja
    przewidywanego deficytu (ta sama zależność co w głównym sensorze:
    czas = potrzebna_ilość_mm / wydajność), bez wyjątków. Informacja o tym,
    co AKTUALNIE blokowałoby zatwierdzenie (deszcz/prognoza/wiatr/przymrozek/
    minimalny odstęp) jest osobnym atrybutem 'zablokowane_przez', odświeżanym
    raz na godzinę (nie co cykl) - wiatr i temperatura skaczą z minuty na
    minutę, więc częstsze sprawdzanie dawałoby migoczący wynik. Ważne: ten
    atrybut NIGDY nie zeruje ani nie zmienia samej liczby minut - to czysty
    kontekst do wglądu. Główny sensor zalecanego podlewania (z bramkami
    sprawdzanymi świeżo przy każdym zatwierdzeniu) pozostaje jedynym źródłem
    prawdy dla faktycznej decyzji."""

    _attr_icon = "mdi:water-sync"
    _attr_native_unit_of_measurement = "min"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry, zid: int, zone: dict) -> None:
        super().__init__(coordinator)
        self._zid = zid
        self._attr_unique_id = f"{entry.entry_id}_zone{zid}_pending_projected"
        self._attr_name = f"{zone['name']} - przewidywany czas podlewania"
        self._attr_suggested_object_id = f"garden_irrigation_{zone['slug']}_projected_watering_time"
        self.entity_id = f"sensor.{self._attr_suggested_object_id}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        zstate = self.coordinator.data["zones"].get(str(self._zid), {})
        return zstate.get("pending_min_projected", 0)

    @property
    def extra_state_attributes(self):
        zstate = self.coordinator.data["zones"].get(str(self._zid), {})
        blocked_by = zstate.get("projected_blocked_by")
        return {
            "przewidywana_ilosc_mm": zstate.get("pending_mm_projected"),
            "zablokowane_przez": blocked_by,
            "info": (
                "Liczba minut to zawsze czysta funkcja przewidywanego deficytu. "
                "'zablokowane_przez' pokazuje, co AKTUALNIE (sprawdzane co godzinę) "
                "wstrzymałoby zatwierdzenie - nie zmienia liczby minut powyżej."
            ),
        }


class ZoneParametersSensor(CoordinatorEntity, SensorEntity):
    """Pokazuje, jaka gleba i rośliny zostały wybrane dla strefy oraz KTÓRA
    konkretna roślina z listy była źródłem każdego przyjętego parametru
    (Kc, głębokość korzeni, próg MAD) - przydatne przy mieszanych nasadzeniach."""

    _attr_icon = "mdi:flower-outline"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry, zid: int, zone: dict) -> None:
        super().__init__(coordinator)
        self._zid = zid
        self._attr_unique_id = f"{entry.entry_id}_zone{zid}_parametry"
        self._attr_name = f"{zone['name']} - parametry gleby i roślin"
        self._attr_suggested_object_id = f"garden_irrigation_{zone['slug']}_soil_plant_parameters"
        self.entity_id = f"sensor.{self._attr_suggested_object_id}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        zone = self.coordinator.zones.get(self._zid, {})
        labels = zone.get("plant_labels") or []
        return ", ".join(labels) if labels else None

    @property
    def extra_state_attributes(self):
        zone = self.coordinator.zones.get(self._zid, {})
        return {
            "gleba": zone.get("soil_label"),
            "wybrane_rosliny": zone.get("plant_labels"),
            "rosliny_i_ich_parametry": zone.get("plants_detail"),
            "przyjete_kc": zone.get("kc"),
            "kc_przyjete_od": zone.get("kc_source_plant"),
            "przyjeta_glebokosc_korzeni_mm": zone.get("root_depth_mm"),
            "glebokosc_przyjeta_od_rosliny": zone.get("root_depth_source_plant"),
            "przyjety_prog_mad": zone.get("mad"),
            "mad_przyjety_od": zone.get("mad_source_plant"),
            "dostepna_woda_gleby_mm_na_m": zone.get("awc_mm_per_m"),
        }


class ZoneKcSensor(CoordinatorEntity, SensorEntity):
    """Przyjęty współczynnik roślinny (Kc) dla strefy - to on, razem z ET0,
    decyduje o tym, jak szybko rośnie deficyt wody w glebie (ETc = ET0 × Kc)."""

    _attr_icon = "mdi:sprout"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry, zid: int, zone: dict) -> None:
        super().__init__(coordinator)
        self._zid = zid
        self._attr_unique_id = f"{entry.entry_id}_zone{zid}_kc"
        self._attr_name = f"{zone['name']} - przyjęte Kc"
        self._attr_suggested_object_id = f"garden_irrigation_{zone['slug']}_kc_value"
        self.entity_id = f"sensor.{self._attr_suggested_object_id}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        zone = self.coordinator.zones.get(self._zid, {})
        return zone.get("kc")

    @property
    def extra_state_attributes(self):
        zone = self.coordinator.zones.get(self._zid, {})
        return {
            "przyjete_od": zone.get("kc_source_plant"),
            "rosliny_i_ich_kc": [
                {"roslina": p["label"], "kc": p["kc"]} for p in (zone.get("plants_detail") or [])
            ],
        }


class ZoneMadSensor(CoordinatorEntity, SensorEntity):
    """Przyjęty próg MAD (Management Allowed Depletion) dla strefy - jaka część
    dostępnej wody w strefie korzeniowej może zostać zużyta, zanim integracja
    uzna, że trzeba podlać. Niższa wartość = podlewanie częściej/wcześniej.

    Wartość to EFEKTYWNY próg używany dziś w obliczeniach - czyli bazowy MAD
    (z wybranych roślin albo ręcznej kalibracji) skorygowany wg oficjalnego
    wzoru FAO-56 na podstawie wczorajszego ETc: przy upale/suszy próg jest
    niższy (podlewanie wcześniej reaguje na stres), przy chłodnej pogodzie -
    wyższy. Bazowa wartość i szczegóły korekty są w atrybutach."""

    _attr_icon = "mdi:water-alert-outline"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry, zid: int, zone: dict) -> None:
        super().__init__(coordinator)
        self._zid = zid
        self._attr_unique_id = f"{entry.entry_id}_zone{zid}_mad"
        self._attr_name = f"{zone['name']} - przyjęty próg MAD"
        self._attr_suggested_object_id = f"garden_irrigation_{zone['slug']}_mad_threshold"
        self.entity_id = f"sensor.{self._attr_suggested_object_id}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        zone = self.coordinator.zones.get(self._zid, {})
        zstate = self.coordinator.data["zones"].get(str(self._zid), {})
        return zstate.get("mad_adjusted", zone.get("mad"))

    @property
    def extra_state_attributes(self):
        zone = self.coordinator.zones.get(self._zid, {})
        zstate = self.coordinator.data["zones"].get(str(self._zid), {})
        etc_yesterday = zstate.get("etc_yesterday_mm")
        base_mad = zone.get("mad")
        adjusted_mad = zstate.get("mad_adjusted", base_mad)
        dynamic_enabled = bool(self.coordinator.data.get("dynamic_mad_enabled", True))
        emergency_override = dynamic_enabled and (etc_yesterday or 0.0) > 5.0
        return {
            "przyjete_od": zone.get("mad_source_plant"),
            "rosliny_i_ich_mad": [
                {"roslina": p["label"], "mad": p["mad"]} for p in (zone.get("plants_detail") or [])
            ],
            "bazowy_mad": base_mad,
            "dynamiczna_korekta_wlaczona": dynamic_enabled,
            "korekta_fao56_etc_wczoraj_mm": etc_yesterday,
            "korekta_zastosowana": (
                round(adjusted_mad - base_mad, 3) if base_mad is not None else None
            ),
            "obejscie_minimalnego_odstepu_dzis": emergency_override,
            "info": (
                "Wartość to próg PO korekcie FAO-56 (p = p_bazowe + 0.04*(5-ETc), zakres 0.1-0.8), "
                "jeśli przełącznik 'Dynamiczna korekta MAD' jest włączony. Gdy wyłączony - to sam "
                "próg bazowy, bez korekty. Gdy ETc > 5 mm/dzień (i przełącznik włączony), minimalny "
                "odstęp między podlewaniami jest dziś pomijany."
            ),
        }


class ZoneMinDaysSensor(CoordinatorEntity, SensorEntity):
    """Skonfigurowany minimalny odstęp między podlewaniami tej strefy (dni) -
    dotąd niewidoczny jako osobna encja, tylko ukryty w konfiguracji. Pokazuje
    też ile dni faktycznie minęło od ostatniego podlania i czy dziś obowiązuje
    (może być pominięty przez korektę FAO-56 przy upale - patrz sensor MAD)."""

    _attr_icon = "mdi:calendar-clock"
    _attr_native_unit_of_measurement = "d"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry, zid: int, zone: dict) -> None:
        super().__init__(coordinator)
        self._zid = zid
        self._attr_unique_id = f"{entry.entry_id}_zone{zid}_min_days"
        self._attr_name = f"{zone['name']} - minimalny odstęp między podlewaniami"
        self._attr_suggested_object_id = f"garden_irrigation_{zone['slug']}_min_days_between_watering"
        self.entity_id = f"sensor.{self._attr_suggested_object_id}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        zone = self.coordinator.zones.get(self._zid, {})
        return zone.get("min_days_between_watering", 0)

    @property
    def extra_state_attributes(self):
        zone = self.coordinator.zones.get(self._zid, {})
        zstate = self.coordinator.data["zones"].get(str(self._zid), {})
        min_days = zone.get("min_days_between_watering", 0)
        last_watered_str = zstate.get("last_watered")
        days_since = None
        if last_watered_str:
            try:
                from datetime import date as _date
                days_since = (_date.today() - _date.fromisoformat(last_watered_str)).days
            except ValueError:
                pass
        etc_yesterday = zstate.get("etc_yesterday_mm")
        return {
            "ostatnie_podlewanie": last_watered_str,
            "dni_od_ostatniego_podlewania": days_since,
            "aktywny_dzisiaj": min_days > 0 and not ((etc_yesterday or 0.0) > 5.0),
            "info": (
                "0 = brak limitu. Gdy > 0, strefa nie zostanie podlana częściej niż co tyle dni, "
                "chyba że wczorajsze ETc przekroczyło 5 mm/dzień (patrz sensor przyjęty próg MAD)."
            ),
        }


class ZoneAreaSensor(CoordinatorEntity, SensorEntity):
    """Skonfigurowana powierzchnia strefy (m²) - dotąd niewidoczna jako
    osobna encja. Dla zraszaczy to cała powierzchnia; dla kroplówek -
    szacowana zwilżana strefa wzdłuż linii (patrz README)."""

    _attr_icon = "mdi:ruler-square"
    _attr_native_unit_of_measurement = "m²"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry, zid: int, zone: dict) -> None:
        super().__init__(coordinator)
        self._zid = zid
        self._attr_unique_id = f"{entry.entry_id}_zone{zid}_area"
        self._attr_name = f"{zone['name']} - powierzchnia strefy"
        self._attr_suggested_object_id = f"garden_irrigation_{zone['slug']}_area"
        self.entity_id = f"sensor.{self._attr_suggested_object_id}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        zone = self.coordinator.zones.get(self._zid, {})
        return zone.get("area_m2")

    @property
    def extra_state_attributes(self):
        zone = self.coordinator.zones.get(self._zid, {})
        return {
            "powierzchnia_skonfigurowana_m2": zone.get("area_m2_raw"),
            "typ_nawadniania": zone.get("irrigation_type"),
            "info": (
                "Dla linii kroplującej wartość główna to EFEKTYWNA powierzchnia wyliczona z "
                "długości linii (nie z pola 'powierzchnia strefy' - to pole jest wtedy ignorowane)."
            ),
        }


class ZoneRateSensor(CoordinatorEntity, SensorEntity):
    """Efektywna wydajność strefy (mm/h) używana w obliczeniach - jeśli
    integracja zdążyła się już nauczyć rzeczywistej wartości z pomiarów
    przepływomierza (samo-kalibracja po każdym podlaniu z realnym pomiarem),
    pokazuje wartość WYUCZONĄ zamiast ręcznie wpisanej. Szczegóły kalibracji
    (wartość ręczna, liczba próbek, ostatni pojedynczy pomiar) w atrybutach."""

    _attr_icon = "mdi:speedometer"
    _attr_native_unit_of_measurement = "mm/h"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry, zid: int, zone: dict) -> None:
        super().__init__(coordinator)
        self._zid = zid
        self._attr_unique_id = f"{entry.entry_id}_zone{zid}_rate"
        self._attr_name = f"{zone['name']} - wydajność"
        self._attr_suggested_object_id = f"garden_irrigation_{zone['slug']}_application_rate"
        self.entity_id = f"sensor.{self._attr_suggested_object_id}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        zone = self.coordinator.zones.get(self._zid, {})
        return self.coordinator._effective_rate_mmh(self._zid, zone)

    @property
    def extra_state_attributes(self):
        zone = self.coordinator.zones.get(self._zid, {})
        zstate = self.coordinator.data["zones"].get(str(self._zid), {})
        learned = zstate.get("learned_rate_mmh")
        learn_enabled = zone.get("learn_rate_from_flow", True)
        return {
            "typ_nawadniania": zone.get("irrigation_type"),
            "uczenie_z_wodomierza_wlaczone": learn_enabled,
            "wartosc_reczna_z_konfiguracji": zone.get("rate_mmh"),
            "wartosc_wyuczona": learned if learn_enabled else None,
            "liczba_probek_kalibracji": zstate.get("learned_rate_samples", 0) if learn_enabled else 0,
            "ostatni_pojedynczy_pomiar": zstate.get("last_measured_rate_mmh") if learn_enabled else None,
            "zrodlo": (
                "wyuczona (przepływomierz)" if (learned and learn_enabled)
                else "ręczna (konfiguracja)"
            ),
            "info": (
                "Po każdym podlaniu z realnym pomiarem z przepływomierza (co najmniej 1 minuta "
                "pracy) integracja aktualizuje tę wartość wykładniczą średnią z pomiarów - nowsze "
                "pomiary ważą więcej. Zastępuje ręcznie wpisaną wydajność we wszystkich obliczeniach "
                "czasu podlewania, dopóki zdąży się nauczyć (pierwszy pomiar = od razu używany). "
                "Wyłącz przełącznikiem 'Ucz się z wodomierza' w konfiguracji strefy, żeby zawsze "
                "używać wyłącznie ręcznie wpisanej wartości."
            ),
        }


class ZoneMaxRuntimeSensor(CoordinatorEntity, SensorEntity):
    """Skonfigurowany limit bezpieczeństwa (maksymalny czas podlewania tej
    strefy, min) - dotąd niewidoczny jako osobna encja. Pokazuje też, ile
    czasu POTRZEBA, żeby w pełni napełnić strefę korzeniową od zera (przy
    obecnej wydajności) - jeśli limit jest niższy niż to wyliczenie, integracja
    nigdy nie zdąży dolać pełnej dawki po dłuższej przerwie (urlop, seria
    pominiętych dni z powodu deszczu) i zgłasza to w HA Repairs."""

    _attr_icon = "mdi:timer-alert-outline"
    _attr_native_unit_of_measurement = "min"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry, zid: int, zone: dict) -> None:
        super().__init__(coordinator)
        self._zid = zid
        self._attr_unique_id = f"{entry.entry_id}_zone{zid}_max_runtime"
        self._attr_name = f"{zone['name']} - maksymalny czas podlewania"
        self._attr_suggested_object_id = f"garden_irrigation_{zone['slug']}_max_runtime"
        self.entity_id = f"sensor.{self._attr_suggested_object_id}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        zone = self.coordinator.zones.get(self._zid, {})
        return zone.get("max_runtime_min")

    @property
    def extra_state_attributes(self):
        zone = self.coordinator.zones.get(self._zid, {})
        available_water_mm = zone.get("awc_mm_per_m", 0) * (zone.get("root_depth_mm", 0) / 1000)
        rate = self.coordinator._effective_rate_mmh(self._zid, zone) or 0
        required_min = math.ceil((available_water_mm / rate) * 60) if rate else None
        configured = zone.get("max_runtime_min")
        too_short = required_min is not None and configured is not None and configured < required_min
        return {
            "wymagany_czas_pelnego_napelnienia_min": required_min,
            "za_niski_limit": too_short,
            "info": (
                "Wymagany czas = pełna pojemność wodna strefy korzeniowej / wydajność zraszaczy. "
                "Jeśli limit jest niższy, po dłuższej przerwie strefa nigdy nie dostanie pełnej dawki - "
                "sprawdź Ustawienia → System → Repairs, jeśli 'za_niski_limit' pokazuje True."
            ),
        }


class SequenceStartSensor(CoordinatorEntity, SensorEntity):
    """Przewidywana godzina rozpoczęcia najbliższej zaplanowanej sekwencji
    podlewania przed wschodem słońca (ustawiana po wywołaniu usługi
    run_sequence_before_sunrise / naciśnięciu odpowiedniego przycisku)."""

    _attr_icon = "mdi:clock-start"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_sequence_start"
        self._attr_name = "Przewidywana godzina rozpoczęcia sekwencji"
        self._attr_suggested_object_id = "garden_irrigation_sequence_start_time"
        self.entity_id = f"sensor.{self._attr_suggested_object_id}"
        self._attr_device_info = _device_info(entry)

    @property
    def _plan(self):
        return self.coordinator.data.get("sequence_plan")

    @property
    def native_value(self):
        plan = self._plan
        if not plan or plan.get("status") not in ("scheduled", "running") or not plan.get("start"):
            return None
        return dt_util.parse_datetime(plan["start"])

    @property
    def extra_state_attributes(self):
        plan = self._plan
        if not plan:
            return {"status": "brak_zaplanowanej_sekwencji"}
        return {
            "status": plan.get("status"),
            "planowany_wschod_slonca": plan.get("sunrise_target"),
            "laczny_czas_min": plan.get("total_minutes"),
            "kolejnosc_stref": plan.get("zones"),
            "obliczono_o": plan.get("computed_at"),
        }


class ZoneWaterTodaySensor(CoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:water"
    _attr_native_unit_of_measurement = "L"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry, zid: int, zone: dict) -> None:
        super().__init__(coordinator)
        self._zid = zid
        self._attr_unique_id = f"{entry.entry_id}_zone{zid}_water_today"
        self._attr_name = f"{zone['name']} - zużycie wody dziś"
        self._attr_suggested_object_id = f"garden_irrigation_{zone['slug']}_water_used_today"
        self.entity_id = f"sensor.{self._attr_suggested_object_id}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        zstate = self.coordinator.data["zones"].get(str(self._zid), {})
        return zstate.get("water_today_l", 0.0)


class ZoneWaterLastWateringSensor(CoordinatorEntity, SensorEntity):
    """Ile litrów zużyto podczas OSTATNIEGO pojedynczego podlewania tej
    strefy - w odróżnieniu od liczników dziś/miesiąc/rok, które sumują
    wiele podlań, ta wartość pokazuje tylko ostatnie, pojedyncze zdarzenie."""

    _attr_icon = "mdi:water-outline"
    _attr_native_unit_of_measurement = "L"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry, zid: int, zone: dict) -> None:
        super().__init__(coordinator)
        self._zid = zid
        self._attr_unique_id = f"{entry.entry_id}_zone{zid}_water_last"
        self._attr_name = f"{zone['name']} - zużycie wody podczas ostatniego podlewania"
        self._attr_suggested_object_id = f"garden_irrigation_{zone['slug']}_water_used_last"
        self.entity_id = f"sensor.{self._attr_suggested_object_id}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        zstate = self.coordinator.data["zones"].get(str(self._zid), {})
        return zstate.get("water_last_watering_l")

    @property
    def extra_state_attributes(self):
        zstate = self.coordinator.data["zones"].get(str(self._zid), {})
        return {"kiedy": zstate.get("last_watering_at")}


class ZoneWaterMonthSensor(CoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:water-check"
    _attr_native_unit_of_measurement = "L"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry, zid: int, zone: dict) -> None:
        super().__init__(coordinator)
        self._zid = zid
        self._attr_unique_id = f"{entry.entry_id}_zone{zid}_water_month"
        self._attr_name = f"{zone['name']} - zużycie wody w tym miesiącu"
        self._attr_suggested_object_id = f"garden_irrigation_{zone['slug']}_water_used_month"
        self.entity_id = f"sensor.{self._attr_suggested_object_id}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        zstate = self.coordinator.data["zones"].get(str(self._zid), {})
        return zstate.get("water_month_l", 0.0)


class TotalWaterTodaySensor(CoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:water"
    _attr_native_unit_of_measurement = "L"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_water_today_total"
        self._attr_name = "Łączne zużycie wody dziś"
        self._attr_suggested_object_id = "garden_irrigation_total_water_today"
        self.entity_id = f"sensor.{self._attr_suggested_object_id}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        return self.coordinator.data.get("water_today_total_l", 0.0)


class TotalWaterLastWateringSensor(CoordinatorEntity, SensorEntity):
    """Suma tego, co KAŻDA strefa zużyła podczas SWOJEGO WŁASNEGO ostatniego
    podlewania - NIE to samo co 'ostatnia sekwencja z jednego dnia'. Jeśli
    strefy podlewały się różnego dnia/o różnej porze, ta wartość i tak sumuje
    ich najnowsze pojedyncze zdarzenia, niezależnie od tego kiedy się
    odbyły - to prosta suma bieżących wartości sensorów
    '<strefa> - zużycie wody podczas ostatniego podlewania', liczona na żywo,
    nie osobno śledzony, kumulowany licznik jak Dziś/Miesiąc/Rok."""

    _attr_icon = "mdi:water-outline"
    _attr_native_unit_of_measurement = "L"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_water_last_watering_total"
        self._attr_name = "Łączne zużycie wody podczas ostatniego podlewania"
        self._attr_suggested_object_id = "garden_irrigation_total_water_last"
        self.entity_id = f"sensor.{self._attr_suggested_object_id}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        total = 0.0
        for zstate in self.coordinator.data["zones"].values():
            total += zstate.get("water_last_watering_l") or 0.0
        return round(total, 1)

    @property
    def extra_state_attributes(self):
        breakdown = {}
        for zid, zone in self.coordinator.zones.items():
            zstate = self.coordinator.data["zones"].get(str(zid), {})
            liters = zstate.get("water_last_watering_l")
            if liters is not None:
                breakdown[zone["name"]] = {"litry": liters, "kiedy": zstate.get("last_watering_at")}
        return {
            "rozbicie_per_strefa": breakdown,
            "info": "Suma ostatniego pojedynczego podlewania KAŻDEJ strefy z osobna - nie musi to być ten sam dzień dla wszystkich.",
        }


class TotalWaterMonthSensor(CoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:water-check"
    _attr_native_unit_of_measurement = "L"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_water_month_total"
        self._attr_name = "Łączne zużycie wody w tym miesiącu"
        self._attr_suggested_object_id = "garden_irrigation_total_water_month"
        self.entity_id = f"sensor.{self._attr_suggested_object_id}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        return self.coordinator.data.get("water_month_total_l", 0.0)


class ZoneWaterYearSensor(CoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:water-check"
    _attr_native_unit_of_measurement = "L"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry, zid: int, zone: dict) -> None:
        super().__init__(coordinator)
        self._zid = zid
        self._attr_unique_id = f"{entry.entry_id}_zone{zid}_water_year"
        self._attr_name = f"{zone['name']} - zużycie wody w tym roku"
        self._attr_suggested_object_id = f"garden_irrigation_{zone['slug']}_water_used_year"
        self.entity_id = f"sensor.{self._attr_suggested_object_id}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        zstate = self.coordinator.data["zones"].get(str(self._zid), {})
        return zstate.get("water_year_l", 0.0)


class TotalWaterYearSensor(CoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:water-check"
    _attr_native_unit_of_measurement = "L"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_water_year_total"
        self._attr_name = "Łączne zużycie wody w tym roku"
        self._attr_suggested_object_id = "garden_irrigation_total_water_year"
        self.entity_id = f"sensor.{self._attr_suggested_object_id}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        return self.coordinator.data.get("water_year_total_l", 0.0)
