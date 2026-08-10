"""Coordinator: liczy ET0 (FAO-56 Penman-Monteith), prowadzi bilans wodny
gleby dla każdej strefy i wystawia rekomendacje podlewania do zatwierdzenia."""
from __future__ import annotations

import asyncio
import logging
import math
from datetime import date, datetime, timedelta
from typing import Any

try:
    from astral import Observer
    from astral.sun import sun as astral_sun
    _ASTRAL_AVAILABLE = True
except ImportError:
    Observer = None
    astral_sun = None
    _ASTRAL_AVAILABLE = False

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AUTO_MODE_ENABLED,
    CONF_AUTO_TRIGGER_BUFFER_MIN,
    CONF_GARDEN_LOCATION,
    CONF_HUMIDITY_SENSOR,
    CONF_MAIN_FLOW_RATE_SENSOR,
    CONF_MAIN_FLOW_SENSOR,
    CONF_FLOW_RATE_ZERO_THRESHOLD,
    CONF_FROST_THRESHOLD_C,
    CONF_HEAT_ET0_THRESHOLD_MM,
    CONF_RAIN_PRIORITY_OVER_HEAT,
    CONF_DYNAMIC_MAD_ENABLED,
    CONF_PRESSURE_SENSOR,
    CONF_RAIN_SENSOR,
    CONF_RAIN_DETECTED_SENSOR,
    CONF_RAIN_FORECAST_SENSOR,
    CONF_RAIN_PAUSE_CHECK_INTERVAL_MIN,
    CONF_RAIN_PAUSE_MAX_WAIT_MIN,
    CONF_RAIN_STOP_CONFIRMATION_MIN,
    CONF_RAIN_PAUSE_THRESHOLD_MM,
    CONF_RAIN_RATE_THRESHOLD_MMH,
    CONF_RAIN_SKIP_THRESHOLD_MM,
    CONF_RAIN_FORECAST_LOOKBACK_MIN,
    CONF_SOLAR_SENSOR,
    CONF_START_MODE,
    CONF_START_OFFSET_MIN,
    CONF_TEMP_SENSOR,
    CONF_UPDATE_INTERVAL,
    CONF_VALVE_VERIFY_TIMEOUT_SEC,
    CONF_WEATHER_ENTITY,
    CONF_WEATHER_FORECAST_HOURS,
    CONF_WEATHER_FORECAST_INTERVAL_MIN,
    CONF_WIND_SENSOR,
    CONF_WIND_SKIP_THRESHOLD_MS,
    CONF_ZONE_COUNT,
    CONF_ZONE_TRANSITION_DELAY_SEC,
    DEFAULT_AUTO_TRIGGER_BUFFER_MIN,
    DEFAULT_FLOW_RATE_ZERO_THRESHOLD,
    DEFAULT_FROST_THRESHOLD_C,
    DEFAULT_HEAT_ET0_THRESHOLD_MM,
    DEFAULT_RAIN_PRIORITY_OVER_HEAT,
    DEFAULT_DYNAMIC_MAD_ENABLED,
    DEFAULT_PLANT,
    DEFAULT_RAIN_PAUSE_CHECK_INTERVAL_MIN,
    DEFAULT_RAIN_PAUSE_MAX_WAIT_MIN,
    DEFAULT_RAIN_STOP_CONFIRMATION_MIN,
    DEFAULT_RAIN_PAUSE_THRESHOLD_MM,
    DEFAULT_RAIN_RATE_THRESHOLD_MMH,
    DEFAULT_RAIN_SKIP_THRESHOLD_MM,
    DEFAULT_RAIN_FORECAST_LOOKBACK_MIN,
    DEFAULT_SOIL,
    DEFAULT_START_MODE,
    DEFAULT_START_OFFSET_MIN,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_VALVE_VERIFY_TIMEOUT_SEC,
    DEFAULT_WEATHER_FORECAST_HOURS,
    DEFAULT_WEATHER_FORECAST_INTERVAL_MIN,
    DEFAULT_WIND_SKIP_THRESHOLD_MS,
    DEFAULT_ZONE_COUNT,
    DEFAULT_ZONE_TRANSITION_DELAY_SEC,
    DOMAIN,
    PLANTS,
    SOIL_TYPES,
    START_MODE_AFTER_SUNRISE,
    START_MODE_AT_SUNRISE,
    START_MODE_BEFORE_SUNRISE,
    START_MODE_FINISH_AT_SUNRISE,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
    ZONE_FIELD_AREA,
    ZONE_FIELD_IRRIGATION_TYPE,
    ZONE_FIELD_DRIP_LINE_LENGTH_M,
    ZONE_FIELD_DRIP_SPACING_CM,
    ZONE_FIELD_DRIP_EMITTER_LPH,
    ZONE_FIELD_DRIP_COUNT,
    ZONE_FIELD_LEARN_RATE_FROM_FLOW,
    IRRIGATION_TYPE_DRIP_LINE,
    DRIP_LINE_WETTED_STRIP_WIDTH_M,
    DEFAULT_IRRIGATION_TYPE,
    DEFAULT_LEARN_RATE_FROM_FLOW,
    ZONE_FIELD_FLOW,
    ZONE_FIELD_FLOW_RATE,
    ZONE_FIELD_MAX_RUNTIME,
    ZONE_FIELD_NAME,
    ZONE_FIELD_PLANTS,
    ZONE_FIELD_RATE,
    ZONE_FIELD_SOIL,
    ZONE_FIELD_SWITCH,
    ZONE_FIELD_TIMER,
    ZONE_FIELD_ADJUST_RUNTIME_FROM_FLOW,
    DEFAULT_ADJUST_RUNTIME_FROM_FLOW,
    ZONE_FIELD_KC_OVERRIDE,
    ZONE_FIELD_MAD_OVERRIDE,
    ZONE_FIELD_ROOT_DEPTH_OVERRIDE_PLANT,
    ZONE_FIELD_MIN_DAYS_BETWEEN,
    ZONE_FIELD_WIND_SENSITIVE,
    ZONE_FIELD_FORCE_HEAT_ENABLED,
    ZONE_FIELD_FORCE_HEAT_DEFICIT_PCT,
    ZONE_FIELD_FORCE_HEAT_MIN_DAYS,
    DEFAULT_FORCE_HEAT_ENABLED,
    DEFAULT_FORCE_HEAT_DEFICIT_PCT,
    DEFAULT_FORCE_HEAT_MIN_DAYS,
    ZONE_STATUS_APPROVED,
    ZONE_STATUS_DISABLED,
    ZONE_STATUS_DONE,
    ZONE_STATUS_IDLE,
    ZONE_STATUS_PAUSED_RAIN,
    ZONE_STATUS_PENDING,
    ZONE_STATUS_RUNNING,
)

_LOGGER = logging.getLogger(__name__)


def _safe_float(hass: HomeAssistant, entity_id: str | None) -> float | None:
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None or state.state in ("unknown", "unavailable", ""):
        return None
    try:
        return float(state.state)
    except (ValueError, TypeError):
        return None


def _volume_to_liters(value: float, unit: str) -> float:
    """Przelicza odczyt przepływomierza na litry, niezależnie od jednostki
    (m³, gal, ft³, CCF, MCF) - większość liczników wody w HA (device_class
    'water') podaje objętość w m³, nie w litrach."""
    unit = (unit or "").strip().lower()
    if unit in ("l", "litre", "litres", "liter", "liters"):
        return value
    if unit in ("m³", "m3", "cubic meter", "cubic meters"):
        return value * 1000
    if unit in ("gal", "gallon", "gallons"):
        return value * 3.78541
    if unit in ("ft³", "ft3", "cubic feet", "cubic foot"):
        return value * 28.3168
    if unit in ("ccf",):  # 100 stóp sześciennych
        return value * 2831.68
    if unit in ("mcf",):  # 1000 stóp sześciennych
        return value * 28316.8
    # brak jednoznacznej jednostki - m³ jest najczęstsza dla liczników wody
    # w HA (device_class 'water'), więc to bezpieczniejsze założenie niż L
    _LOGGER.warning(
        "Przepływomierz ma nierozpoznaną jednostkę objętości '%s' - zakładam m³", unit
    )
    return value * 1000


def _flow_rate_to_lpm(value: float, unit: str) -> float:
    """Przelicza przepływ chwilowy na L/min, niezależnie od jednostki źródłowej
    (m³/h, m³/min, L/h, gal/min itd.) - integracja wewnętrznie liczy zawsze w L/min."""
    unit = (unit or "").strip().lower()
    if unit in ("l/min",):
        return value
    if unit in ("l/h", "l/hr"):
        return value / 60
    if unit in ("m³/h", "m3/h"):
        return value * 1000 / 60
    if unit in ("m³/min", "m3/min"):
        return value * 1000
    if unit in ("gal/min", "gpm"):
        return value * 3.78541
    # brak jednoznacznej jednostki - zwróć bez przeliczenia (lepsze niż nic),
    # ale zaloguj, żeby było wiadomo sprawdzić ręcznie
    _LOGGER.warning(
        "Przepływomierz chwilowy ma nierozpoznaną jednostkę '%s' - używam wartości bez przeliczenia", unit
    )
    return value


def _et0_penman_monteith(
    tmax: float, tmin: float, rad_mj_m2_day: float, wind_ms: float, rh_mean: float,
    elevation_m: float, latitude_deg: float, day_of_year: int, pressure_kpa: float | None = None,
) -> float:
    """Uproszczone FAO-56 Penman-Monteith, dobowy krok czasowy.
    Zwraca ET0 w mm/dzień. Jeśli danych brak/są nierealne, funkcja wywołująca
    powinna użyć metody zapasowej (Hargreaves)."""
    tmean = (tmax + tmin) / 2
    # nachylenie krzywej prężności pary (kPa/°C)
    delta = 4098 * (0.6108 * math.exp((17.27 * tmean) / (tmean + 237.3))) / ((tmean + 237.3) ** 2)
    # stała psychrometryczna - z REALNEGO pomiaru ciśnienia, jeśli dostępny,
    # w przeciwnym razie ze standardowego wzoru barometrycznego (FAO-56)
    pressure = pressure_kpa if pressure_kpa is not None else 101.3 * ((293 - 0.0065 * elevation_m) / 293) ** 5.26
    gamma = 0.000665 * pressure
    # prężność pary nasyconej i rzeczywistej
    es_tmax = 0.6108 * math.exp((17.27 * tmax) / (tmax + 237.3))
    es_tmin = 0.6108 * math.exp((17.27 * tmin) / (tmin + 237.3))
    es = (es_tmax + es_tmin) / 2
    ea = es * (rh_mean / 100)
    # promieniowanie netto - przybliżenie: Rns z albedo 0.23, Rnl uproszczone
    rns = (1 - 0.23) * rad_mj_m2_day
    # promieniowanie długofalowe netto, uproszczone (bez Rso, przybliżenie via rad_mj_m2_day)
    sigma = 4.903e-9
    tmax_k = tmax + 273.16
    tmin_k = tmin + 273.16
    rnl = sigma * ((tmax_k ** 4 + tmin_k ** 4) / 2) * (0.34 - 0.14 * math.sqrt(max(ea, 0))) * max(
        0.05, min(1.0, 1.35 * (rad_mj_m2_day / max(rad_mj_m2_day, 0.1)) - 0.35)
    )
    rn = rns - rnl
    g = 0  # strumień ciepła w glebę, pomijalny w kroku dobowym
    u2 = wind_ms  # zakładamy pomiar zbliżony do wysokości 2m; brak korekty wysokości anemometru

    numerator = 0.408 * delta * (rn - g) + gamma * (900 / (tmean + 273)) * u2 * (es - ea)
    denominator = delta + gamma * (1 + 0.34 * u2)
    et0 = numerator / denominator
    return max(0.0, round(et0, 2))


def _fao56_adjusted_mad(p_table: float, etc_mm_day: float) -> float:
    """Dynamiczna korekta MAD (p) wg oficjalnego wzoru FAO-56 (rozdział 8):
    p_adjusted = p_table + 0.04 * (5 - ETc), ograniczone do [0.1, 0.8].
    Sens fizyczny: przy wysokim ETc (upał, susza) próg jest NIŻSZY - roślina
    zaczyna cierpieć wcześniej, bo korzenie nie nadążają dostarczać wody przy
    tak dużym zapotrzebowaniu atmosfery, nawet zanim gleba wyschnie do
    'normalnego' poziomu. Przy niskim ETc próg jest WYŻSZY - można pozwolić
    glebie wyschnąć bardziej, zanim będzie to problem. ETc w mm/dzień."""
    p_adjusted = p_table + 0.04 * (5 - etc_mm_day)
    return max(0.1, min(0.8, p_adjusted))


def _et0_hargreaves(tmax: float, tmin: float, tmean: float, ra_mj_m2_day: float) -> float:
    """Metoda zapasowa, gdy brak pełnych danych (promieniowanie/wilgotność/wiatr)."""
    et0 = 0.0023 * (tmean + 17.8) * math.sqrt(max(0.0, tmax - tmin)) * ra_mj_m2_day
    return max(0.0, round(et0, 2))


def _extraterrestrial_radiation(latitude_deg: float, day_of_year: int) -> float:
    """Ra w MJ/m^2/dzień - potrzebne dla metody Hargreavesa."""
    lat_rad = math.radians(latitude_deg)
    dr = 1 + 0.033 * math.cos(2 * math.pi / 365 * day_of_year)
    decl = 0.409 * math.sin(2 * math.pi / 365 * day_of_year - 1.39)
    ws = math.acos(max(-1.0, min(1.0, -math.tan(lat_rad) * math.tan(decl))))
    ra = (
        (24 * 60 / math.pi)
        * 0.0820
        * dr
        * (ws * math.sin(lat_rad) * math.sin(decl) + math.cos(lat_rad) * math.cos(decl) * math.sin(ws))
    )
    return ra


class GardenIrrigationCoordinator(DataUpdateCoordinator):
    """Koordynator pobierający dane pogodowe, prowadzący bilans wodny gleby
    i wystawiający rekomendacje/statusy stref."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.hass = hass
        cfg = {**entry.data, **entry.options}
        self.cfg = cfg
        interval = cfg.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=interval),
        )
        self._store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}_{entry.entry_id}")
        self.zones: dict[int, dict[str, Any]] = self._build_zone_config()
        self._data: dict[str, Any] = {
            "date": dt_util.now().date().isoformat(),
            "daily": self._empty_daily(),
            "zones": {
                str(z): {
                    "smd": 0.0, "status": ZONE_STATUS_IDLE, "pending_mm": 0.0, "pending_min": 0,
                    "last_watered": None, "water_today_l": 0.0, "water_month_l": 0.0, "water_year_l": 0.0,
                    "smd_projected": 0.0, "etc_budget_mm": 0.0, "etc_accrued_mm": 0.0,
                    "pending_mm_projected": 0.0, "pending_min_projected": 0,
                    "mad_adjusted": self.zones[z]["mad"], "etc_yesterday_mm": None,
                    "learned_rate_mmh": None, "learned_rate_samples": 0, "last_measured_rate_mmh": None,
                }
                for z in self.zones
            },
            "et0_yesterday": None,
            "flow_start": {},
            "flow_start_time": {},
            "sequence_plan": None,
            "weather_forecast_cache_mm": None,
            "rain_measured_today_mm": 0.0,
            "weather_forecast_cache_at": None,
            "rain_forecast_samples": [],  # [{"at": iso, "mm": float}] - historia świeżych odczytów prognozy, do wyliczania maksimum z ostatniego okna (łapanie krótkotrwałych skoków)
            "irrigation_paused": False,
            "dynamic_mad_enabled": self.cfg.get(CONF_DYNAMIC_MAD_ENABLED, DEFAULT_DYNAMIC_MAD_ENABLED),
            "water_stats_month": dt_util.now().strftime("%Y-%m"),
            "water_stats_year": dt_util.now().strftime("%Y"),
            "water_today_total_l": 0.0,
            "water_month_total_l": 0.0,
            "water_year_total_l": 0.0,
        }
        self._unsub_listeners: list[Any] = []
        self._auto_trigger_unsub = None

    # ---------------------------------------------------------------- setup

    def _build_zone_config(self) -> dict[int, dict[str, Any]]:
        zones: dict[int, dict[str, Any]] = {}
        zone_count = int(self.cfg.get(CONF_ZONE_COUNT, DEFAULT_ZONE_COUNT))
        for i in range(1, zone_count + 1):
            prefix = f"zone{i}_"
            switch = self.cfg.get(prefix + ZONE_FIELD_SWITCH)
            if not switch:
                continue

            soil_key = self.cfg.get(prefix + ZONE_FIELD_SOIL, DEFAULT_SOIL)
            soil = SOIL_TYPES.get(soil_key, SOIL_TYPES[DEFAULT_SOIL])

            plant_keys = self.cfg.get(prefix + ZONE_FIELD_PLANTS) or [DEFAULT_PLANT]
            selected_plant_items = [(p, PLANTS[p]) for p in plant_keys if p in PLANTS] or [
                (DEFAULT_PLANT, PLANTS[DEFAULT_PLANT])
            ]
            # pełny rozkład WSZYSTKICH wybranych roślin i ich parametrów - widoczny
            # w sensorze diagnostycznym, żeby jasno było widać, z czego wybierane
            # jest Kc/głębokość/MAD, a nie tylko wynik końcowy
            plants_detail = [
                {
                    "key": key,
                    "label": plant["label"],
                    "kc": plant["kc"],
                    "root_depth_mm": plant["root_depth_mm"],
                    "mad": plant["mad"],
                }
                for key, plant in selected_plant_items
            ]

            # mieszane nasadzenia na jednej strefie - podejście konserwatywne:
            # Kc i głębokość korzeni bierzemy od najbardziej wymagającej rośliny (żeby
            # żadna nie usychała), próg MAD od najbardziej wrażliwej (najniższy MAD
            # = najwcześniej uruchamiamy podlewanie). Zapamiętujemy też KTÓRA roślina
            # z listy była źródłem każdego z tych parametrów - widać to potem w sensorze.
            kc_key, kc_plant = max(selected_plant_items, key=lambda kv: kv[1]["kc"])
            root_key, root_plant = max(selected_plant_items, key=lambda kv: kv[1]["root_depth_mm"])
            mad_key, mad_plant = min(selected_plant_items, key=lambda kv: kv[1]["mad"])
            kc = kc_plant["kc"]
            kc_source = kc_plant["label"]
            root_depth_mm = root_plant["root_depth_mm"]
            root_depth_source = root_plant["label"]
            root_depth_auto = True
            mad = mad_plant["mad"]
            mad_source = mad_plant["label"]

            # ręczny wybór głębokości korzeni z listy roślin już dodanych do
            # strefy - świadome zastąpienie automatycznego maksimum, gdy jedna
            # roślina (np. pojedyncze drzewo w miksie krzewów) zniekształcałaby
            # pojemność całej strefy dla reszty roślin. Działa TYLKO gdy wybrana
            # roślina nadal jest wśród aktualnie wybranych dla tej strefy.
            root_override_key = self.cfg.get(prefix + ZONE_FIELD_ROOT_DEPTH_OVERRIDE_PLANT)
            if root_override_key and root_override_key in PLANTS:
                override_plant = next(
                    (p for k, p in selected_plant_items if k == root_override_key), None
                )
                if override_plant is not None:
                    root_depth_mm = override_plant["root_depth_mm"]
                    root_depth_source = f"{override_plant['label']} (wybrana ręcznie)"
                    root_depth_auto = False

            # ręczna kalibracja - jeśli po obserwacji ogrodu chcesz skorygować Kc lub
            # próg MAD niezależnie od tego, co wynika z wybranych roślin, wpisana tu
            # wartość CAŁKOWICIE zastępuje wyliczoną (root_depth nadal z roślin)
            kc_override_raw = (self.cfg.get(prefix + ZONE_FIELD_KC_OVERRIDE) or "").strip()
            if kc_override_raw:
                try:
                    kc = float(kc_override_raw)
                    kc_source = "ręczna kalibracja"
                except ValueError:
                    _LOGGER.warning("Strefa %s: nieprawidłowa wartość kc_override '%s' - ignoruję", i, kc_override_raw)

            mad_override_raw = (self.cfg.get(prefix + ZONE_FIELD_MAD_OVERRIDE) or "").strip()
            if mad_override_raw:
                try:
                    mad = float(mad_override_raw)
                    mad_source = "ręczna kalibracja"
                except ValueError:
                    _LOGGER.warning("Strefa %s: nieprawidłowa wartość mad_override '%s' - ignoruję", i, mad_override_raw)

            zone_name = self.cfg.get(prefix + ZONE_FIELD_NAME) or f"Strefa {i}"
            raw_area_m2 = float(self.cfg.get(prefix + ZONE_FIELD_AREA, 10.0))
            irrigation_type = self.cfg.get(prefix + ZONE_FIELD_IRRIGATION_TYPE, DEFAULT_IRRIGATION_TYPE)
            if irrigation_type == IRRIGATION_TYPE_DRIP_LINE:
                drip_length = self.cfg.get(prefix + ZONE_FIELD_DRIP_LINE_LENGTH_M)
                if drip_length:
                    # linia prowadzona tuż obok roślin (uproszczenie) - efektywna
                    # powierzchnia liczona z samej długości linii, NIE z pola
                    # "powierzchnia strefy" (które dla tego typu jest ignorowane)
                    zone_effective_area_m2 = float(drip_length) * DRIP_LINE_WETTED_STRIP_WIDTH_M
                else:
                    zone_effective_area_m2 = raw_area_m2
            else:
                zone_effective_area_m2 = raw_area_m2

            zones[i] = {
                "name": zone_name,
                "slug": f"zone_{i:02d}",
                "switch": switch,
                "flow_sensor": self.cfg.get(prefix + ZONE_FIELD_FLOW) or self.cfg.get(CONF_MAIN_FLOW_SENSOR) or None,
                "flow_rate_sensor": self.cfg.get(prefix + ZONE_FIELD_FLOW_RATE) or self.cfg.get(CONF_MAIN_FLOW_RATE_SENSOR) or None,
                "soil_key": soil_key,
                "soil_label": soil["label"],
                "plant_keys": plant_keys,
                "plant_labels": [PLANTS[p]["label"] for p in plant_keys if p in PLANTS],
                "plants_detail": plants_detail,
                "kc": kc,
                "kc_source_plant": kc_source,
                "root_depth_mm": root_depth_mm,
                "root_depth_source_plant": root_depth_source,
                "root_depth_auto": root_depth_auto,
                "awc_mm_per_m": soil["awc_mm_per_m"],
                "mad": mad,
                "mad_source_plant": mad_source,
                "area_m2": zone_effective_area_m2,
                "area_m2_raw": raw_area_m2,
                "rate_mmh": float(self.cfg.get(prefix + ZONE_FIELD_RATE, 10.0)),
                "irrigation_type": irrigation_type,
                "drip_line_length_m": self.cfg.get(prefix + ZONE_FIELD_DRIP_LINE_LENGTH_M),
                "drip_spacing_cm": self.cfg.get(prefix + ZONE_FIELD_DRIP_SPACING_CM),
                "drip_emitter_lph": self.cfg.get(prefix + ZONE_FIELD_DRIP_EMITTER_LPH),
                "drip_count": self.cfg.get(prefix + ZONE_FIELD_DRIP_COUNT),
                "learn_rate_from_flow": bool(
                    self.cfg.get(prefix + ZONE_FIELD_LEARN_RATE_FROM_FLOW, DEFAULT_LEARN_RATE_FROM_FLOW)
                ),
                "max_runtime_min": int(self.cfg.get(prefix + ZONE_FIELD_MAX_RUNTIME, 30)),
                "timer_entity": self.cfg.get(prefix + ZONE_FIELD_TIMER) or None,
                "adjust_runtime_from_flow": bool(
                    self.cfg.get(prefix + ZONE_FIELD_ADJUST_RUNTIME_FROM_FLOW, DEFAULT_ADJUST_RUNTIME_FROM_FLOW)
                ),
                "min_days_between_watering": int(self.cfg.get(prefix + ZONE_FIELD_MIN_DAYS_BETWEEN, 0) or 0),
                "wind_sensitive": bool(self.cfg.get(prefix + ZONE_FIELD_WIND_SENSITIVE, False)),
                "force_heat_enabled": bool(
                    self.cfg.get(prefix + ZONE_FIELD_FORCE_HEAT_ENABLED, DEFAULT_FORCE_HEAT_ENABLED)
                ),
                "force_heat_deficit_pct": float(
                    self.cfg.get(prefix + ZONE_FIELD_FORCE_HEAT_DEFICIT_PCT, DEFAULT_FORCE_HEAT_DEFICIT_PCT)
                ),
                "force_heat_min_days": int(
                    self.cfg.get(prefix + ZONE_FIELD_FORCE_HEAT_MIN_DAYS, DEFAULT_FORCE_HEAT_MIN_DAYS)
                ),
            }
        return zones

    def _garden_latitude(self) -> float:
        """Szerokość geograficzna - z wybranej lokalizacji (mapa) jeśli podana,
        w przeciwnym razie wprost z ogólnej konfiguracji lokalizacji HA."""
        loc = self.cfg.get(CONF_GARDEN_LOCATION)
        if isinstance(loc, dict) and loc.get("latitude") is not None:
            try:
                return float(loc["latitude"])
            except (ValueError, TypeError):
                pass
        return self.hass.config.latitude or 52.0

    def _garden_longitude(self) -> float:
        """Długość geograficzna - z wybranej lokalizacji (mapa) jeśli podana,
        w przeciwnym razie wprost z ogólnej konfiguracji lokalizacji HA."""
        loc = self.cfg.get(CONF_GARDEN_LOCATION)
        if isinstance(loc, dict) and loc.get("longitude") is not None:
            try:
                return float(loc["longitude"])
            except (ValueError, TypeError):
                pass
        return self.hass.config.longitude or 21.0

    def _compute_sunrise(self, target_date: date) -> datetime | None:
        """Liczy wschód słońca dla lokalizacji/wysokości ogrodu na podany dzień,
        biblioteką astral (ta sama, na której opiera się wbudowana integracja
        Sun w HA) - bez potrzeby osobnej encji sensor.sun_next_rising."""
        if not _ASTRAL_AVAILABLE:
            _LOGGER.error(
                "Biblioteka astral jest niedostępna w tym środowisku - funkcje zależne od "
                "wschodu słońca (sekwencja, tryb automatyczny) nie będą działać. Reszta "
                "integracji (bilans wodny, ręczne podlewanie) działa normalnie."
            )
            return None
        lat = self._garden_latitude()
        lon = self._garden_longitude()
        elevation = self._garden_elevation()
        tz = dt_util.get_time_zone(self.hass.config.time_zone) or dt_util.UTC
        try:
            observer = Observer(latitude=lat, longitude=lon, elevation=elevation)
            events = astral_sun(observer, date=target_date, tzinfo=tz)
            return events["sunrise"]
        except Exception as err:  # noqa: BLE001 - np. dzień polarny/noc polarna przy skrajnych szerokościach
            _LOGGER.error(
                "Nie udało się wyliczyć wschodu słońca dla %s (lat=%s, lon=%s): %s",
                target_date, lat, lon, err,
            )
            return None

    def _next_sunrise(self) -> datetime | None:
        """Najbliższy nadchodzący wschód słońca - dziś, jeśli jeszcze nie minął,
        w przeciwnym razie jutro."""
        now = dt_util.now()
        today_sunrise = self._compute_sunrise(now.date())
        if today_sunrise and today_sunrise > now:
            return today_sunrise
        return self._compute_sunrise(now.date() + timedelta(days=1))

    def _garden_elevation(self) -> float:
        """Wysokość n.p.m. - wprost z ogólnej konfiguracji lokalizacji HA."""
        return self.hass.config.elevation or 100.0

    def weather_verification_data(self) -> dict[str, Any]:
        """Zbiera w jednym miejscu WSZYSTKIE dane pogodowe, na podstawie
        których integracja liczy zapotrzebowanie - zarówno migawkę z
        wczoraj (to, co faktycznie napędziło ET0), jak i żywy odczyt teraz
        (do porównania z tym, co pokazuje sama stacja pogodowa) oraz stan
        deszczu (prognoza i zmierzony licznik). Wyłącznie do wglądu/
        weryfikacji - nie wpływa na żadne obliczenia."""
        temp_now = _safe_float(self.hass, self.cfg.get(CONF_TEMP_SENSOR))
        solar_now = _safe_float(self.hass, self.cfg.get(CONF_SOLAR_SENSOR))
        rh_now = _safe_float(self.hass, self.cfg.get(CONF_HUMIDITY_SENSOR))
        wind_now = self._read_wind_speed_ms()
        rain_total_entity = self.cfg.get(CONF_RAIN_SENSOR)
        rain_total_now = _safe_float(self.hass, rain_total_entity)

        return {
            "teraz_temperatura_c": temp_now,
            "teraz_naslonecznienie_wm2": solar_now,
            "teraz_wilgotnosc_pct": rh_now,
            "teraz_wiatr_ms": round(wind_now, 2) if wind_now is not None else None,
            "wczoraj": self._data.get("et0_yesterday_inputs"),
            "prognoza_opadu_mm": self._data.get("weather_forecast_cache_mm"),
            "prognoza_opadu_pobrana_o": self._data.get("weather_forecast_cache_at"),
            "prognoza_max_w_oknie_mm": self._rain_forecast_rolling_max(),
            "prognoza_okno_min": int(
                self.cfg.get(CONF_RAIN_FORECAST_LOOKBACK_MIN, DEFAULT_RAIN_FORECAST_LOOKBACK_MIN)
            ),
            "opad_licznik_calkowity_mm": rain_total_now,
            "opad_licznik_encja": rain_total_entity,
            "opad_zmierzony_dzisiaj_mm": self._data.get("rain_measured_today_mm", 0.0),
            "prognoza_nocna": self._data.get("rain_forecast_nightly"),
            "prognoza_ostatnie_sprawdzenie": self._data.get("rain_forecast_last_check"),
            "wymuszenie_upal_prog_et0_mm": float(
                self.cfg.get(CONF_HEAT_ET0_THRESHOLD_MM, DEFAULT_HEAT_ET0_THRESHOLD_MM)
            ),
            "wymuszenie_upal_kandydaci": [
                self.zones[z]["name"] for z in (self._data.get("heat_candidates") or []) if z in self.zones
            ],
            "wymuszenie_upal_ostatnia_prognoza": self._data.get("heat_forecast_today"),
            "info": (
                "Dane 'teraz' to żywy odczyt skonfigurowanych czujników - jeśli któreś pole "
                "pokazuje None, integracja nie ma tego czujnika skonfigurowanego albo nie może "
                "go odczytać. Dane 'wczoraj' to dokładnie to, co napędziło ostatnie ET0 - jeśli "
                "'metoda' pokazuje Hargreaves zamiast Penman-Monteith, oznacza to, że któregoś "
                "dnia zabrakło nasłonecznienia/wiatru/wilgotności (sprawdź liczby próbek). "
                "'opad_zmierzony_dzisiaj_mm' to suma wszystkich przyrostów licznika total_rain "
                "od ostatniej północy, faktycznie odjęta od deficytu każdej strefy na bieżąco - "
                "resetuje się o północy, nie jest to surowy odczyt licznika. "
                "'prognoza_opadu_mm' to NAJŚWIEŻSZY, pojedynczy odczyt prognozy - natomiast "
                "'prognoza_max_w_oknie_mm' (okno: 'prognoza_okno_min' minut) to MAKSIMUM z całej "
                "ostatniej historii odczytów w tym oknie, i TO WŁAŚNIE ta wartość jest realnie "
                "porównywana z progiem przy decyzji o wstrzymaniu - dzięki temu krótkotrwały skok "
                "prognozy (np. nadciągająca komórka burzowa) nie zniknie z decyzji tylko dlatego, "
                "że sama prognoza zdążyła się cofnąć, zanim wypadło kolejne sprawdzenie."
            ),
        }

    def _garden_pressure_kpa(self) -> float | None:
        """Realny pomiar ciśnienia (kPa), jeśli skonfigurowano czujnik i jest
        dostępny - w przeciwnym razie None (funkcja ET0 wtedy sama wyliczy
        ciśnienie standardowe ze wzoru barometrycznego na podstawie wysokości)."""
        entity_id = self.cfg.get(CONF_PRESSURE_SENSOR)
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable", ""):
            return None
        try:
            value = float(state.state)
        except (ValueError, TypeError):
            return None
        unit = (state.attributes.get("unit_of_measurement") or "").lower()
        if unit in ("hpa", "mbar", "mb"):
            return value / 10
        if unit in ("kpa",):
            return value
        if unit in ("inhg",):
            return value * 3.38639
        if unit in ("mmhg", "torr"):
            return value * 0.133322
        if unit in ("pa",):
            return value / 1000
        # brak jednoznacznej jednostki - hPa jest zdecydowanie najczęstsza w HA
        # (stacje pogodowe, OpenWeatherMap), więc to bezpieczniejsze założenie
        # niż zwrócenie surowej liczby, która przy hPa dałaby ok. 10x za dużo
        _LOGGER.warning(
            "Czujnik ciśnienia %s ma nierozpoznaną jednostkę '%s' - zakładam hPa", entity_id, unit
        )
        return value / 10

    def _read_wind_speed_ms(self) -> float | None:
        """Odczytuje prędkość wiatru i przelicza na m/s niezależnie od jednostki
        czujnika (km/h, mph, węzły, m/s) - większość stacji pogodowych (w tym
        Ecowitt/WS) podaje wiatr w km/h, a wzór Penman-Monteith wymaga m/s."""
        entity_id = self.cfg.get(CONF_WIND_SENSOR)
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable", ""):
            return None
        try:
            value = float(state.state)
        except (ValueError, TypeError):
            return None
        unit = (state.attributes.get("unit_of_measurement") or "").lower()
        if unit in ("m/s", "ms"):
            return value
        if unit in ("km/h", "kph", "kmh"):
            return value / 3.6
        if unit in ("mph", "mi/h"):
            return value * 0.44704
        if unit in ("kn", "kt", "knots"):
            return value * 0.514444
        # brak jednoznacznej jednostki - km/h jest bardzo częsta w stacjach
        # pogodowych (Ecowitt/WS), więc to bezpieczniejsze założenie niż
        # potraktowanie wartości jako m/s (dałoby ~3,6x zawyżony wynik)
        _LOGGER.warning(
            "Czujnik wiatru %s ma nierozpoznaną jednostkę '%s' - zakładam km/h", entity_id, unit
        )
        return value / 3.6

    @staticmethod
    def _empty_daily() -> dict[str, Any]:
        return {
            "tmax": None,
            "tmin": None,
            "rad_sum_wm2": 0.0,
            "rad_count": 0,
            "wind_sum": 0.0,
            "wind_count": 0,
            "rh_sum": 0.0,
            "rh_count": 0,
        }

    async def async_setup(self) -> None:
        stored = await self._store.async_load()
        if stored:
            self._data.update(stored)
            if "daily" not in self._data or self._data["daily"] is None:
                self._data["daily"] = self._empty_daily()

        # samo-naprawa: uzupełnij pola sensorów przewidywanych, jeśli brakuje
        # ich w zapisanych danych (np. integracja zainstalowana przed tą
        # funkcją, ani razu nie przeszła jeszcze przez nocne przeliczenie)
        for zid_str, zstate in self._data["zones"].items():
            zstate.setdefault("smd_projected", zstate.get("smd", 0.0))
            zstate.setdefault("etc_budget_mm", 0.0)
            zstate.setdefault("etc_accrued_mm", 0.0)
            zstate.setdefault("pending_mm_projected", 0.0)
            zstate.setdefault("pending_min_projected", 0)
            zone = self.zones.get(int(zid_str))
            zstate.setdefault("mad_adjusted", zone["mad"] if zone else 0.5)
            zstate.setdefault("etc_yesterday_mm", None)
            zstate.setdefault("learned_rate_mmh", None)
            zstate.setdefault("learned_rate_samples", 0)
            zstate.setdefault("last_measured_rate_mmh", None)
        self._data.setdefault("flow_start_time", {})
        self._data.setdefault("et0_yesterday_inputs", None)
        self._data.setdefault("rain_measured_today_mm", 0.0)
        self._data.setdefault(
            "dynamic_mad_enabled", self.cfg.get(CONF_DYNAMIC_MAD_ENABLED, DEFAULT_DYNAMIC_MAD_ENABLED)
        )

        # sprawdź, czy skonfigurowane encje stref faktycznie istnieją - jeśli
        # nie, zgłoś to jako Repairs zamiast po cichu milczeć w logach.
        # WAŻNE: robimy to dopiero PO pełnym starcie HA, nie od razu przy
        # ładowaniu tej integracji - integracje w HA ładują się równolegle, w
        # nieprzewidywalnej kolejności, więc sprawdzenie "na gorąco" mogłoby
        # dać fałszywy alarm, gdyby np. integracja Tuya (dostarczająca zawory)
        # akurat jeszcze się nie zdążyła w pełni załadować.
        if self.hass.is_running:
            self._check_missing_entities()
        else:
            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED, self._on_hass_started
            )

    @callback
    def _on_hass_started(self, _event) -> None:
        """Wywoływane po pełnym starcie HA. Oznaczone @callback, żeby HA
        uruchamiało to bezpośrednio w pętli zdarzeń (event loop) - bez tego
        HA traktuje zwykłą, nieoznaczoną funkcję jako potencjalnie blokującą
        i wysyła ją do osobnego wątku roboczego, z którego wywołania
        issue_registry (async_create_issue/async_delete_issue) są niebezpieczne
        i mogą uszkodzić dane albo zawiesić HA (ostrzeżenie z homeassistant.helpers.frame)."""
        self._check_missing_entities()

    def _check_missing_entities(self) -> None:
        for zid, zone in self.zones.items():
            if self.hass.states.get(zone["switch"]) is None:
                self._create_issue(
                    f"missing_entity_zone_{zid}", "missing_zone_entity",
                    {"garden_irrigation_zone_name": zone["name"], "entity_id": zone["switch"]},
                )
            else:
                self._delete_issue(f"missing_entity_zone_{zid}")

        # temperatura jest jedynym naprawdę niezbędnym czujnikiem do liczenia
        # ET0 (nawet metoda zapasowa Hargreaves jej wymaga) - jeśli brak,
        # bilans wodny nigdy się nie ruszy, więc ostrzeż w Repairs zamiast
        # po cichu nic nie robić
        if not self.cfg.get(CONF_TEMP_SENSOR):
            self._create_issue("missing_temp_sensor", "missing_temp_sensor", {})
        else:
            self._delete_issue("missing_temp_sensor")

        # sprawdź, czy skonfigurowany limit bezpieczeństwa (max_runtime_min) w
        # ogóle mieści czas potrzebny na pełne napełnienie strefy korzeniowej
        # od zera - jeśli nie, integracja NIGDY nie zdąży dolać pełnej dawki
        # po dłuższej przerwie (urlop, seria pominiętych dni z powodu deszczu)
        for zid, zone in self.zones.items():
            rate = self._effective_rate_mmh(zid, zone) or 0
            if not rate:
                continue
            available_water_mm = zone["awc_mm_per_m"] * (zone["root_depth_mm"] / 1000)
            required_min = math.ceil((available_water_mm / rate) * 60)
            configured_min = zone.get("max_runtime_min", 0)
            if configured_min < required_min:
                self._create_issue(
                    f"runtime_too_short_zone_{zid}", "runtime_too_short",
                    {
                        "garden_irrigation_zone_name": zone["name"],
                        "configured_min": str(configured_min),
                        "required_min": str(required_min),
                    },
                )
            else:
                self._delete_issue(f"runtime_too_short_zone_{zid}")

        # nasłuchuj wyłączeń zaworów, żeby policzyć zużytą wodę z przepływomierza
        switches = [z["switch"] for z in self.zones.values()]
        if switches:
            self._unsub_listeners.append(
                async_track_state_change_event(self.hass, switches, self._on_switch_change)
            )
        async_track_time_interval(self.hass, self._async_persist, timedelta(minutes=5))

        # tryb automatyczny: bez żadnej zewnętrznej automatyzacji HA - integracja sama
        # planuje moment "obudzenia się" względem wschodu słońca (wyliczonego
        # samodzielnie z lokalizacji ogrodu, bez potrzeby osobnej encji).
        # Przeplanowywane też co noc przy przeliczeniu dnia (_roll_over_day).
        if self.cfg.get(CONF_AUTO_MODE_ENABLED, True):
            self._schedule_auto_trigger()

    async def _async_persist(self, _now=None) -> None:
        await self._store.async_save(self._data)

    # ------------------------------------------------------ tryb automatyczny

    def _target_start_bound(self, sunrise_dt: datetime, total_minutes: float, total_transition_min: float) -> datetime:
        """Punkt odniesienia 'kiedy startujemy' wg wybranego trybu. Dla trybu
        'zakończ o wschodzie' zależy od łącznego czasu (dlatego przyjmowany jako
        parametr - przy planowaniu wyzwalacza używamy GÓRNEGO szacunku z
        max_runtime, a przy faktycznym starcie dokładnych, bieżących minut)."""
        mode = self.cfg.get(CONF_START_MODE, DEFAULT_START_MODE)
        offset_min = int(self.cfg.get(CONF_START_OFFSET_MIN, DEFAULT_START_OFFSET_MIN))
        if mode == START_MODE_AT_SUNRISE:
            return sunrise_dt
        if mode == START_MODE_BEFORE_SUNRISE:
            return sunrise_dt - timedelta(minutes=offset_min)
        if mode == START_MODE_AFTER_SUNRISE:
            return sunrise_dt + timedelta(minutes=offset_min)
        # domyślnie: START_MODE_FINISH_AT_SUNRISE
        return sunrise_dt - timedelta(minutes=total_minutes + total_transition_min)

    def _schedule_auto_trigger(self) -> None:
        """Liczy moment 'obudzenia się' integracji względem wybranego trybu
        startu. Dla trybu 'zakończ o wschodzie' to celowo GÓRNY, bezpieczny
        szacunek (suma max_runtime_min wszystkich stref + bufor) - dokładny,
        faktyczny czas startu i tak jest przeliczany precyzyjnie w środku
        async_run_sequence_before_sunrise na podstawie rzeczywistych (zwykle
        dużo krótszych) rekomendacji. Dla pozostałych trybów punkt odniesienia
        jest znany dokładnie niezależnie od czasu podlewania."""
        if self._auto_trigger_unsub is not None:
            self._auto_trigger_unsub()
            self._auto_trigger_unsub = None

        sunrise_dt = self._next_sunrise()
        if sunrise_dt is None:
            _LOGGER.warning("Tryb automatyczny: nie udało się wyliczyć wschodu - nie zaplanowano wyzwalacza")
            return

        zone_count = len(self.zones)
        transition_delay_sec = int(
            self.cfg.get(CONF_ZONE_TRANSITION_DELAY_SEC, DEFAULT_ZONE_TRANSITION_DELAY_SEC)
        )
        total_transition_min = (zone_count - 1) * transition_delay_sec / 60 if zone_count > 1 else 0
        total_max_runtime = sum(z["max_runtime_min"] for z in self.zones.values())
        buffer_min = int(self.cfg.get(CONF_AUTO_TRIGGER_BUFFER_MIN, DEFAULT_AUTO_TRIGGER_BUFFER_MIN))

        target_bound = self._target_start_bound(sunrise_dt, total_max_runtime, total_transition_min)
        trigger_time = target_bound - timedelta(minutes=buffer_min)

        now = dt_util.now()
        if trigger_time <= now:
            today_str = now.date().isoformat()
            already_ran_today = self._data.get("last_auto_trigger_date") == today_str
            if not already_ran_today and now < sunrise_dt:
                # zaplanowany czas już minął (typowo: HA było wyłączone/w
                # trakcie restartu dokładnie w tym momencie) - ale dzisiejsza
                # sekwencja jeszcze się NIE odbyła i wschód jeszcze nie minął,
                # więc uruchamiamy z niewielkim opóźnieniem TERAZ, zamiast po
                # cichu czekać do jutra i tracić całodniowe podlewanie
                _LOGGER.warning(
                    "Tryb automatyczny: zaplanowany czas (%s) już minął, prawdopodobnie z powodu "
                    "restartu HA w tym oknie - uruchamiam sekwencję teraz, z opóźnieniem, zamiast "
                    "czekać do jutra",
                    trigger_time,
                )
                self._auto_trigger_unsub = async_track_point_in_time(
                    self.hass, self._async_auto_trigger_fired, now + timedelta(seconds=5)
                )
                return
            # wschód już minął ALBO sekwencja już dziś ruszyła - faktycznie
            # nic więcej nie da się/trzeba dziś zrobić, czekamy na jutro
            _LOGGER.debug(
                "Tryb automatyczny: wyliczony czas wyzwolenia (%s) już minął - czekam na kolejny wschód",
                trigger_time,
            )
            return

        _LOGGER.info(
            "Tryb automatyczny: zaplanowano samoczynne przeliczenie/start na %s (wschód %s, bufor %s min)",
            trigger_time, sunrise_dt, buffer_min,
        )
        self._auto_trigger_unsub = async_track_point_in_time(
            self.hass, self._async_auto_trigger_fired, trigger_time
        )

    async def _async_auto_trigger_fired(self, _now) -> None:
        self._auto_trigger_unsub = None
        self._data["last_auto_trigger_date"] = dt_util.now().date().isoformat()
        await self._async_persist()
        _LOGGER.info("Tryb automatyczny: wyzwolono - przeliczam i startuję sekwencję")
        await self.async_run_sequence_before_sunrise()

    # ------------------------------------------------------------- update

    async def _async_update_data(self) -> dict[str, Any]:
        today = dt_util.now().date()
        stored_date = date.fromisoformat(self._data["date"])
        if today != stored_date:
            await self._roll_over_day(stored_date, today)

        daily = self._data["daily"]
        temp = _safe_float(self.hass, self.cfg.get(CONF_TEMP_SENSOR))
        solar = _safe_float(self.hass, self.cfg.get(CONF_SOLAR_SENSOR))
        wind = self._read_wind_speed_ms()
        rh = _safe_float(self.hass, self.cfg.get(CONF_HUMIDITY_SENSOR))

        if temp is not None:
            daily["tmax"] = temp if daily["tmax"] is None else max(daily["tmax"], temp)
            daily["tmin"] = temp if daily["tmin"] is None else min(daily["tmin"], temp)
        if solar is not None:
            daily["rad_sum_wm2"] += solar
            daily["rad_count"] += 1
        if wind is not None:
            daily["wind_sum"] += wind
            daily["wind_count"] += 1
        if rh is not None:
            daily["rh_sum"] += rh
            daily["rh_count"] += 1

        self._async_apply_measured_rain()
        await self._async_sample_rain_forecast()
        self._async_accrue_projected_etc()
        await self._async_maybe_refresh_projected_gates()
        self._auto_trigger_safety_net()

        await self._async_persist()
        return self._data

    def _auto_trigger_safety_net(self) -> None:
        """Bezpiecznik trybu automatycznego, uruchamiany przy każdym cyklu
        głównej aktualizacji (co ok. 10 min, nie osobny, nowy timer). Chroni
        przed sytuacją, w której zaplanowany wewnętrzny timer
        (async_track_point_in_time) z jakiegokolwiek powodu NIE wystrzelił
        (nie tylko z powodu restartu HA w newralgicznym oknie - to już
        obsługuje _schedule_auto_trigger samo w sobie - ale też np.
        nieobsłużony wyjątek, chwilowe zawieszenie pętli zdarzeń itp.).

        Celowo NIE ma sztywno wpisanego zakresu godzin (np. '1:00-7:00') -
        zamiast tego po prostu ponownie wywołuje _schedule_auto_trigger(),
        która sama wie, jaki jest właściwy czas na podstawie RZECZYWISTEJ
        konfiguracji (tryb startu, wschód, bufor) i ma już wbudowaną logikę
        nadrabiania spóźnienia. Dzięki temu okno bezpieczeństwa automatycznie
        dostosowuje się do konfiguracji, pory roku itd., zamiast być
        sztywnym zgadywaniem z mojej strony."""
        if not self.cfg.get(CONF_AUTO_MODE_ENABLED, True):
            return
        if self._is_paused():
            return
        if self._auto_trigger_unsub is not None:
            # timer nadal żywy i zaplanowany - nic nie rób, on się tym zajmie
            return
        today_str = dt_util.now().date().isoformat()
        if self._data.get("last_auto_trigger_date") == today_str:
            # dzisiejsza sekwencja już ruszyła - nic do zrobienia
            return
        self._schedule_auto_trigger()

    async def _async_maybe_refresh_projected_gates(self) -> None:
        """Odświeża atrybut 'zablokowane_przez' na sensorach przewidywanego
        czasu podlewania - ale co godzinę, nie co cykl aktualizacji (10 min).
        Wiatr i temperatura naturalnie skaczą z minuty na minutę, więc
        sprawdzanie bramek tak często dawałoby migoczący wynik (0 min -> 15
        min -> 0 min w ciągu godziny). Sama liczba minut (pending_min_projected)
        NIE jest tu w ogóle dotykana - zostaje czystą funkcją deficytu,
        liczoną w _compute_projected_status. To wyłącznie dodatkowy kontekst."""
        checked_at_str = self._data.get("projected_gates_checked_at")
        if checked_at_str:
            checked_at = dt_util.parse_datetime(checked_at_str)
            if checked_at and (dt_util.utcnow() - checked_at) < timedelta(hours=1):
                return

        frost_risk, frost_temp = self._frost_risk()
        windy, wind_val = self._wind_risk()
        rain_skip, rain_val = await self._async_rain_expected_tracked("godzinne odświeżenie")

        for zid, zone in self.zones.items():
            zstate = self._data["zones"].get(str(zid))
            if not zstate:
                continue
            blockers = []
            if rain_skip:
                blockers.append(f"prognoza opadu {rain_val:.1f} mm ≥ próg")
            if frost_risk:
                blockers.append(f"ryzyko przymrozku ({frost_temp:.1f}°C)")
            if windy and zone.get("wind_sensitive"):
                blockers.append(f"silny wiatr ({wind_val:.1f} m/s)")
            min_days = zone.get("min_days_between_watering", 0)
            # obejście minimalnego odstępu: zgodnie z definicją FAO-56 "gorące,
            # suche warunki" to ETc > 5 mm/dzień (dokładnie tam, gdzie korekta
            # p staje się ujemna) - NIE skrajny dół wzoru (p<=0,1), który w
            # polskim klimacie praktycznie nigdy nie zostanie osiągnięty
            emergency_override = (
                self._data.get("dynamic_mad_enabled", True)
                and (zstate.get("etc_yesterday_mm") or 0.0) > 5.0
            )
            last_watered_str = zstate.get("last_watered")
            if min_days > 0 and last_watered_str and not emergency_override:
                try:
                    last_watered = date.fromisoformat(last_watered_str)
                    days_since = (dt_util.now().date() - last_watered).days
                    if days_since < min_days:
                        blockers.append(
                            f"minimalny odstęp {min_days} dni (ostatnio {days_since} dni temu)"
                        )
                except ValueError:
                    pass
            elif min_days > 0 and emergency_override:
                blockers.append(
                    "UWAGA: minimalny odstęp pominięty z powodu upału "
                    f"(ETc {zstate.get('etc_yesterday_mm')} mm/dzień > 5 mm/dzień, FAO-56)"
                )
            zstate["projected_blocked_by"] = blockers or None

        self._data["projected_gates_checked_at"] = dt_util.utcnow().isoformat()

    def _async_accrue_projected_etc(self) -> None:
        """Rozkłada dobowy 'budżet' ETc na małe przyrosty w każdym cyklu
        aktualizacji, wyłącznie dla pól '_projected' (podgląd). Uproszczenie:
        rozkład jest RÓWNOMIERNY w czasie (nie ważony rzeczywistym rytmem
        parowania, skoncentrowanym w dzień) - to kompromis prostoty. Główny,
        decyzyjny deficyt (smd/pending_min) pozostaje nietknięty."""
        update_interval_min = int(self.cfg.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL))
        ticks_per_day = max(1, round((24 * 60) / update_interval_min))
        for zid_str, zstate in self._data["zones"].items():
            budget = zstate.get("etc_budget_mm", 0.0)
            if budget <= 0:
                continue
            accrued = zstate.get("etc_accrued_mm", 0.0)
            if accrued >= budget:
                continue
            increment = min(budget / ticks_per_day, budget - accrued)
            zstate["smd_projected"] = zstate.get("smd_projected", 0.0) + increment
            zstate["etc_accrued_mm"] = accrued + increment
            self._compute_projected_status(int(zid_str))

    def _async_apply_measured_rain(self) -> float:
        """Sprawdza LICZNIK NARASTAJĄCY opadu (total rain, nigdy się nie zeruje) i
        jeśli od ostatniego sprawdzenia przybyło wody, natychmiast odejmuje ją z
        bilansu wodnego każdej strefy. Działa co cykl aktualizacji (nie tylko o
        północy), więc deszcz np. o 2:00 jest uwzględniony zanim ruszy podlewanie
        o 4:00 - nie trzeba czekać do kolejnego przeliczenia dnia.
        Zwraca zmierzony przyrost (mm) - używane też do wykrywania deszczu W
        TRAKCIE podlewania (patrz _async_run_zone_monitored)."""
        current = _safe_float(self.hass, self.cfg.get(CONF_RAIN_SENSOR))
        if current is None:
            return 0.0
        last = self._data.get("last_rain_total")
        if last is None:
            # pierwsze uruchomienie - zapamiętaj punkt startowy, nic jeszcze nie odejmuj
            self._data["last_rain_total"] = current
            return 0.0
        diff = current - last
        if diff < 0:
            # licznik zresetowany (restart urządzenia / integracji pogodowej) - nie
            # traktuj tego jako ujemny opad, po prostu zacznij liczyć od nowa
            _LOGGER.info(
                "Licznik opadu (%s) się zmniejszył (%.1f -> %.1f) - traktuję jako reset licznika",
                self.cfg.get(CONF_RAIN_SENSOR), last, current,
            )
            self._data["last_rain_total"] = current
            return 0.0
        if diff == 0:
            return 0.0

        for zid_str, zstate in self._data["zones"].items():
            zstate["smd"] = max(0.0, zstate.get("smd", 0.0) - diff)
            zstate["smd_projected"] = max(0.0, zstate.get("smd_projected", 0.0) - diff)
        self._data["last_rain_total"] = current
        self._data["rain_measured_today_mm"] = round(self._data.get("rain_measured_today_mm", 0.0) + diff, 2)
        _LOGGER.info("Zmierzony opad +%.1f mm - odjęto z bilansu wodnego wszystkich stref", diff)
        return diff

    async def _roll_over_day(self, prev_date: date, today: date) -> None:
        """O północy: policz ET0 za wczorajszy dzień, zaktualizuj bilans wodny
        każdej strefy i wystaw rekomendacje na dziś."""
        daily = self._data["daily"]
        lat = self._garden_latitude()
        elevation = self._garden_elevation()
        pressure_kpa = self._garden_pressure_kpa()
        day_of_year = prev_date.timetuple().tm_yday

        et0 = None
        et0_inputs = {
            "data": prev_date.isoformat(),
            "metoda": "brak_danych",
            "tmax_c": daily["tmax"],
            "tmin_c": daily["tmin"],
            "tmean_c": None,
            "naslonecznienie_srednie_wm2": None,
            "wiatr_sredni_ms": None,
            "wilgotnosc_srednia_pct": None,
            "liczba_probek_naslonecznienia": daily["rad_count"],
            "liczba_probek_wiatru": daily["wind_count"],
            "liczba_probek_wilgotnosci": daily["rh_count"],
        }
        if daily["tmax"] is not None and daily["tmin"] is not None:
            tmean = (daily["tmax"] + daily["tmin"]) / 2
            et0_inputs["tmean_c"] = round(tmean, 1)
            if daily["rad_count"] > 0 and daily["wind_count"] > 0 and daily["rh_count"] > 0:
                rad_avg_wm2 = daily["rad_sum_wm2"] / daily["rad_count"]
                # W/m^2 (średnia) -> MJ/m^2/dzień: * 0.0864
                rad_mj = rad_avg_wm2 * 0.0864
                wind_avg = daily["wind_sum"] / daily["wind_count"]
                rh_avg = daily["rh_sum"] / daily["rh_count"]
                et0 = _et0_penman_monteith(
                    daily["tmax"], daily["tmin"], rad_mj, wind_avg, rh_avg, elevation, lat,
                    day_of_year, pressure_kpa,
                )
                et0_inputs["metoda"] = "penman_monteith"
                et0_inputs["naslonecznienie_srednie_wm2"] = round(rad_avg_wm2, 1)
                et0_inputs["wiatr_sredni_ms"] = round(wind_avg, 2)
                et0_inputs["wilgotnosc_srednia_pct"] = round(rh_avg, 1)
            else:
                ra = _extraterrestrial_radiation(lat, day_of_year)
                et0 = _et0_hargreaves(daily["tmax"], daily["tmin"], tmean, ra)
                et0_inputs["metoda"] = "hargreaves (zapasowa - brak nasłonecznienia/wiatru/wilgotności)"

        self._data["et0_yesterday"] = et0
        self._data["et0_yesterday_inputs"] = et0_inputs

        for zid, zone in self.zones.items():
            zstate = self._data["zones"].setdefault(
                str(zid), {"smd": 0.0, "status": ZONE_STATUS_IDLE, "pending_mm": 0.0, "pending_min": 0}
            )
            etc = et0 * zone["kc"] if et0 is not None else None
            if etc is not None:
                zstate["smd"] = max(0.0, zstate["smd"] + etc)
                zstate["etc_yesterday_mm"] = round(etc, 2)
                # dynamiczna korekta MAD wg FAO-56 - próg podlewania reaguje
                # na wczorajsze tempo zużycia wody, nie tylko na sam deficyt.
                # Wyłączalna przełącznikiem "Dynamiczna korekta MAD (FAO-56)".
                if self._data.get("dynamic_mad_enabled", True):
                    zstate["mad_adjusted"] = _fao56_adjusted_mad(zone["mad"], etc)
                else:
                    zstate["mad_adjusted"] = zone["mad"]
            self._compute_zone_status(zid)

            # osobna, czysto informacyjna projekcja - startuje każdego dnia od
            # tego samego punktu co główny (autorytatywny) deficyt, ale w ciągu
            # dnia rośnie płynnie (patrz _async_accrue_projected_etc), zamiast
            # czekać do kolejnej północy. NIE wpływa na żadną decyzję o
            # podlewaniu - to wyłącznie podgląd.
            etc_today_budget = etc if etc is not None else 0.0
            zstate["smd_projected"] = zstate["smd"]
            zstate["etc_budget_mm"] = etc_today_budget
            zstate["etc_accrued_mm"] = 0.0
            self._compute_projected_status(zid)

        # kwalifikacja kandydatów do wymuszonego podlewania przed upałem
        # (ETAP A - patrz docstring _prepare_heat_candidates) - musi zajść
        # PRZED globalnymi bramkami deszcz/przymrozek poniżej, bo to od niej
        # zależy pełny, potencjalny skład dzisiejszej kolejki
        self._prepare_heat_candidates(today)

        # globalne bramki - jeśli zapowiada się deszcz/przymrozek, oznacz wszystkie
        # oczekujące strefy jako wstrzymane (bez zerowania deficytu - dogonimy jutro)
        await self._apply_rain_forecast_hold()
        self._apply_frost_hold()

        self._data["daily"] = self._empty_daily()
        self._data["date"] = today.isoformat()
        self._data["water_today_total_l"] = 0.0
        self._data["rain_measured_today_mm"] = 0.0
        for zstate in self._data["zones"].values():
            zstate["water_today_l"] = 0.0
            zstate["forced_heat_watering"] = False
        self._maybe_roll_water_stats_month()
        self._maybe_roll_water_stats_year()
        await self._async_persist()

        # przeplanuj wyzwalacz trybu automatycznego na dzisiejszy wschód
        if self.cfg.get(CONF_AUTO_MODE_ENABLED, True):
            self._schedule_auto_trigger()

    async def _async_rain_forecast_mm(self) -> float | None:
        """Zwraca prognozowany opad w mm. Jeśli skonfigurowano encję weather.*,
        pyta ją o prognozę godzinową (przez usługę weather.get_forecasts) i
        sumuje opad w najbliższych `weather_forecast_hours` godzinach - ale
        NIE częściej niż raz na `weather_forecast_interval_min` (niezależnie od
        częstotliwości odpytywania pozostałych czujników - część usług pogodowych
        ma limity zapytań). W międzyczasie zwraca ostatnią zapamiętaną wartość.
        Jeśli encja weather.* nie jest skonfigurowana, korzysta ze starego
        sposobu - zwykłej encji sensor (np. własnego szablonu)."""
        weather_entity = self.cfg.get(CONF_WEATHER_ENTITY)
        if not weather_entity:
            return _safe_float(self.hass, self.cfg.get(CONF_RAIN_FORECAST_SENSOR))

        interval_min = int(
            self.cfg.get(CONF_WEATHER_FORECAST_INTERVAL_MIN, DEFAULT_WEATHER_FORECAST_INTERVAL_MIN)
        )
        cached_at_str = self._data.get("weather_forecast_cache_at")
        if cached_at_str:
            cached_at = dt_util.parse_datetime(cached_at_str)
            if cached_at and (dt_util.utcnow() - cached_at) < timedelta(minutes=interval_min):
                return self._data.get("weather_forecast_cache_mm")

        try:
            result = await self.hass.services.async_call(
                "weather", "get_forecasts",
                {"type": "hourly"},
                target={"entity_id": weather_entity},
                blocking=True, return_response=True,
            )
            entries = ((result or {}).get(weather_entity) or {}).get("forecast", [])
            horizon_hours = int(self.cfg.get(CONF_WEATHER_FORECAST_HOURS, DEFAULT_WEATHER_FORECAST_HOURS))
            now = dt_util.utcnow()
            horizon_end = now + timedelta(hours=horizon_hours)
            total = 0.0
            for item in entries:
                dt_str = item.get("datetime")
                item_dt = dt_util.parse_datetime(dt_str) if dt_str else None
                if item_dt is None:
                    continue
                if item_dt.tzinfo is None:
                    item_dt = dt_util.as_utc(item_dt)
                if now <= item_dt <= horizon_end:
                    precip = item.get("precipitation")
                    if precip is not None:
                        total += float(precip)
            self._data["weather_forecast_cache_mm"] = round(total, 2)
            self._data["weather_forecast_cache_at"] = now.isoformat()
            await self._async_persist()
            _LOGGER.info(
                "Pobrano prognozę z %s: %.1f mm w najbliższych %s h", weather_entity, total, horizon_hours
            )
            return total
        except Exception as err:  # noqa: BLE001 - integracja pogodowa może się różnić / chwilowo nie odpowiadać
            _LOGGER.warning(
                "Nie udało się pobrać prognozy z %s (%s) - używam ostatniej zapamiętanej wartości",
                weather_entity, err,
            )
            return self._data.get("weather_forecast_cache_mm")

    async def _async_sample_rain_forecast(self) -> None:
        """Odczytuje AKTUALNĄ prognozę opadu i dopisuje ją do krótkiej historii
        próbek (niezależnie od tego, czy akurat trwa jakieś 'oficjalne'
        sprawdzenie typu 'noc' czy 'przed sekwencją'). Wywoływane przy KAŻDYM
        cyklu głównej aktualizacji koordynatora (domyślnie co ok. 10 min).

        Po co: prognoza krótkoterminowa (nowcasting) potrafi skoczyć z 2mm do
        40mm i z powrotem w ciągu pół godziny (np. przechodząca komórka
        burzowa). Jeśli sprawdzamy próg tylko w kilku ustalonych momentach
        (noc, tuż przed sekwencją), taki krótkotrwały skok może zdążyć
        całkowicie zniknąć z prognozy, zanim którykolwiek z tych momentów
        nastąpi - i podlewanie wystartuje tak, jakby nic się nie działo.
        Dzięki tej historii bierzemy pod uwagę MAKSIMUM z ostatnich
        `rain_forecast_lookback_min` minut, a nie tylko pojedynczy, najświeższy
        odczyt."""
        forecast = await self._async_rain_forecast_mm()
        if forecast is None:
            return
        samples: list[dict] = self._data.setdefault("rain_forecast_samples", [])
        samples.append({"at": dt_util.utcnow().isoformat(), "mm": forecast})
        lookback_min = int(
            self.cfg.get(CONF_RAIN_FORECAST_LOOKBACK_MIN, DEFAULT_RAIN_FORECAST_LOOKBACK_MIN)
        )
        cutoff = dt_util.utcnow() - timedelta(minutes=lookback_min)
        kept = []
        for sample in samples:
            sample_at = dt_util.parse_datetime(sample.get("at", ""))
            if sample_at and sample_at >= cutoff:
                kept.append(sample)
        self._data["rain_forecast_samples"] = kept

    def _rain_forecast_rolling_max(self) -> float | None:
        """Maksymalna wartość prognozy opadu spośród próbek zapamiętanych w
        ostatnim oknie (patrz _async_sample_rain_forecast). Zwraca None, jeśli
        nie mamy jeszcze żadnej próbki (np. tuż po starcie integracji)."""
        samples = self._data.get("rain_forecast_samples") or []
        values = [s["mm"] for s in samples if s.get("mm") is not None]
        if not values:
            return None
        return max(values)

    async def _async_rain_expected(self) -> tuple[bool, float | None]:
        """Zwraca (czy_pomijac, wartosc_prognozy_mm) na podstawie MAKSIMUM
        prognozy z ostatniego okna czasowego (nie tylko pojedynczego,
        najświeższego odczytu - patrz _rain_forecast_rolling_max) i
        skonfigurowanego progu."""
        live_forecast = await self._async_rain_forecast_mm()
        # upewnij się, że bieżący odczyt też jest już w historii, nawet jeśli
        # akurat trafiamy pomiędzy cyklicznymi próbkowaniami (np. ktoś ręcznie
        # zatwierdza strefę tuż po starcie integracji)
        if live_forecast is not None:
            samples: list[dict] = self._data.setdefault("rain_forecast_samples", [])
            samples.append({"at": dt_util.utcnow().isoformat(), "mm": live_forecast})
        rolling_max = self._rain_forecast_rolling_max()
        threshold = float(self.cfg.get(CONF_RAIN_SKIP_THRESHOLD_MM, DEFAULT_RAIN_SKIP_THRESHOLD_MM))
        if rolling_max is None:
            return False, live_forecast
        return rolling_max >= threshold, rolling_max

    async def _async_rain_expected_tracked(self, source: str) -> tuple[bool, float | None]:
        """To samo co _async_rain_expected(), ale dodatkowo zapisuje TRWAŁY
        ślad tego konkretnego sprawdzenia - widoczny w
        sensor.garden_irrigation_weather_inputs, atrybut
        'prognoza_ostatnie_sprawdzenie'. Nadpisywany przy KAŻDYM kolejnym
        sprawdzeniu (z dowolnego źródła) - to wyłącznie diagnostyka, nie
        wpływa na samą decyzję. Sprawdzenie ze źródła 'noc' zapisywane jest
        DODATKOWO osobno (atrybut 'prognoza_nocna'), żeby zawsze było widać,
        jaka była decyzja z nocnego przeliczenia, niezależnie od tego, co
        działo się później w ciągu dnia."""
        skip, forecast = await self._async_rain_expected()
        threshold = float(self.cfg.get(CONF_RAIN_SKIP_THRESHOLD_MM, DEFAULT_RAIN_SKIP_THRESHOLD_MM))
        now = dt_util.now()
        self._data["rain_forecast_last_check"] = {
            "zrodlo": source,
            "kiedy": now.isoformat(),
            "prognoza_mm": forecast,
            "prog_mm": threshold,
            "wstrzymano": skip,
        }
        if source == "noc":
            self._data["rain_forecast_nightly"] = {
                "data": now.date().isoformat(),
                "prognoza_mm": forecast,
                "prog_mm": threshold,
                "wstrzymano": skip,
            }
        return skip, forecast

    @staticmethod
    def _forecast_wind_to_ms(value: float, unit: str | None) -> float:
        """Jak _read_wind_speed_ms, ale dla wartości z prognozy (nie z encji
        czujnika) - te same jednostki mogą się pojawić, więc ta sama logika
        konwersji."""
        unit_l = (unit or "").lower()
        if unit_l in ("m/s", "ms"):
            return value
        if unit_l in ("mph", "mi/h"):
            return value * 0.44704
        if unit_l in ("kn", "kt", "knots"):
            return value * 0.514444
        # km/h (albo jednostka nieznana - to najczęstszy przypadek u dostawców
        # prognoz, w tym OpenWeatherMap w polskiej lokalizacji)
        return value / 3.6

    async def _async_forecast_et0_today(self) -> dict[str, Any] | None:
        """Liczy prognozowane ET0 na DZISIAJ (dzień kalendarzowy lokalny) z
        prognozy GODZINOWEJ (nie dobowej - patrz uzasadnienie w README:
        pole 'temperature'/'humidity' itp. w prognozie dobowej bywa
        pojedynczym zrzutem z jednej, niekoniecznie reprezentatywnej godziny,
        a nie prawdziwą średnią dobową; Tmax/Tmin z obu źródeł są za to
        zgodne). Zwraca słownik z ET0 i danymi wejściowymi (do diagnostyki),
        albo None, jeśli dane są niedostępne/niepełne - w takim wypadku
        wywołujący MA założyć 'nie ma upału' (bezpieczny wariant domyślny),
        nie próbować zgadywać.

        Nasłonecznienie nie jest dostępne wprost w prognozie - szacowane z
        zachmurzenia (cloud_coverage) względem promieniowania w warunkach
        bezchmurnego nieba (Rso), tym samym uproszczonym wzorem, którego
        użyto przy weryfikacji tej metody na rzeczywistych danych."""
        weather_entity = self.cfg.get(CONF_WEATHER_ENTITY)
        if not weather_entity:
            return None
        try:
            result = await self.hass.services.async_call(
                "weather", "get_forecasts",
                {"type": "hourly"},
                target={"entity_id": weather_entity},
                blocking=True, return_response=True,
            )
        except Exception as err:  # noqa: BLE001 - usługa pogodowa może chwilowo nie odpowiadać
            _LOGGER.warning(
                "Nie udało się pobrać prognozy godzinowej z %s do wyliczenia ET0 (%s)",
                weather_entity, err,
            )
            return None
        entries = ((result or {}).get(weather_entity) or {}).get("forecast", [])
        if not entries:
            return None

        weather_state = self.hass.states.get(weather_entity)
        wind_unit = weather_state.attributes.get("wind_speed_unit") if weather_state else None

        today_local = dt_util.now().date()
        temps: list[float] = []
        humidities: list[float] = []
        winds_ms: list[float] = []
        clouds: list[float] = []
        for item in entries:
            dt_str = item.get("datetime")
            item_dt = dt_util.parse_datetime(dt_str) if dt_str else None
            if item_dt is None:
                continue
            if item_dt.tzinfo is None:
                item_dt = dt_util.as_utc(item_dt)
            if dt_util.as_local(item_dt).date() != today_local:
                continue
            temp = item.get("temperature")
            if temp is not None:
                temps.append(float(temp))
            if item.get("humidity") is not None:
                humidities.append(float(item["humidity"]))
            if item.get("wind_speed") is not None:
                winds_ms.append(self._forecast_wind_to_ms(float(item["wind_speed"]), wind_unit))
            if item.get("cloud_coverage") is not None:
                clouds.append(float(item["cloud_coverage"]))

        # za mało próbek dla dzisiejszej daty lokalnej (np. odpytanie tuż po
        # północy, zanim prognoza "dojrzeje") - lepiej nic nie zwrócić niż
        # policzyć ET0 z 1-2 godzin i potraktować to jako miarodajne
        if len(temps) < 6:
            return None

        tmax = max(temps)
        tmin = min(temps)
        humidity_mean = sum(humidities) / len(humidities) if humidities else 50.0
        # wiatr z prognozy zwykle podawany dla standardowej wysokości 10m
        # (WMO) - korekta logarytmiczna do 2m, tak jak wymaga FAO-56
        wind_mean_10m = sum(winds_ms) / len(winds_ms) if winds_ms else 2.0
        wind_2m = wind_mean_10m * 4.87 / math.log(67.8 * 10 - 5.42)
        cloud_mean_pct = sum(clouds) / len(clouds) if clouds else 50.0

        lat = self._garden_latitude()
        elevation = self._garden_elevation()
        pressure_kpa = self._garden_pressure_kpa()
        day_of_year = today_local.timetuple().tm_yday
        ra = _extraterrestrial_radiation(lat, day_of_year)
        rso = (0.75 + 2e-5 * elevation) * ra
        rs = rso * (1 - 0.75 * (cloud_mean_pct / 100))

        et0 = _et0_penman_monteith(
            tmax, tmin, rs, wind_2m, humidity_mean, elevation, lat, day_of_year, pressure_kpa,
        )
        return {
            "et0_mm": et0,
            "tmax_c": round(tmax, 1),
            "tmin_c": round(tmin, 1),
            "wilgotnosc_srednia_pct": round(humidity_mean, 1),
            "wiatr_sredni_ms": round(wind_2m, 2),
            "zachmurzenie_srednie_pct": round(cloud_mean_pct, 1),
            "liczba_probek": len(temps),
            "obliczone_o": dt_util.utcnow().isoformat(),
        }


        """To samo co _async_rain_expected(), ale dodatkowo zapisuje TRWAŁY
        ślad tego konkretnego sprawdzenia - widoczny w
        sensor.garden_irrigation_weather_inputs, atrybut
        'ostatnie_sprawdzenie_prognozy'. Nadpisywany przy KAŻDYM kolejnym
        sprawdzeniu (niezależnie od źródła), więc zawsze pokazuje to, co
        integracja NAPRAWDĘ ostatnio wzięła pod uwagę - z opisem 'źródło'
        (noc / przed zatwierdzeniem / przed sekwencją / godzinne odświeżenie)
        i znacznikiem czasu."""
        skip, forecast = await self._async_rain_expected()
        threshold = float(self.cfg.get(CONF_RAIN_SKIP_THRESHOLD_MM, DEFAULT_RAIN_SKIP_THRESHOLD_MM))
        self._data["rain_forecast_last_check"] = {
            "kiedy": dt_util.now().isoformat(),
            "zrodlo": source,
            "prognoza_mm": forecast,
            "prog_mm": threshold,
            "wstrzymano": skip,
        }
        return skip, forecast

    def _is_raining_now(self) -> bool | None:
        """Szybki detektor 'czy pada TERAZ' z opcjonalnej encji (np. z Twojej
        stacji pogody) - reaguje natychmiast, bez czekania na akumulację mm w
        liczniku total rain. Obsługuje dwa typy encji:
        - binary_sensor (np. dedykowany czujnik deszczu) - stan on/off wprost,
        - zwykły sensor liczbowy (np. sensor.ws_rain_rate w mm/h) - porównanie
          z progiem rain_rate_threshold_mmh.
        Zwraca None, jeśli sensor nie jest skonfigurowany albo jego stan jest
        nieznany - wtedy wywołujący MUSI skorzystać z total_rain jako
        zapasowego sposobu wykrycia."""
        entity_id = self.cfg.get(CONF_RAIN_DETECTED_SENSOR)
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable", ""):
            return None

        if entity_id.startswith("binary_sensor."):
            return state.state == "on"

        try:
            rate = float(state.state)
        except (ValueError, TypeError):
            return None
        threshold = float(self.cfg.get(CONF_RAIN_RATE_THRESHOLD_MMH, DEFAULT_RAIN_RATE_THRESHOLD_MMH))
        return rate > threshold

    async def _apply_rain_forecast_hold(self) -> None:
        """Wywoływane co noc przy przeliczaniu dnia - wstępne oznaczenie stref."""
        skip, forecast = await self._async_rain_expected_tracked("noc")
        threshold = float(self.cfg.get(CONF_RAIN_SKIP_THRESHOLD_MM, DEFAULT_RAIN_SKIP_THRESHOLD_MM))
        # trwała migawka TYLKO z nocnego przeliczenia - nadpisywana wyłącznie
        # przy KOLEJNYM nocnym przeliczeniu (nie przy każdym sprawdzeniu w
        # ciągu dnia, w odróżnieniu od 'rain_forecast_last_check' wyżej)
        self._data["rain_forecast_nightly"] = {
            "data": dt_util.now().date().isoformat(),
            "prognoza_mm": forecast,
            "prog_mm": threshold,
            "wstrzymano": skip,
        }
        if not skip:
            return
        for zid, zstate in self._data["zones"].items():
            if zstate.get("status") == ZONE_STATUS_PENDING:
                zstate["status"] = ZONE_STATUS_IDLE
                zstate["pending_min"] = 0
                zstate["skip_reason"] = f"prognoza opadu {forecast:.1f} mm ≥ próg - wstrzymano"
                _LOGGER.info(
                    "Strefa %s wstrzymana - prognoza opadu %.1f mm (deficyt zostaje, dogoni jutro)",
                    zid, forecast,
                )

    # --------------------------------------------------------- flow-metering

    @staticmethod
    def _is_active_state(state: str) -> bool:
        """switch: 'on', valve: 'open' (a przejściowo też 'opening')."""
        return state in ("on", "open", "opening")

    @callback
    def _on_switch_change(self, event) -> None:
        entity_id = event.data.get("entity_id")
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        if new_state is None or old_state is None:
            return
        zid = self._zone_id_for_switch(entity_id)
        if zid is None:
            return
        zone = self.zones[zid]
        was_active = self._is_active_state(old_state.state)
        is_active = self._is_active_state(new_state.state)

        if not was_active and is_active:
            # zawór się otworzył - zapamiętaj odczyt przepływomierza i czas
            # startu (do samo-kalibracji rzeczywistej wydajności strefy)
            if zone["flow_sensor"]:
                start = _safe_float(self.hass, zone["flow_sensor"])
                self._data["flow_start"][str(zid)] = start
            self._data.setdefault("flow_start_time", {})[str(zid)] = dt_util.utcnow().isoformat()
            self._data["zones"][str(zid)]["status"] = ZONE_STATUS_RUNNING
            self.hass.async_create_task(self._async_persist())

        elif was_active and not is_active:
            zstate = self._data["zones"].setdefault(str(zid), {"smd": 0.0})
            depth_applied = None
            measured_from_flow_sensor = False
            if zone["flow_sensor"]:
                start = self._data["flow_start"].get(str(zid))
                end_state = self.hass.states.get(zone["flow_sensor"])
                end = _safe_float(self.hass, zone["flow_sensor"])
                if start is not None and end is not None and end >= start:
                    raw_used = end - start
                    unit = end_state.attributes.get("unit_of_measurement") if end_state else None
                    liters_used = _volume_to_liters(raw_used, unit)
                    depth_applied = liters_used / zone["area_m2"] if zone["area_m2"] else None
                    measured_from_flow_sensor = depth_applied is not None
            if depth_applied is None:
                # brak przepływomierza / błędny odczyt - licz z czasu pracy i efektywnej
                # (wyuczonej, jeśli już jest, w przeciwnym razie ręcznej) wydajności
                # (przybliżenie - nie znamy dokładnie ile trwało włączenie, więc korzystamy z pending_min)
                depth_applied = self._effective_rate_mmh(zid, zone) * (zstate.get("pending_min", 0) / 60)

            # samo-kalibracja rzeczywistej wydajności strefy - TYLKO gdy mamy
            # prawdziwy pomiar z przepływomierza (nie szacunek), zawór był
            # otwarty wystarczająco długo, żeby pomiar miał sens, ORAZ strefa
            # ma włączony przełącznik "Ucz się z wodomierza" (jeśli wyłączony,
            # świadomie NIE zapisujemy nauczonej wartości - nie tylko jej nie
            # używamy - żeby sensor wydajności nie pokazywał czegoś, co i tak
            # jest ignorowane)
            if measured_from_flow_sensor and zone.get("learn_rate_from_flow", True):
                start_time_str = self._data.get("flow_start_time", {}).get(str(zid))
                elapsed_min = None
                if start_time_str:
                    start_time = dt_util.parse_datetime(start_time_str)
                    if start_time:
                        elapsed_min = (dt_util.utcnow() - start_time).total_seconds() / 60
                if elapsed_min and elapsed_min >= 1 and depth_applied > 0:
                    measured_rate = depth_applied / (elapsed_min / 60)
                    # sanity check - odrzuć skrajnie nierealne odczyty (np.
                    # glitch przepływomierza), zamiast psuć nauczoną wartość.
                    # Górna granica 500 (nie 200) - potwierdzone bezpośrednim
                    # pomiarem, że małe strefy (np. donice) z niemałym
                    # przepływem mogą legalnie osiągać 200+ mm/h, patrz README
                    if 0.5 <= measured_rate <= 500:
                        prev_rate = zstate.get("learned_rate_mmh")
                        prev_samples = zstate.get("learned_rate_samples", 0)
                        if prev_rate is None:
                            new_rate = measured_rate
                        else:
                            # wygładzanie wykładnicze - nowsze pomiary ważą
                            # więcej, ale pojedynczy dziwny wynik nie zepsuje
                            # od razu całej historii
                            new_rate = prev_rate * 0.7 + measured_rate * 0.3
                        zstate["learned_rate_mmh"] = round(new_rate, 2)
                        zstate["learned_rate_samples"] = min(prev_samples + 1, 999)
                        zstate["last_measured_rate_mmh"] = round(measured_rate, 2)
                        _LOGGER.info(
                            "Strefa %s: samo-kalibracja wydajności - zmierzono %.1f mm/h "
                            "(uśredniona: %.1f mm/h, próbka #%s)",
                            zid, measured_rate, new_rate, zstate["learned_rate_samples"],
                        )
            self._data.get("flow_start_time", {}).pop(str(zid), None)

            zstate["smd"] = max(0.0, zstate.get("smd", 0.0) - depth_applied)
            zstate["smd_projected"] = max(0.0, zstate.get("smd_projected", 0.0) - depth_applied)
            zstate["pending_mm"] = 0.0
            zstate["pending_min"] = 0
            zstate["status"] = ZONE_STATUS_DONE
            self._data["flow_start"].pop(str(zid), None)
            self._compute_projected_status(zid)

            # statystyki zużycia wody + data ostatniego podlewania (do bramki
            # minimalnego odstępu między podlewaniami)
            liters_delivered = max(0.0, depth_applied) * zone.get("area_m2", 0.0)
            if liters_delivered > 0:
                self._maybe_roll_water_stats_month()
                self._maybe_roll_water_stats_year()
                # zaokrąglenie do 0,1 L (nie 0,01) - to faktyczna, prawdziwa
                # granica precyzji typowego licznika wody (device_class water),
                # który sam raportuje objętość w m³ z ograniczoną liczbą miejsc
                # po przecinku (np. 0,0001 m³ = 0,1 L) - druga cyfra po przecinku
                # sugerowałaby precyzję, której odczyt fizycznie nie ma
                zstate["water_today_l"] = round(zstate.get("water_today_l", 0.0) + liters_delivered, 1)
                zstate["water_month_l"] = round(zstate.get("water_month_l", 0.0) + liters_delivered, 1)
                zstate["water_year_l"] = round(zstate.get("water_year_l", 0.0) + liters_delivered, 1)
                zstate["water_last_watering_l"] = round(liters_delivered, 1)
                zstate["last_watering_at"] = dt_util.now().isoformat()
                self._data["water_today_total_l"] = round(
                    self._data.get("water_today_total_l", 0.0) + liters_delivered, 1
                )
                self._data["water_month_total_l"] = round(
                    self._data.get("water_month_total_l", 0.0) + liters_delivered, 1
                )
                self._data["water_year_total_l"] = round(
                    self._data.get("water_year_total_l", 0.0) + liters_delivered, 1
                )
                zstate["last_watered"] = dt_util.now().date().isoformat()

            self.hass.async_create_task(self._async_persist())
            self.async_set_updated_data(self._data)

    def _maybe_roll_water_stats_month(self) -> None:
        current_month = dt_util.now().strftime("%Y-%m")
        if self._data.get("water_stats_month") != current_month:
            self._data["water_stats_month"] = current_month
            self._data["water_month_total_l"] = 0.0
            for zstate in self._data["zones"].values():
                zstate["water_month_l"] = 0.0

    def _maybe_roll_water_stats_year(self) -> None:
        current_year = dt_util.now().strftime("%Y")
        if self._data.get("water_stats_year") != current_year:
            self._data["water_stats_year"] = current_year
            self._data["water_year_total_l"] = 0.0
            for zstate in self._data["zones"].values():
                zstate["water_year_l"] = 0.0

    def _create_issue(self, issue_id: str, translation_key: str, placeholders: dict | None = None) -> None:
        # usuń i utwórz od nowa za każdym razem, zamiast liczyć na to, że HA
        # zaktualizuje słownik podstawień (translation_placeholders) w JUŻ
        # istniejącym, aktywnym zgłoszeniu - podejrzenie: HA może nie
        # odświeżać tego słownika dla zgłoszenia, które od dawna jest aktywne
        # bez przerwy (warunek cały czas prawdziwy), co dawałoby dokładnie
        # obserwowany objaw: treść szablonu się aktualizuje (wczytywana
        # świeżo z plików tłumaczeń), ale wartości podstawień - nie
        ir.async_delete_issue(self.hass, DOMAIN, issue_id)
        ir.async_create_issue(
            self.hass, DOMAIN, issue_id,
            is_fixable=False, severity=ir.IssueSeverity.WARNING,
            translation_key=translation_key, translation_placeholders=placeholders or {},
        )

    def _delete_issue(self, issue_id: str) -> None:
        ir.async_delete_issue(self.hass, DOMAIN, issue_id)

    def _zone_id_for_switch(self, entity_id: str) -> int | None:
        for zid, zone in self.zones.items():
            if zone["switch"] == entity_id:
                return zid
        return None

    def _compute_projected_status(self, zid: int) -> None:
        """Wersja _compute_zone_status dla PODGLĄDU - czysty wynik modelu
        bilansu wodnego (deficyt vs próg), bez żadnych bramek decyzyjnych
        (deszcz/prognoza/wiatr/przymrozek/minimalny odstęp). Nie wpływa na
        żadną faktyczną decyzję o podlewaniu - wyłącznie do wglądu."""
        zone = self.zones.get(zid)
        zstate = self._data["zones"].get(str(zid))
        if not zone or not zstate:
            return
        available_water_mm = zone["awc_mm_per_m"] * (zone["root_depth_mm"] / 1000)
        mad_used = zstate.get("mad_adjusted", zone["mad"])
        threshold = available_water_mm * mad_used
        smd = zstate.get("smd_projected", 0.0)

        if smd >= threshold and smd > 0:
            depth_needed = min(smd, available_water_mm)
            runtime_min = math.ceil((depth_needed / self._effective_rate_mmh(zid, zone)) * 60)
            zstate["pending_mm_projected"] = round(depth_needed, 1)
            zstate["pending_min_projected"] = min(runtime_min, zone["max_runtime_min"])
        else:
            zstate["pending_mm_projected"] = 0.0
            zstate["pending_min_projected"] = 0

    def _effective_rate_mmh(self, zid: int, zone: dict) -> float:
        """Zwraca rzeczywistą, samo-wyuczoną wydajność strefy (z pomiarów
        przepływomierza), jeśli integracja zdążyła się już czegoś nauczyć -
        w przeciwnym razie wartość ręcznie wpisaną w konfiguracji. Respektuje
        przełącznik 'Ucz się z wodomierza' - jeśli wyłączony, zawsze zwraca
        wartość ręczną, niezależnie od tego, czy coś już wyuczono."""
        if not zone.get("learn_rate_from_flow", True):
            return zone["rate_mmh"]
        zstate = self._data["zones"].get(str(zid), {})
        learned = zstate.get("learned_rate_mmh")
        return learned if learned else zone["rate_mmh"]

    def _compute_zone_status(self, zid: int) -> None:
        """Ustala pending_mm/pending_min/status na podstawie aktualnego SMD i
        progu, oraz stosuje bramkę minimalnego odstępu między podlewaniami
        (żeby korzenie uczyły się sięgać głębiej, zamiast przyzwyczajać się do
        codziennego płytkiego podlewania). Próg (MAD) jest dynamicznie
        korygowany co noc wg wzoru FAO-56 na podstawie wczorajszego ETc - przy
        upale/suszy próg jest niższy (podlewanie wcześniej), przy chłodnej,
        pochmurnej pogodzie wyższy. Minimalny odstęp między podlewaniami jest
        pomijany w dniach, które FAO-56 definiuje jako 'gorące i suche'
        (ETc > 5 mm/dzień - dokładnie tam, gdzie korekta p staje się ujemna).
        NIE czekamy na skrajny dół wzoru (p=0,1) - w polskim klimacie
        praktycznie nieosiągalny nawet w upały, więc obejście nigdy by nie
        zadziałało w praktyce."""
        zone = self.zones.get(zid)
        zstate = self._data["zones"].get(str(zid))
        if not zone or not zstate:
            return
        available_water_mm = zone["awc_mm_per_m"] * (zone["root_depth_mm"] / 1000)
        mad_used = zstate.get("mad_adjusted", zone["mad"])
        threshold = available_water_mm * mad_used
        smd = zstate.get("smd", 0.0)

        if smd >= threshold and smd > 0:
            depth_needed = min(smd, available_water_mm)
            runtime_min = math.ceil((depth_needed / self._effective_rate_mmh(zid, zone)) * 60)
            zstate["pending_mm"] = round(depth_needed, 1)
            zstate["pending_min"] = min(runtime_min, zone["max_runtime_min"])
            zstate["status"] = ZONE_STATUS_PENDING
            zstate["skip_reason"] = None

            min_days = zone.get("min_days_between_watering", 0)
            emergency_override = (
                self._data.get("dynamic_mad_enabled", True)
                and (zstate.get("etc_yesterday_mm") or 0.0) > 5.0
            )
            last_watered_str = zstate.get("last_watered")
            if min_days > 0 and last_watered_str and not emergency_override:
                try:
                    last_watered = date.fromisoformat(last_watered_str)
                    days_since = (dt_util.now().date() - last_watered).days
                    if days_since < min_days:
                        zstate["status"] = ZONE_STATUS_IDLE
                        zstate["pending_min"] = 0
                        zstate["skip_reason"] = (
                            f"minimalny odstęp {min_days} dni między podlewaniami "
                            f"(ostatnio {days_since} dni temu)"
                        )
                except ValueError:
                    pass
            elif min_days > 0 and last_watered_str and emergency_override:
                _LOGGER.info(
                    "Strefa %s: minimalny odstęp POMINIĘTY - wczorajsze ETc (%.1f mm/dzień) "
                    "przekroczyło próg 5 mm/dzień (FAO-56 'gorące i suche warunki')",
                    zid, zstate.get("etc_yesterday_mm") or 0.0,
                )
        else:
            zstate["pending_mm"] = 0.0
            zstate["pending_min"] = 0
            zstate["status"] = ZONE_STATUS_IDLE
            zstate["skip_reason"] = None

    def _recompute_zone_pending(self, zid: int) -> None:
        """Wywoływane po świeżym odjęciu zmierzonego opadu tuż przed startem -
        przelicza status i, jeśli strefa właśnie 'wypadła' z pending z powodu
        opadu, ustawia odpowiedni komunikat."""
        zstate = self._data["zones"].get(str(zid))
        was_pending = bool(zstate) and zstate.get("status") == ZONE_STATUS_PENDING
        self._compute_zone_status(zid)
        if zstate and was_pending and zstate.get("status") == ZONE_STATUS_IDLE and not zstate.get("skip_reason"):
            zstate["skip_reason"] = "zmierzony opad tuż przed startem pokrył zapotrzebowanie"

    def _prepare_heat_candidates(self, today: date) -> None:
        """ETAP A wymuszonego podlewania przed upałem - wywoływane RAZ, przy
        nocnym przeliczeniu (_roll_over_day), PRZED jakimkolwiek pytaniem
        pogody o prognozę. Tu zapada wyłącznie kwalifikacja "czy ta strefa
        jest w ogóle KANDYDATEM" na podstawie samego stanu lokalnego:

        - strefa już zakwalifikowana normalnie (zwykły próg MAD) -> pomijamy,
          i tak wejdzie do kolejki, upał nie musi jej niczego "wymuszać"
        - deficyt powyżej skonfigurowanego progu % -> pomijamy (to już nie
          jest "profilaktyczne doładowanie", tylko zwykłe zaległe podlewanie,
          które i tak się zdarzy)
        - ostatnie wymuszenie było zbyt niedawno (min_days) -> pomijamy
          (bezpiecznik przed wymuszaniem codziennie w wielodniowej fali upałów)

        Wynik (lista ID stref-kandydatów) jest zapisywany trwale w
        self._data["heat_candidates"] i wykorzystywany PÓŹNIEJ, tego samego
        dnia, w ETAPIE B (patrz _async_confirm_heat_candidates), gdzie
        dopiero pytamy o prognozę ET0/opadu. Rozdzielenie na dwa etapy jest
        celowe - dzięki temu harmonogram startu (liczony wstecz od wschodu)
        od razu uwzględnia PEŁNY, potencjalny skład kolejki, zamiast dokładać
        kandydatów tuż przed startem i psuć już wyliczony czas."""
        candidates: list[int] = []
        for zid, zone in self.zones.items():
            if not zone.get("force_heat_enabled"):
                continue
            zstate = self._data["zones"].get(str(zid))
            if not zstate:
                continue
            if zstate.get("status") == ZONE_STATUS_PENDING:
                # i tak wejdzie do kolejki normalnie - upał nie musi nic wymuszać
                continue
            available_water_mm = zone["awc_mm_per_m"] * (zone["root_depth_mm"] / 1000)
            mad_used = zstate.get("mad_adjusted", zone["mad"])
            threshold = available_water_mm * mad_used
            if threshold <= 0:
                continue
            smd = zstate.get("smd", 0.0)
            deficit_pct = (smd / threshold) * 100
            max_pct = zone.get("force_heat_deficit_pct", DEFAULT_FORCE_HEAT_DEFICIT_PCT)
            if deficit_pct > max_pct:
                continue
            min_days = zone.get("force_heat_min_days", DEFAULT_FORCE_HEAT_MIN_DAYS)
            last_forced_str = zstate.get("last_forced_heat_date")
            if min_days > 0 and last_forced_str:
                try:
                    last_forced = date.fromisoformat(last_forced_str)
                    if (today - last_forced).days < min_days:
                        continue
                except ValueError:
                    pass
            candidates.append(zid)
            zstate["heat_candidate"] = True

        for zid, zstate in self._data["zones"].items():
            if int(zid) not in candidates:
                zstate.pop("heat_candidate", None)

        self._data["heat_candidates"] = candidates
        self._data["heat_candidates_confirmed"] = False
        if candidates:
            _LOGGER.info(
                "Wymuszone podlewanie przed upałem: %s kandydat(ów) na dziś (%s) - "
                "ostateczna decyzja po sprawdzeniu prognozy ET0 tuż przed sekwencją",
                len(candidates), [self.zones[z]["name"] for z in candidates],
            )

    async def _async_confirm_heat_candidates(self, rain_skip: bool, rain_mm: float | None) -> None:
        """ETAP B - wywoływane RAZ, tuż przed startem sekwencji, zaraz po
        ogólnym sprawdzeniu prognozy opadu "przed sekwencją" (rain_skip/
        rain_mm to WYNIK TEGO SAMEGO sprawdzenia - przekazany, a nie pytany
        drugi raz, żeby nie dublować zapytań do usługi pogodowej i nie
        nadpisywać diagnostyki dwoma niezależnymi śladami). Podejmuje
        OSTATECZNĄ decyzję dla kandydatów wyznaczonych w ETAPIE A
        (_prepare_heat_candidates) - nie dokłada tu żadnych NOWYCH
        kandydatów, tylko potwierdza albo odrzuca te już wyznaczone o
        północy (patrz uzasadnienie w README)."""
        candidates: list[int] = self._data.get("heat_candidates") or []
        if not candidates or self._data.get("heat_candidates_confirmed"):
            return
        self._data["heat_candidates_confirmed"] = True

        if self.cfg.get(CONF_RAIN_PRIORITY_OVER_HEAT, DEFAULT_RAIN_PRIORITY_OVER_HEAT) and rain_skip:
            _LOGGER.info(
                "Wymuszone podlewanie przed upałem: ODWOŁANE dla %s stref - prognoza opadu "
                "(%.1f mm) ma pierwszeństwo",
                len(candidates), rain_mm or 0.0,
            )
            self._data["heat_candidates"] = []
            for zid in candidates:
                zstate = self._data["zones"].get(str(zid))
                if zstate:
                    zstate.pop("heat_candidate", None)
            await self._async_persist()
            return

        forecast = await self._async_forecast_et0_today()
        self._data["heat_forecast_today"] = forecast
        threshold = float(self.cfg.get(CONF_HEAT_ET0_THRESHOLD_MM, DEFAULT_HEAT_ET0_THRESHOLD_MM))
        et0 = forecast.get("et0_mm") if forecast else None

        if et0 is None or et0 < threshold:
            _LOGGER.info(
                "Wymuszone podlewanie przed upałem: ODRZUCONE dla %s stref - prognozowane ET0 "
                "(%s mm) poniżej progu (%.1f mm) albo prognoza niedostępna",
                len(candidates), et0, threshold,
            )
            reason = (
                f"wymuszenie przed upałem odrzucone - prognoza ET0 ({et0} mm) poniżej progu ({threshold} mm)"
                if et0 is not None else
                "wymuszenie przed upałem odrzucone - prognoza pogody niedostępna"
            )
            for zid in candidates:
                zstate = self._data["zones"].get(str(zid))
                if zstate:
                    zstate.pop("heat_candidate", None)
                    zstate["skip_reason"] = reason
            self._data["heat_candidates"] = []
            await self._async_persist()
            return

        today_str = dt_util.now().date().isoformat()
        confirmed_names = []
        for zid in candidates:
            zone = self.zones.get(zid)
            zstate = self._data["zones"].get(str(zid))
            if not zone or not zstate:
                continue
            available_water_mm = zone["awc_mm_per_m"] * (zone["root_depth_mm"] / 1000)
            smd = zstate.get("smd", 0.0)
            depth_needed = max(0.0, available_water_mm - smd)
            if depth_needed <= 0:
                zstate.pop("heat_candidate", None)
                continue
            runtime_min = math.ceil((depth_needed / self._effective_rate_mmh(zid, zone)) * 60)
            zstate["pending_mm"] = round(depth_needed, 1)
            zstate["pending_min"] = min(runtime_min, zone["max_runtime_min"])
            zstate["status"] = ZONE_STATUS_PENDING
            zstate["skip_reason"] = None
            zstate["forced_heat_watering"] = True
            zstate["last_forced_heat_date"] = today_str
            zstate.pop("heat_candidate", None)
            confirmed_names.append(zone["name"])
        self._data["heat_candidates"] = []
        _LOGGER.info(
            "Wymuszone podlewanie przed upałem: POTWIERDZONE dla %s (ET0 %.1f mm ≥ próg %.1f mm)",
            confirmed_names, et0, threshold,
        )
        await self._async_persist()

    # ------------------------------------------------------- bramki globalne

    def _current_temperature_c(self) -> float | None:
        return _safe_float(self.hass, self.cfg.get(CONF_TEMP_SENSOR))

    def _frost_risk(self) -> tuple[bool, float | None]:
        temp = self._current_temperature_c()
        threshold = float(self.cfg.get(CONF_FROST_THRESHOLD_C, DEFAULT_FROST_THRESHOLD_C))
        if temp is None:
            return False, None
        return temp <= threshold, temp

    def _apply_frost_hold(self) -> None:
        """Wywoływane co noc - jeśli aktualna temperatura wskazuje na ryzyko
        przymrozku, wstrzymuje WSZYSTKIE oczekujące strefy (dotyczy całego
        systemu - węże/zawory, nie tylko konkretnej rośliny)."""
        risk, temp = self._frost_risk()
        if not risk:
            return
        for zid, zstate in self._data["zones"].items():
            if zstate.get("status") == ZONE_STATUS_PENDING:
                zstate["status"] = ZONE_STATUS_IDLE
                zstate["pending_min"] = 0
                zstate["skip_reason"] = f"ryzyko przymrozku - temperatura {temp:.1f}°C ≤ próg - wstrzymano"
                _LOGGER.info("Strefa %s wstrzymana - ryzyko przymrozku (%.1f°C)", zid, temp)

    def _wind_risk(self) -> tuple[bool, float | None]:
        wind = self._read_wind_speed_ms()
        threshold = float(self.cfg.get(CONF_WIND_SKIP_THRESHOLD_MS, DEFAULT_WIND_SKIP_THRESHOLD_MS))
        if wind is None:
            return False, None
        return wind >= threshold, wind

    def _is_paused(self) -> bool:
        return bool(self._data.get("irrigation_paused"))

    async def async_set_paused(self, paused: bool) -> None:
        self._data["irrigation_paused"] = paused
        await self._async_persist()
        self.async_set_updated_data(self._data)
        _LOGGER.info("Podlewanie %s", "wstrzymane globalnie" if paused else "wznowione")

    async def async_set_dynamic_mad_enabled(self, enabled: bool) -> None:
        self._data["dynamic_mad_enabled"] = enabled
        await self._async_persist()
        self.async_set_updated_data(self._data)
        _LOGGER.info(
            "Dynamiczna korekta MAD (FAO-56) %s", "włączona" if enabled else "wyłączona"
        )

    # --------------------------------------------------------------- akcje

    async def async_approve_zone(self, zid: int) -> None:
        if self._is_paused():
            _LOGGER.info("Strefa %s: podlewanie wstrzymane globalnie (przełącznik pauzy) - pomijam", zid)
            return
        zstate = self._data["zones"].get(str(zid))
        if not zstate or zstate["status"] != ZONE_STATUS_PENDING:
            _LOGGER.warning("Strefa %s nie oczekuje na zatwierdzenie", zid)
            return

        # świeże sprawdzenie zmierzonego opadu I prognozy tuż przed startem
        self._async_apply_measured_rain()
        self._recompute_zone_pending(zid)
        if zstate["status"] != ZONE_STATUS_PENDING:
            _LOGGER.info("Strefa %s: pominięto start - %s", zid, zstate.get("skip_reason"))
            await self._async_persist()
            self.async_set_updated_data(self._data)
            return

        skip, forecast = await self._async_rain_expected_tracked("przed zatwierdzeniem strefy")
        if skip:
            zstate["status"] = ZONE_STATUS_IDLE
            zstate["pending_min"] = 0
            zstate["skip_reason"] = f"prognoza opadu {forecast:.1f} mm ≥ próg - wstrzymano tuż przed startem"
            _LOGGER.info("Strefa %s: pominięto start - świeża prognoza opadu %.1f mm", zid, forecast)
            await self._async_persist()
            self.async_set_updated_data(self._data)
            return

        frost_risk, temp = self._frost_risk()
        if frost_risk:
            zstate["status"] = ZONE_STATUS_IDLE
            zstate["pending_min"] = 0
            zstate["skip_reason"] = f"ryzyko przymrozku - temperatura {temp:.1f}°C ≤ próg - wstrzymano tuż przed startem"
            _LOGGER.info("Strefa %s: pominięto start - ryzyko przymrozku (%.1f°C)", zid, temp)
            await self._async_persist()
            self.async_set_updated_data(self._data)
            return

        if self.zones[zid].get("wind_sensitive"):
            windy, wind = self._wind_risk()
            if windy:
                zstate["status"] = ZONE_STATUS_IDLE
                zstate["pending_min"] = 0
                zstate["skip_reason"] = f"wiatr {wind:.1f} m/s ≥ próg - wstrzymano (strefa wrażliwa)"
                _LOGGER.info("Strefa %s: pominięto start - silny wiatr (%.1f m/s)", zid, wind)
                await self._async_persist()
                self.async_set_updated_data(self._data)
                return

        zstate["status"] = ZONE_STATUS_APPROVED
        await self.async_run_zone(zid, zstate["pending_min"])

    async def async_approve_all(self) -> None:
        if self._is_paused():
            _LOGGER.info("Podlewanie wstrzymane globalnie (przełącznik pauzy) - pomijam approve_all")
            return
        for zid, zstate in list(self._data["zones"].items()):
            if zstate["status"] == ZONE_STATUS_PENDING:
                await self.async_approve_zone(int(zid))

    async def async_skip_zone(self, zid: int) -> None:
        zstate = self._data["zones"].get(str(zid))
        if not zstate:
            return
        zstate["status"] = ZONE_STATUS_IDLE
        zstate["pending_mm"] = 0.0
        zstate["pending_min"] = 0
        await self._async_persist()
        self.async_set_updated_data(self._data)

    async def async_run_zone(self, zid: int, minutes: int) -> None:
        zone = self.zones.get(zid)
        if not zone:
            _LOGGER.warning("Nieznana strefa %s", zid)
            return
        minutes = max(1, min(int(minutes), zone["max_runtime_min"]))
        self._data["zones"].setdefault(str(zid), {})["pending_min"] = minutes
        # ręczne wymuszenie (usługa run_zone) - respektuj DOKŁADNIE podaną
        # liczbę minut, bez sterowania objętościowego (zostawiony przez
        # użytkownika 'pending_mm' może być nieaktualny/z innej strefy stanu,
        # bo ta usługa celowo pomija cały mechanizm wyliczania celu)
        self.hass.async_create_task(
            self._async_run_zone_monitored(zid, minutes, use_volume_target=False)
        )
        self.async_set_updated_data(self._data)

    # ------------------------------------------------ sekwencja przed wschodem

    async def async_run_sequence_before_sunrise(self) -> None:
        """Ustala listę zatwierdzonych stref (z uwzględnieniem świeżej kontroli
        prognozy opadu) i planuje ich sekwencyjne uruchomienie tak, aby ostatnia
        strefa zakończyła podlewanie mniej więcej o wschodzie słońca."""
        if self._is_paused():
            _LOGGER.info("Podlewanie wstrzymane globalnie (przełącznik pauzy) - sekwencja nie zaplanowana")
            return

        sunrise_dt = self._next_sunrise()
        if sunrise_dt is None:
            _LOGGER.warning("Nie udało się wyliczyć wschodu słońca - sekwencja nie zaplanowana")
            return

        # świeża kontrola zmierzonego opadu i prognozy - te same zasady co przy zwykłym zatwierdzaniu
        self._async_apply_measured_rain()
        for zid in self.zones:
            self._recompute_zone_pending(zid)
        skip, forecast = await self._async_rain_expected_tracked("przed sekwencją")
        # ETAP B wymuszonego podlewania przed upałem - wykorzystuje TEN SAM
        # wynik sprawdzenia deszczu powyżej (patrz docstring), musi zajść
        # PRZED budową kolejki poniżej, żeby ewentualnie potwierdzone strefy
        # (status ustawiony na PENDING) zdążyły się w niej znaleźć
        await self._async_confirm_heat_candidates(skip, forecast)
        frost_risk, temp = self._frost_risk()
        windy, wind = self._wind_risk()

        queue: list[tuple[int, int]] = []
        for zid_str, zstate in self._data["zones"].items():
            if zstate.get("status") != ZONE_STATUS_PENDING:
                continue
            zid = int(zid_str)
            if skip:
                zstate["status"] = ZONE_STATUS_IDLE
                zstate["pending_min"] = 0
                zstate["skip_reason"] = f"prognoza opadu {forecast:.1f} mm ≥ próg - sekwencja wstrzymana"
                continue
            if frost_risk:
                zstate["status"] = ZONE_STATUS_IDLE
                zstate["pending_min"] = 0
                zstate["skip_reason"] = f"ryzyko przymrozku - temperatura {temp:.1f}°C ≤ próg - sekwencja wstrzymana"
                continue
            if windy and self.zones[zid].get("wind_sensitive"):
                zstate["status"] = ZONE_STATUS_IDLE
                zstate["pending_min"] = 0
                zstate["skip_reason"] = f"wiatr {wind:.1f} m/s ≥ próg - pominięto (strefa wrażliwa)"
                continue
            queue.append((zid, int(zstate["pending_min"])))

        await self._async_persist()
        self.async_set_updated_data(self._data)

        if not queue:
            _LOGGER.info("Brak stref do podlania w sekwencji przed wschodem")
            self._data["sequence_plan"] = {
                "status": "no_zones",
                "computed_at": dt_util.utcnow().isoformat(),
            }
            await self._async_persist()
            self.async_set_updated_data(self._data)
            return

        transition_delay_sec = int(
            self.cfg.get(CONF_ZONE_TRANSITION_DELAY_SEC, DEFAULT_ZONE_TRANSITION_DELAY_SEC)
        )
        total_minutes = sum(minutes for _, minutes in queue)
        total_transition_min = (len(queue) - 1) * transition_delay_sec / 60 if len(queue) > 1 else 0
        start_time = self._target_start_bound(sunrise_dt, total_minutes, total_transition_min)
        now = dt_util.now()
        if start_time <= now:
            _LOGGER.info(
                "Sekwencja: wyliczony start (%s) już minął - start natychmiast",
                start_time,
            )
            start_time = now

        # buduję listę z planowaną godziną startu KAŻDEJ strefy (kumulatywnie, z przerwą tranzycyjną)
        zone_plan = []
        cursor = start_time
        for zid, minutes in queue:
            zone_plan.append(
                {
                    "zone_id": zid,
                    "name": self.zones[zid]["name"],
                    "planned_start": cursor.isoformat(),
                    "minutes": minutes,
                }
            )
            cursor += timedelta(minutes=minutes, seconds=transition_delay_sec)

        self._data["sequence_plan"] = {
            "status": "scheduled",
            "computed_at": dt_util.utcnow().isoformat(),
            "start": start_time.isoformat(),
            "sunrise_target": sunrise_dt.isoformat(),
            "total_minutes": total_minutes,
            "zones": zone_plan,
        }
        await self._async_persist()
        self.async_set_updated_data(self._data)

        _LOGGER.info(
            "Zaplanowano sekwencję %s stref (łącznie %s min), start %s, planowany koniec %s",
            len(queue), total_minutes, start_time, sunrise_dt,
        )
        self.hass.async_create_task(self._async_sequence_worker(queue, start_time))

    async def _async_verify_valve_state(self, zone: dict, expected_active: bool, timeout_sec: int) -> bool:
        """Odpytuje stan encji zaworu co 1s, aż potwierdzi oczekiwany stan
        (otwarty/zamknięty) albo upłynie timeout. Jeśli strefa ma skonfigurowany
        przepływomierz CHWILOWY, dodatkowo wymaga, żeby przepływ się zgadzał z
        oczekiwanym stanem (>próg przy otwieraniu, <próg przy zamykaniu) -
        to mocniejsze potwierdzenie niż sam stan encji (wychwytuje np. zawór,
        który raportuje 'zamknięty', ale fizycznie przecieka). Brak odczytu z
        przepływomierza (niedostępny) nie blokuje weryfikacji - liczy się
        wtedy tylko stan encji, jak dotychczas."""
        entity_id = zone["switch"]
        flow_rate_entity = zone.get("flow_rate_sensor")
        flow_threshold = float(
            self.cfg.get(CONF_FLOW_RATE_ZERO_THRESHOLD, DEFAULT_FLOW_RATE_ZERO_THRESHOLD)
        )
        elapsed = 0
        while elapsed <= timeout_sec:
            state = self.hass.states.get(entity_id)
            entity_ok = (
                state is not None
                and state.state not in ("unknown", "unavailable")
                and self._is_active_state(state.state) == expected_active
            )
            flow_ok = True
            if entity_ok and flow_rate_entity:
                flow_state = self.hass.states.get(flow_rate_entity)
                flow_val = _safe_float(self.hass, flow_rate_entity)
                if flow_val is not None:
                    unit = flow_state.attributes.get("unit_of_measurement") if flow_state else None
                    flow_val_lpm = _flow_rate_to_lpm(flow_val, unit)
                    is_flowing = flow_val_lpm > flow_threshold
                    flow_ok = is_flowing == expected_active
            if entity_ok and flow_ok:
                return True
            await asyncio.sleep(1)
            elapsed += 1
        return False

    async def _async_run_zone_monitored(self, zid: int, minutes: int, use_volume_target: bool = True) -> bool:
        """Otwiera zawor i pilnuje go az do zakonczenia, sprawdzajac co
        `rain_pause_check_interval_min` minut zarowno deszcz, jak i (jesli
        strefa ma przeplywomierz) faktycznie dostarczona objetosc wody:

        - Ze przeplywomierzem: zamyka zawor, gdy dostarczona objetosc
          osiagnie wyliczony cel (mm x powierzchnia) - NIEZALEZNIE od tego, czy
          stalo sie to szybciej czy wolniej niz szacowany czas. Jesli po
          szacowanym czasie cel jeszcze nie jest osiagniety (np. spadek
          cisnienia, wolniejszy przeplyw niz zwykle), podlewanie jest
          automatycznie WYDLUZANE, az do twardego limitu max_runtime_min -
          ten limit nigdy nie jest przekraczany, niezaleznie od wszystkiego.
        - Bez przeplywomierza: czysto czasowe, jak dotychczas - zamyka po
          wyliczonym czasie, bez mozliwosci potwierdzenia/wydluzenia.

        Deszcz w trakcie podlewania (niezaleznie od powyzszego):
        - zamyka zawor natychmiast (nie ma sensu podlewac w deszcz),
        - czeka do rain_pause_max_wait_min na ustanie opadu,
        - jesli opad ustanie: WZNAWIA te sama strefe na POZOSTALY czas/objetosc,
        - jesli opad trwa dluzej: PODDAJE SIE, zwraca False (sygnal do
          przerwania reszty kolejki/sekwencji).

        Po zakonczeniu zapisuje w zstate sposob zakonczenia
        ('objetosc_osiagnieta' / 'czas' / 'limit_bezpieczenstwa'), planowany
        i faktyczny czas - widoczne w atrybutach sensora statusu strefy.

        Zwraca True, jesli strefa zostala w pelni podlana (od razu albo po
        wznowieniu), False jesli poddano sie z powodu dlugotrwalego deszczu."""
        zone = self.zones.get(zid)
        if not zone:
            return True
        estimated_min = max(1, min(int(minutes), zone["max_runtime_min"]))
        remaining_min = estimated_min
        domain = zone["switch"].split(".")[0]
        open_service, close_service = ("open_valve", "close_valve") if domain == "valve" else ("turn_on", "turn_off")

        check_interval_min = int(self.cfg.get(CONF_RAIN_PAUSE_CHECK_INTERVAL_MIN, DEFAULT_RAIN_PAUSE_CHECK_INTERVAL_MIN))
        pause_threshold = float(self.cfg.get(CONF_RAIN_PAUSE_THRESHOLD_MM, DEFAULT_RAIN_PAUSE_THRESHOLD_MM))
        max_wait_min = int(self.cfg.get(CONF_RAIN_PAUSE_MAX_WAIT_MIN, DEFAULT_RAIN_PAUSE_MAX_WAIT_MIN))

        zstate0 = self._data["zones"].setdefault(str(zid), {})
        target_mm = zstate0.get("pending_mm", 0.0)
        target_liters = target_mm * zone["area_m2"] if zone.get("area_m2") else None
        use_volume_control = (
            use_volume_target
            and zone.get("adjust_runtime_from_flow", True)
            and bool(zone.get("flow_sensor"))
            and bool(target_liters)
            and target_liters > 0
        )
        session_start_flow = None
        total_elapsed_min = 0.0

        while remaining_min > 0:
            zstate = self._data["zones"].setdefault(str(zid), {})
            zstate["status"] = ZONE_STATUS_APPROVED
            # jedna decyzja ("Automatycznie dostosuj czas podlewania zgodny z
            # pomiarem zużycia"), dwie konsekwencje razem, nie osobno:
            # - WŁĄCZONE (domyślnie): czas może się wydłużyć/skrócić na żywo
            #   wg przepływomierza (patrz use_volume_control wyżej), a watchdog
            #   ustawiany na CAŁY limit bezpieczeństwa strefy (pomniejszony o
            #   czas już zużyty w tej sesji) - żeby sterownik nigdy nie ucierpiał
            #   podlewania przed integracją, zanim ta dociągnie do celu.
            # - WYŁĄCZONE: czysto czasowe, bez wydłużania/skracania na żywo, a
            #   watchdog dopasowany dokładnie do wyliczonego/pozostałego czasu
            #   TEJ sesji - ciaśniejsze zabezpieczenie, spójne z tym, że
            #   integracja i tak nigdy nie zamierza podlewać dłużej.
            if zone.get("adjust_runtime_from_flow", True):
                watchdog_min = math.ceil(zone["max_runtime_min"] - total_elapsed_min)
            else:
                watchdog_min = remaining_min
            zstate["pending_min"] = remaining_min
            self.async_set_updated_data(self._data)

            if zone.get("timer_entity"):
                try:
                    await self.hass.services.async_call(
                        "number", "set_value",
                        {"entity_id": zone["timer_entity"], "value": max(1, watchdog_min)},
                        blocking=True,
                    )
                except Exception as err:  # noqa: BLE001 - nie blokuj podlewania z powodu watchdoga
                    _LOGGER.warning("Nie udalo sie ustawic watchdog timera dla strefy %s: %s", zid, err)

            await self.hass.services.async_call(domain, open_service, {"entity_id": zone["switch"]}, blocking=True)

            verify_timeout = int(
                self.cfg.get(CONF_VALVE_VERIFY_TIMEOUT_SEC, DEFAULT_VALVE_VERIFY_TIMEOUT_SEC)
            )
            opened_ok = await self._async_verify_valve_state(zone, True, verify_timeout)
            if not opened_ok:
                _LOGGER.error(
                    "Strefa %s: zawor %s NIE potwierdzil otwarcia w ciagu %ss - pomijam te strefe "
                    "(sprawdz sterownik/lacznosc), reszta sekwencji bedzie kontynuowana",
                    zid, zone["switch"], verify_timeout,
                )
                zstate["status"] = ZONE_STATUS_IDLE
                zstate["pending_min"] = 0
                zstate["skip_reason"] = "blad: zawor nie potwierdzil otwarcia"
                self._create_issue(
                    f"valve_open_failed_zone_{zid}", "valve_open_failed",
                    {"garden_irrigation_zone_name": zone["name"], "entity_id": zone["switch"]},
                )
                self.async_set_updated_data(self._data)
                return True
            self._delete_issue(f"valve_open_failed_zone_{zid}")

            # przy pierwszym (nie po pauzie deszczowej) otwarciu tej sesji -
            # zapamietaj odczyt przeplywomierza jako punkt odniesienia dla
            # sterowania objetosciowego (CALEJ sesji, nie tylko tego segmentu -
            # dzieki temu wznowienie po deszczu poprawnie liczy laczna objetosc)
            if use_volume_control and session_start_flow is None:
                session_start_flow = _safe_float(self.hass, zone["flow_sensor"])

            # dla stref ze sterowaniem objetosciowym petla moze iterowac DLUZEJ
            # niz pierwotny szacunek (remaining_min) - az do twardego limitu
            # bezpieczenstwa - jesli cel objetosciowy jeszcze nie jest osiagniety
            segment_limit_min = (
                max(remaining_min, zone["max_runtime_min"] - total_elapsed_min)
                if use_volume_control else remaining_min
            )

            elapsed_min = 0.0
            rained_during_run = False
            volume_reached = False
            trigger_reason = ""
            while elapsed_min < segment_limit_min:
                step = min(check_interval_min, segment_limit_min - elapsed_min)
                await asyncio.sleep(step * 60)
                elapsed_min += step

                # zawsze aktualizuj bilans wodny na podstawie total_rain (to musi
                # dzialac niezaleznie od tego, czy jest dodatkowy detektor)
                diff = self._async_apply_measured_rain()

                # WYKRYCIE pauzy: najpierw szybki detektor binarny (jesli
                # skonfigurowany i dostepny) - reaguje natychmiast, bez czekania
                # na akumulacje mm. W jego braku - total_rain jako zapasowy sposob.
                quick = self._is_raining_now()
                if quick is not None:
                    if quick:
                        rained_during_run = True
                        trigger_reason = "szybki detektor deszczu zglosil opad"
                        break
                elif diff >= pause_threshold:
                    rained_during_run = True
                    trigger_reason = f"zmierzony opad +{diff:.1f} mm (total rain)"
                    break

                # STEROWANIE OBJETOSCIOWE - sprawdz, czy dostarczono juz
                # wystarczajaco wody, niezaleznie od uplywu czasu
                if use_volume_control and session_start_flow is not None:
                    flow_state = self.hass.states.get(zone["flow_sensor"])
                    current = _safe_float(self.hass, zone["flow_sensor"])
                    if current is not None and current >= session_start_flow:
                        unit = flow_state.attributes.get("unit_of_measurement") if flow_state else None
                        delivered_liters = _volume_to_liters(current - session_start_flow, unit)
                        if delivered_liters >= target_liters:
                            volume_reached = True
                            break

            total_elapsed_min += elapsed_min

            if volume_reached or not rained_during_run:
                await self.hass.services.async_call(
                    domain, close_service, {"entity_id": zone["switch"]}, blocking=True
                )
                closed_ok = await self._async_verify_valve_state(zone, False, verify_timeout)
                if not closed_ok:
                    _LOGGER.error(
                        "Strefa %s: zawor %s NIE potwierdzil zamkniecia w ciagu %ss - PRZERYWAM "
                        "reszte sekwencji dla bezpieczenstwa (sprawdz recznie, czy zawor faktycznie sie zamknal!)",
                        zid, zone["switch"], verify_timeout,
                    )
                    zstate["status"] = ZONE_STATUS_IDLE
                    zstate["skip_reason"] = "blad: zawor nie potwierdzil zamkniecia - sprawdz recznie!"
                    self._create_issue(
                        f"valve_close_failed_zone_{zid}", "valve_close_failed",
                        {"garden_irrigation_zone_name": zone["name"], "entity_id": zone["switch"]},
                    )
                    self.async_set_updated_data(self._data)
                    return False
                self._delete_issue(f"valve_close_failed_zone_{zid}")

                if volume_reached:
                    completion_method = "objetosc_osiagnieta"
                elif use_volume_control and total_elapsed_min >= zone["max_runtime_min"] - 0.01:
                    completion_method = "limit_bezpieczenstwa"
                    _LOGGER.warning(
                        "Strefa %s: osiagnieto limit bezpieczenstwa (%s min) BEZ dostarczenia "
                        "wyliczonej ilosci wody (%.1f mm) - sprawdz cisnienie/wydajnosc strefy",
                        zid, zone["max_runtime_min"], target_mm,
                    )
                else:
                    completion_method = "czas"
                zstate["completion_method"] = completion_method
                zstate["planned_runtime_min"] = estimated_min
                zstate["actual_runtime_min"] = round(total_elapsed_min, 1)
                zstate["runtime_extended_min"] = round(max(0.0, total_elapsed_min - estimated_min), 1)
                return True

            # zaczelo padac w trakcie podlewania - zamknij zawor i czekaj
            await self.hass.services.async_call(domain, close_service, {"entity_id": zone["switch"]}, blocking=True)
            closed_ok = await self._async_verify_valve_state(zone, False, verify_timeout)
            if not closed_ok:
                _LOGGER.error(
                    "Strefa %s: zawor %s NIE potwierdzil zamkniecia po wykryciu deszczu w ciagu "
                    "%ss - PRZERYWAM reszte sekwencji dla bezpieczenstwa (sprawdz recznie!)",
                    zid, zone["switch"], verify_timeout,
                )
                zstate["status"] = ZONE_STATUS_IDLE
                zstate["skip_reason"] = "blad: zawor nie potwierdzil zamkniecia po deszczu - sprawdz recznie!"
                self._create_issue(
                    f"valve_close_failed_zone_{zid}", "valve_close_failed",
                    {"garden_irrigation_zone_name": zone["name"], "entity_id": zone["switch"]},
                )
                self.async_set_updated_data(self._data)
                return False
            self._delete_issue(f"valve_close_failed_zone_{zid}")
            remaining_min = max(1, remaining_min - elapsed_min)
            zstate["status"] = ZONE_STATUS_PAUSED_RAIN
            zstate["skip_reason"] = f"wstrzymano - {trigger_reason}"
            self.async_set_updated_data(self._data)
            _LOGGER.info(
                "Strefa %s: wstrzymano w trakcie podlewania (%s), dostarczono dotad %.1f min pracy",
                zid, trigger_reason, total_elapsed_min,
            )

            confirmation_min = int(
                self.cfg.get(CONF_RAIN_STOP_CONFIRMATION_MIN, DEFAULT_RAIN_STOP_CONFIRMATION_MIN)
            )
            # ile mm spadło PODCZAS TEJ konkretnej pauzy - osobne od SMD (które
            # miesza w sobie deszcz I wodę z wodociągu) - potrzebne, żeby
            # pomniejszyć cel TEJ sesji dokładnie o deszcz, nie dublując
            # odliczenia wody już dostarczonej z wodociągu (to liczy się
            # osobno, przez session_start_flow, i NIE jest tu ruszane)
            rain_during_pause_mm = 0.0
            waited_min = 0
            clean_streak_min = 0
            covered_by_rain = False
            while True:
                await asyncio.sleep(check_interval_min * 60)
                waited_min += check_interval_min
                diff = self._async_apply_measured_rain()
                if diff > 0:
                    rain_during_pause_mm += diff
                # żywy zapis - widoczny na bieżąco w trakcie pauzy, nie tylko
                # po jej zakończeniu (np. sensor.<strefa>_zalecane_podlewanie)
                zstate["rain_during_current_pause_mm"] = round(rain_during_pause_mm, 2)
                self.async_set_updated_data(self._data)
                if diff < pause_threshold:
                    # brak opadu w TYM sprawdzeniu - ale wznawiamy dopiero po
                    # NIEPRZERWANYM okresie ciszy (confirmation_min), nie od
                    # razu po pierwszym czystym sprawdzeniu. Deszcz często
                    # pada impulsowo (kilka fal, nie jeden ciągły opad) - bez
                    # tego zabezpieczenia zawór otwierałby się i zamykał na
                    # przemian z każdą przerwą między falami, niepotrzebnie
                    # zużywając mechanicznie elektrozawór.
                    clean_streak_min += check_interval_min
                else:
                    # znowu wykryto opad - zeruje licznik ciszy, trzeba zacząć
                    # odliczać nieprzerwany okres od nowa
                    clean_streak_min = 0
                if rain_during_pause_mm >= target_mm:
                    # deszcz PODCZAS pauzy sam już pokrył cel tej strefy -
                    # dalsze podlewanie niepotrzebne, niezależnie od tego, czy
                    # nadal pada
                    covered_by_rain = True
                    break
                if clean_streak_min >= confirmation_min:
                    break
                if waited_min >= max_wait_min:
                    # bezpiecznik czasowy - NIE rezygnujemy z podlewania z
                    # powodu długiego opadu (tylko z powodu pokrycia
                    # zapotrzebowania, sprawdzone wyżej) - po prostu przestajemy
                    # czekać na potwierdzenie ciszy i wznawiamy z tym, co
                    # zdążyliśmy zmierzyć, zamiast czekać w nieskończoność
                    _LOGGER.info(
                        "Strefa %s: opad trwa dłużej niż %s min (limit oczekiwania na potwierdzenie "
                        "ciszy) - wznawiam mimo to, z pomniejszonym celem, zamiast rezygnować",
                        zid, max_wait_min,
                    )
                    break

            # niezależnie od powodu wyjścia z pętli - przelicz cel na nowo,
            # pomniejszony o deszcz, który spadł PODCZAS tej pauzy (woda z
            # wodociągu już dostarczona w tej sesji jest liczona osobno,
            # przez session_start_flow, i tu w ogóle nie jest ruszana)
            target_mm = max(0.0, target_mm - rain_during_pause_mm)
            target_liters = target_mm * zone["area_m2"] if zone.get("area_m2") else None
            use_volume_control = (
                use_volume_target
                and zone.get("adjust_runtime_from_flow", True)
                and bool(zone.get("flow_sensor"))
                and bool(target_liters)
                and target_liters > 0
            )

            if covered_by_rain or target_mm <= 0.01:
                _LOGGER.info(
                    "Strefa %s: podczas pauzy spadło %.1f mm - to pokrywa cel tej strefy, "
                    "podlewanie niepotrzebne",
                    zid, rain_during_pause_mm,
                )
                zstate["status"] = ZONE_STATUS_IDLE
                zstate["pending_min"] = 0
                zstate["skip_reason"] = f"deficyt pokryty przez deszcz w trakcie pauzy (+{rain_during_pause_mm:.1f} mm)"
                self.async_set_updated_data(self._data)
                return True

            if not use_volume_control:
                # dla stref bez sterowania objętościowego (albo z wyłączonym
                # dostosowywaniem) - przelicz też szacowany, pozostały czas na
                # podstawie pomniejszonego celu, żeby nie kontynuować liczenia
                # od starego, nieaktualnego już szacunku
                rate = self._effective_rate_mmh(zid, zone)
                remaining_min = max(1, math.ceil((target_mm / rate) * 60)) if rate else remaining_min

            _LOGGER.info(
                "Strefa %s: wznawiam - podczas pauzy spadło %.1f mm, pozostały cel: %.1f mm",
                zid, rain_during_pause_mm, target_mm,
            )
            # petla while remaining_min > 0 wznowi strefe na pozostaly czas/objetosc

        return True

    async def _async_sequence_worker(self, queue: list[tuple[int, int]], start_time: datetime) -> None:
        delay = (start_time - dt_util.utcnow()).total_seconds()
        if delay > 0:
            await asyncio.sleep(delay)

        if self._data.get("sequence_plan"):
            self._data["sequence_plan"]["status"] = "running"
            self.async_set_updated_data(self._data)

        transition_delay_sec = int(
            self.cfg.get(CONF_ZONE_TRANSITION_DELAY_SEC, DEFAULT_ZONE_TRANSITION_DELAY_SEC)
        )

        for idx, (zid, minutes) in enumerate(queue):
            # jeśli w międzyczasie ktoś ręcznie pominął/zatwierdził strefę inaczej, uszanuj to
            zstate = self._data["zones"].get(str(zid))
            if zstate and zstate.get("status") == ZONE_STATUS_IDLE and zstate.get("skip_reason"):
                continue
            completed = await self._async_run_zone_monitored(zid, minutes)
            if not completed:
                # niepotwierdzone zamknięcie zaworu (JEDYNY powód False - deszcz
                # już nigdy nie anuluje reszty kolejki, patrz _async_run_zone_monitored)
                # - anuluj resztę kolejki, nie otwieraj kolejnej strefy dopóki nie ma
                # pewności, że poprzednia jest bezpiecznie zamknięta
                for rzid, _ in queue[idx + 1:]:
                    rzstate = self._data["zones"].get(str(rzid))
                    if rzstate and rzstate.get("status") == ZONE_STATUS_PENDING:
                        rzstate["status"] = ZONE_STATUS_IDLE
                        rzstate["pending_min"] = 0
                        rzstate["skip_reason"] = "reszta sekwencji anulowana - poprzednia strefa nie zakończyła poprawnie"
                if self._data.get("sequence_plan"):
                    self._data["sequence_plan"]["status"] = "cancelled_rain"
                await self._async_persist()
                self.async_set_updated_data(self._data)
                _LOGGER.info("Sekwencja przerwana - poprzednia strefa nie zakończyła poprawnie")
                return

            # przerwa tranzycyjna: daje integracji czas na dokończenie odczytu
            # przepływomierza (event zamknięcia już potwierdzony przez weryfikację
            # w _async_run_zone_monitored) zanim otworzy kolejny zawór
            if idx < len(queue) - 1 and transition_delay_sec > 0:
                await asyncio.sleep(transition_delay_sec)

        if self._data.get("sequence_plan"):
            self._data["sequence_plan"]["status"] = "done"
        await self._async_persist()
        self.async_set_updated_data(self._data)
