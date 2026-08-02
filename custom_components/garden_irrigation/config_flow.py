"""Config flow dla Garden Irrigation."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    CONF_AUTO_MODE_ENABLED,
    CONF_AUTO_TRIGGER_BUFFER_MIN,
    CONF_HUMIDITY_SENSOR,
    CONF_MAIN_FLOW_RATE_SENSOR,
    CONF_MAIN_FLOW_SENSOR,
    CONF_FLOW_RATE_ZERO_THRESHOLD,
    CONF_FROST_THRESHOLD_C,
    CONF_DYNAMIC_MAD_ENABLED,
    CONF_GARDEN_LOCATION,
    CONF_PRESSURE_SENSOR,
    CONF_RAIN_DETECTED_SENSOR,
    CONF_RAIN_FORECAST_SENSOR,
    CONF_RAIN_PAUSE_CHECK_INTERVAL_MIN,
    CONF_RAIN_PAUSE_MAX_WAIT_MIN,
    CONF_RAIN_STOP_CONFIRMATION_MIN,
    CONF_RAIN_PAUSE_THRESHOLD_MM,
    CONF_RAIN_RATE_THRESHOLD_MMH,
    CONF_RAIN_SENSOR,
    CONF_RAIN_SKIP_THRESHOLD_MM,
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
    DEFAULT_DYNAMIC_MAD_ENABLED,
    DEFAULT_PLANT,
    DEFAULT_RAIN_PAUSE_CHECK_INTERVAL_MIN,
    DEFAULT_RAIN_PAUSE_MAX_WAIT_MIN,
    DEFAULT_RAIN_STOP_CONFIRMATION_MIN,
    DEFAULT_RAIN_PAUSE_THRESHOLD_MM,
    DEFAULT_RAIN_RATE_THRESHOLD_MMH,
    DEFAULT_RAIN_SKIP_THRESHOLD_MM,
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
    MAX_ZONE_COUNT,
    PLANTS,
    SOIL_TYPES,
    ZONE_FIELD_AREA,
    ZONE_FIELD_FLOW,
    ZONE_FIELD_FLOW_RATE,
    ZONE_FIELD_MAX_RUNTIME,
    ZONE_FIELD_NAME,
    ZONE_FIELD_PLANTS,
    ZONE_FIELD_RATE,
    ZONE_FIELD_IRRIGATION_TYPE,
    ZONE_FIELD_DRIP_LINE_LENGTH_M,
    ZONE_FIELD_DRIP_SPACING_CM,
    ZONE_FIELD_DRIP_EMITTER_LPH,
    ZONE_FIELD_DRIP_COUNT,
    ZONE_FIELD_LEARN_RATE_FROM_FLOW,
    ZONE_FIELD_AUTO_CALC_RATE,
    IRRIGATION_TYPES,
    IRRIGATION_TYPE_DRIP_LINE,
    IRRIGATION_TYPE_DRIP_POINTS,
    DRIP_LINE_WETTED_STRIP_WIDTH_M,
    DEFAULT_IRRIGATION_TYPE,
    DEFAULT_LEARN_RATE_FROM_FLOW,
    DEFAULT_AUTO_CALC_RATE,
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
)


def _weather_schema(defaults: dict[str, Any], hass=None) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(
                CONF_TEMP_SENSOR, description={"suggested_value": defaults.get(CONF_TEMP_SENSOR)}
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
            ),
            vol.Optional(
                CONF_SOLAR_SENSOR, description={"suggested_value": defaults.get(CONF_SOLAR_SENSOR)}
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Optional(
                CONF_WIND_SENSOR, description={"suggested_value": defaults.get(CONF_WIND_SENSOR)}
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Optional(
                CONF_HUMIDITY_SENSOR, description={"suggested_value": defaults.get(CONF_HUMIDITY_SENSOR)}
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="humidity")
            ),
            vol.Optional(
                CONF_RAIN_SENSOR, description={"suggested_value": defaults.get(CONF_RAIN_SENSOR)}
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Optional(
                CONF_RAIN_FORECAST_SENSOR,
                description={"suggested_value": defaults.get(CONF_RAIN_FORECAST_SENSOR)},
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Optional(
                CONF_WEATHER_ENTITY, description={"suggested_value": defaults.get(CONF_WEATHER_ENTITY)}
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="weather")),
            vol.Optional(
                CONF_WEATHER_FORECAST_HOURS,
                default=defaults.get(CONF_WEATHER_FORECAST_HOURS, DEFAULT_WEATHER_FORECAST_HOURS),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=24, step=1, unit_of_measurement="h")
            ),
            vol.Optional(
                CONF_WEATHER_FORECAST_INTERVAL_MIN,
                default=defaults.get(
                    CONF_WEATHER_FORECAST_INTERVAL_MIN, DEFAULT_WEATHER_FORECAST_INTERVAL_MIN
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=15, max=360, step=15, unit_of_measurement="min")
            ),
            vol.Optional(
                CONF_RAIN_DETECTED_SENSOR, description={"suggested_value": defaults.get(CONF_RAIN_DETECTED_SENSOR)}
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["binary_sensor", "sensor"])
            ),
            vol.Optional(
                CONF_RAIN_RATE_THRESHOLD_MMH,
                default=defaults.get(CONF_RAIN_RATE_THRESHOLD_MMH, DEFAULT_RAIN_RATE_THRESHOLD_MMH),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=20, step=0.1, unit_of_measurement="mm/h")
            ),
            vol.Optional(
                CONF_RAIN_SKIP_THRESHOLD_MM,
                default=defaults.get(CONF_RAIN_SKIP_THRESHOLD_MM, DEFAULT_RAIN_SKIP_THRESHOLD_MM),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=20, step=0.5, unit_of_measurement="mm")
            ),
            vol.Optional(
                CONF_START_MODE, default=defaults.get(CONF_START_MODE, DEFAULT_START_MODE)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(
                            value="finish_at_sunrise",
                            label="Zakończ ostatnią strefę o wschodzie (wstecz od sumy czasów)",
                        ),
                        selector.SelectOptionDict(value="at_sunrise", label="Start dokładnie o wschodzie"),
                        selector.SelectOptionDict(
                            value="before_sunrise", label="Start X minut PRZED wschodem (stały odstęp)"
                        ),
                        selector.SelectOptionDict(
                            value="after_sunrise", label="Start X minut PO wschodzie (stały odstęp)"
                        ),
                    ],
                    mode="dropdown",
                )
            ),
            vol.Optional(
                CONF_START_OFFSET_MIN,
                default=defaults.get(CONF_START_OFFSET_MIN, DEFAULT_START_OFFSET_MIN),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=240, step=5, unit_of_measurement="min")
            ),
            vol.Optional(
                CONF_RAIN_PAUSE_THRESHOLD_MM,
                default=defaults.get(CONF_RAIN_PAUSE_THRESHOLD_MM, DEFAULT_RAIN_PAUSE_THRESHOLD_MM),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0.1, max=10, step=0.1, unit_of_measurement="mm")
            ),
            vol.Optional(
                CONF_RAIN_PAUSE_CHECK_INTERVAL_MIN,
                default=defaults.get(
                    CONF_RAIN_PAUSE_CHECK_INTERVAL_MIN, DEFAULT_RAIN_PAUSE_CHECK_INTERVAL_MIN
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=15, step=1, unit_of_measurement="min")
            ),
            vol.Optional(
                CONF_RAIN_PAUSE_MAX_WAIT_MIN,
                default=defaults.get(CONF_RAIN_PAUSE_MAX_WAIT_MIN, DEFAULT_RAIN_PAUSE_MAX_WAIT_MIN),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=5, max=120, step=5, unit_of_measurement="min")
            ),
            vol.Optional(
                CONF_RAIN_STOP_CONFIRMATION_MIN,
                default=defaults.get(CONF_RAIN_STOP_CONFIRMATION_MIN, DEFAULT_RAIN_STOP_CONFIRMATION_MIN),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=60, step=1, unit_of_measurement="min")
            ),
            vol.Optional(
                CONF_AUTO_MODE_ENABLED, default=defaults.get(CONF_AUTO_MODE_ENABLED, True)
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_AUTO_TRIGGER_BUFFER_MIN,
                default=defaults.get(CONF_AUTO_TRIGGER_BUFFER_MIN, DEFAULT_AUTO_TRIGGER_BUFFER_MIN),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=60, step=1, unit_of_measurement="min")
            ),
            vol.Optional(
                CONF_UPDATE_INTERVAL,
                default=defaults.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=5, max=60, step=5, unit_of_measurement="min")
            ),
            vol.Optional(
                CONF_PRESSURE_SENSOR, description={"suggested_value": defaults.get(CONF_PRESSURE_SENSOR)}
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="pressure")
            ),
            vol.Optional(
                CONF_ZONE_TRANSITION_DELAY_SEC,
                default=defaults.get(CONF_ZONE_TRANSITION_DELAY_SEC, DEFAULT_ZONE_TRANSITION_DELAY_SEC),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=60, step=1, unit_of_measurement="s")
            ),
            vol.Optional(
                CONF_VALVE_VERIFY_TIMEOUT_SEC,
                default=defaults.get(CONF_VALVE_VERIFY_TIMEOUT_SEC, DEFAULT_VALVE_VERIFY_TIMEOUT_SEC),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=5, max=120, step=5, unit_of_measurement="s")
            ),
            vol.Optional(
                CONF_MAIN_FLOW_SENSOR, description={"suggested_value": defaults.get(CONF_MAIN_FLOW_SENSOR)}
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Optional(
                CONF_MAIN_FLOW_RATE_SENSOR, description={"suggested_value": defaults.get(CONF_MAIN_FLOW_RATE_SENSOR)}
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Optional(
                CONF_FLOW_RATE_ZERO_THRESHOLD,
                default=defaults.get(CONF_FLOW_RATE_ZERO_THRESHOLD, DEFAULT_FLOW_RATE_ZERO_THRESHOLD),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=10, step=0.1, unit_of_measurement="L/min")
            ),
            vol.Optional(
                CONF_WIND_SKIP_THRESHOLD_MS,
                default=defaults.get(CONF_WIND_SKIP_THRESHOLD_MS, DEFAULT_WIND_SKIP_THRESHOLD_MS),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=25, step=0.5, unit_of_measurement="m/s")
            ),
            vol.Optional(
                CONF_FROST_THRESHOLD_C,
                default=defaults.get(CONF_FROST_THRESHOLD_C, DEFAULT_FROST_THRESHOLD_C),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=-10, max=10, step=0.5, unit_of_measurement="°C")
            ),
            vol.Optional(
                CONF_DYNAMIC_MAD_ENABLED,
                default=defaults.get(CONF_DYNAMIC_MAD_ENABLED, DEFAULT_DYNAMIC_MAD_ENABLED),
            ): selector.BooleanSelector(),
        }
    )


def _location_schema(defaults: dict[str, Any], hass=None) -> vol.Schema:
    """Osobny, izolowany krok - TYLKO mapa lokalizacji ogrodu. Celowo oddzielony
    od reszty formularza pogody, żeby w razie problemu było jasne, że to
    dokładnie ten selektor jest podejrzany, a nie któreś z 27 innych pól."""
    default_location = defaults.get(CONF_GARDEN_LOCATION)
    if not isinstance(default_location, dict) or default_location.get("latitude") is None:
        if hass is not None and hass.config.latitude:
            default_location = {
                "latitude": hass.config.latitude,
                "longitude": hass.config.longitude,
                "radius": 10,
            }
        else:
            default_location = {"latitude": 52.0, "longitude": 21.0, "radius": 10}

    return vol.Schema(
        {
            vol.Optional(
                CONF_GARDEN_LOCATION, default=default_location
            ): selector.LocationSelector(selector.LocationSelectorConfig(radius=True)),
        }
    )


def _zone_count_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_ZONE_COUNT, default=defaults.get(CONF_ZONE_COUNT, DEFAULT_ZONE_COUNT)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=MAX_ZONE_COUNT, step=1, mode="box")
            ),
        }
    )


def _suggested_rate_mmh(prefix: str, defaults: dict[str, Any], learned_rate: float | None = None) -> float | None:
    """Sugeruje wartość pola 'Wydajność'. Priorytet: (1) wartość WYUCZONA
    przez samo-kalibrację z przepływomierza, jeśli integracja już się czegoś
    nauczyła - bardziej wiarygodna niż jakikolwiek statyczny wzór/tabela;
    (2) wyliczenie z typu nawadniania i jego parametrów; dostępne tylko
    wtedy, gdy strefa była już wcześniej zapisana (ten sam ograniczenie co
    przy wyborze głębokości korzeni: formularz HA nie może odczytać pól
    wypełnianych w tym samym kroku). Wynik to tylko PODPOWIEDŹ w polu -
    użytkownik może ją swobodnie nadpisać ręcznie."""
    if learned_rate:
        return round(learned_rate, 1)

    itype = defaults.get(prefix + ZONE_FIELD_IRRIGATION_TYPE, DEFAULT_IRRIGATION_TYPE)
    info = IRRIGATION_TYPES.get(itype)
    if info and info["default_rate_mmh"] is not None:
        return info["default_rate_mmh"]

    emitter = defaults.get(prefix + ZONE_FIELD_DRIP_EMITTER_LPH)
    if itype == IRRIGATION_TYPE_DRIP_LINE:
        length = defaults.get(prefix + ZONE_FIELD_DRIP_LINE_LENGTH_M)
        spacing_cm = defaults.get(prefix + ZONE_FIELD_DRIP_SPACING_CM)
        if length and spacing_cm and emitter:
            count = length / (spacing_cm / 100)
            flow_lh = count * emitter
            effective_area = length * DRIP_LINE_WETTED_STRIP_WIDTH_M
            if effective_area > 0:
                return round(flow_lh / effective_area, 1)
        return None

    if itype == IRRIGATION_TYPE_DRIP_POINTS:
        count = defaults.get(prefix + ZONE_FIELD_DRIP_COUNT)
        area = defaults.get(prefix + ZONE_FIELD_AREA)
        if count and emitter and area:
            flow_lh = count * emitter
            return round(flow_lh / area, 1)
        return None

    return None


def _root_depth_override_options(selected_plant_keys: list[str]) -> list:
    """Buduje listę wyboru głębokości korzeni z roślin JUŻ ZAPISANYCH w tej
    strefie (z poprzedniego zapisu konfiguracji) - posortowaną rosnąco wg Kc,
    z Kc widocznym w etykiecie każdej opcji. Puste, jeśli strefa jeszcze nigdy
    nie została zapisana z wybranymi roślinami (formularz HA nie może
    dynamicznie filtrować pól na podstawie innych pól wypełnianych w tym
    samym kroku - lista odzwierciedla stan sprzed tego zapisu)."""
    entries = [
        (key, PLANTS[key]) for key in (selected_plant_keys or []) if key in PLANTS
    ]
    entries.sort(key=lambda item: item[1]["kc"])
    options = [
        selector.SelectOptionDict(
            value=key,
            label=f"{val['label']} (Kc {val['kc']:.2f}, korzenie {val['root_depth_mm']} mm)",
        )
        for key, val in entries
    ]
    return options


def _zone_schema(index: int, defaults: dict[str, Any], learned_rate: float | None = None) -> dict:
    prefix = f"zone{index}_"
    plant_options = [
        selector.SelectOptionDict(value=key, label=val["label"]) for key, val in PLANTS.items()
    ]
    soil_options = [
        selector.SelectOptionDict(value=key, label=val["label"]) for key, val in SOIL_TYPES.items()
    ]
    return {
        vol.Optional(
            prefix + ZONE_FIELD_NAME, default=defaults.get(prefix + ZONE_FIELD_NAME, "")
        ): selector.TextSelector(),
        vol.Optional(
            prefix + ZONE_FIELD_SWITCH,
            description={"suggested_value": defaults.get(prefix + ZONE_FIELD_SWITCH)},
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["switch", "valve"])
        ),
        vol.Optional(
            prefix + ZONE_FIELD_FLOW, description={"suggested_value": defaults.get(prefix + ZONE_FIELD_FLOW)}
        ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
        vol.Optional(
            prefix + ZONE_FIELD_FLOW_RATE, description={"suggested_value": defaults.get(prefix + ZONE_FIELD_FLOW_RATE)}
        ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
        vol.Optional(
            prefix + ZONE_FIELD_SOIL,
            default=defaults.get(prefix + ZONE_FIELD_SOIL, DEFAULT_SOIL),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(options=soil_options, mode="dropdown")
        ),
        vol.Optional(
            prefix + ZONE_FIELD_PLANTS,
            default=defaults.get(prefix + ZONE_FIELD_PLANTS, [DEFAULT_PLANT]),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(options=plant_options, mode="dropdown", multiple=True)
        ),
        vol.Optional(
            prefix + ZONE_FIELD_AREA, default=defaults.get(prefix + ZONE_FIELD_AREA, 10.0)
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=1000, step=0.5, unit_of_measurement="m²")
        ),
        vol.Optional(
            prefix + ZONE_FIELD_IRRIGATION_TYPE,
            default=defaults.get(prefix + ZONE_FIELD_IRRIGATION_TYPE, DEFAULT_IRRIGATION_TYPE),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(value=key, label=val["label"])
                    for key, val in IRRIGATION_TYPES.items()
                ],
                mode="dropdown",
            )
        ),
        vol.Optional(
            prefix + ZONE_FIELD_DRIP_LINE_LENGTH_M,
            description={"suggested_value": defaults.get(prefix + ZONE_FIELD_DRIP_LINE_LENGTH_M)},
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=500, step=0.5, unit_of_measurement="m")
        ),
        vol.Optional(
            prefix + ZONE_FIELD_DRIP_SPACING_CM,
            description={"suggested_value": defaults.get(prefix + ZONE_FIELD_DRIP_SPACING_CM)},
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=1, max=200, step=1, unit_of_measurement="cm")
        ),
        vol.Optional(
            prefix + ZONE_FIELD_DRIP_EMITTER_LPH,
            description={"suggested_value": defaults.get(prefix + ZONE_FIELD_DRIP_EMITTER_LPH)},
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0.1, max=50, step=0.1, unit_of_measurement="L/h")
        ),
        vol.Optional(
            prefix + ZONE_FIELD_DRIP_COUNT,
            description={"suggested_value": defaults.get(prefix + ZONE_FIELD_DRIP_COUNT)},
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=1, max=200, step=1, unit_of_measurement="szt.")
        ),
        vol.Optional(
            prefix + ZONE_FIELD_AUTO_CALC_RATE,
            default=defaults.get(prefix + ZONE_FIELD_AUTO_CALC_RATE, DEFAULT_AUTO_CALC_RATE),
        ): selector.BooleanSelector(),
        vol.Optional(
            prefix + ZONE_FIELD_RATE,
            description={
                "suggested_value": (
                    _suggested_rate_mmh(prefix, defaults, learned_rate)
                    if defaults.get(prefix + ZONE_FIELD_AUTO_CALC_RATE, DEFAULT_AUTO_CALC_RATE)
                    else None
                )
                or defaults.get(prefix + ZONE_FIELD_RATE)
                or 10.0
            },
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0.5, max=500, step=0.1, mode="box", unit_of_measurement="mm/h")
        ),
        vol.Optional(
            prefix + ZONE_FIELD_LEARN_RATE_FROM_FLOW,
            default=defaults.get(prefix + ZONE_FIELD_LEARN_RATE_FROM_FLOW, DEFAULT_LEARN_RATE_FROM_FLOW),
        ): selector.BooleanSelector(),
        vol.Optional(
            prefix + ZONE_FIELD_MAX_RUNTIME,
            default=defaults.get(prefix + ZONE_FIELD_MAX_RUNTIME, 30),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=1, max=240, step=1, unit_of_measurement="min")
        ),
        vol.Optional(
            prefix + ZONE_FIELD_TIMER, description={"suggested_value": defaults.get(prefix + ZONE_FIELD_TIMER)}
        ): selector.EntitySelector(selector.EntitySelectorConfig(domain="number")),
        vol.Optional(
            prefix + ZONE_FIELD_ADJUST_RUNTIME_FROM_FLOW,
            default=defaults.get(prefix + ZONE_FIELD_ADJUST_RUNTIME_FROM_FLOW, DEFAULT_ADJUST_RUNTIME_FROM_FLOW),
        ): selector.BooleanSelector(),
        vol.Optional(
            prefix + ZONE_FIELD_KC_OVERRIDE,
            default=defaults.get(prefix + ZONE_FIELD_KC_OVERRIDE, ""),
        ): selector.TextSelector(),
        vol.Optional(
            prefix + ZONE_FIELD_MAD_OVERRIDE,
            default=defaults.get(prefix + ZONE_FIELD_MAD_OVERRIDE, ""),
        ): selector.TextSelector(),
        vol.Optional(
            prefix + ZONE_FIELD_ROOT_DEPTH_OVERRIDE_PLANT,
            description={"suggested_value": defaults.get(prefix + ZONE_FIELD_ROOT_DEPTH_OVERRIDE_PLANT)},
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=_root_depth_override_options(defaults.get(prefix + ZONE_FIELD_PLANTS, [])),
                mode="dropdown",
            )
        ),
        vol.Optional(
            prefix + ZONE_FIELD_MIN_DAYS_BETWEEN,
            default=defaults.get(prefix + ZONE_FIELD_MIN_DAYS_BETWEEN, 0),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=30, step=1, unit_of_measurement="dni")
        ),
        vol.Optional(
            prefix + ZONE_FIELD_WIND_SENSITIVE,
            default=defaults.get(prefix + ZONE_FIELD_WIND_SENSITIVE, False),
        ): selector.BooleanSelector(),
    }


def _zones_schema(
    zone_count: int, defaults: dict[str, Any], hass=None, entry_id: str | None = None
) -> vol.Schema:
    # jeśli integracja jest już uruchomiona (edytujesz istniejący wpis przez
    # "Konfiguruj"), sprawdź, czy poszczególne strefy zdążyły się już czegoś
    # nauczyć z przepływomierza - jeśli tak, formularz podpowie tę wartość
    # zamiast zawsze wracać do statycznego wzoru/tabeli
    learned_rates: dict[int, float] = {}
    if hass is not None and entry_id is not None:
        coordinator = hass.data.get(DOMAIN, {}).get(entry_id)
        if coordinator is not None:
            for zid_str, zstate in coordinator.data.get("zones", {}).items():
                rate = zstate.get("learned_rate_mmh")
                if rate:
                    try:
                        learned_rates[int(zid_str)] = rate
                    except ValueError:
                        pass

    schema: dict = {}
    for i in range(1, zone_count + 1):
        schema.update(_zone_schema(i, defaults, learned_rates.get(i)))
    return vol.Schema(schema)


class GardenIrrigationConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Kreator konfiguracji: pogoda -> lokalizacja -> liczba stref -> szczegóły stref."""

    VERSION = 2

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_location()
        return self.async_show_form(step_id="user", data_schema=_weather_schema({}, self.hass))

    async def async_step_location(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_zone_count()
        return self.async_show_form(
            step_id="location", data_schema=_location_schema(self._data, self.hass)
        )

    async def async_step_zone_count(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_zones()
        return self.async_show_form(
            step_id="zone_count", data_schema=_zone_count_schema(self._data)
        )

    async def async_step_zones(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._data.update(user_input)
            title = "Ogród - Inteligentne Nawadnianie" if self.hass.config.language.startswith("pl") else "Garden - Smart Irrigation"
            return self.async_create_entry(title=title, data=self._data)

        zone_count = int(self._data.get(CONF_ZONE_COUNT, DEFAULT_ZONE_COUNT))
        return self.async_show_form(
            step_id="zones", data_schema=_zones_schema(zone_count, {})
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return GardenIrrigationOptionsFlow(config_entry)


class GardenIrrigationOptionsFlow(config_entries.OptionsFlow):
    """Pozwala edytować pogodę, liczbę i szczegóły stref po instalacji."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry
        self._current = {**config_entry.data, **config_entry.options}
        self._data: dict[str, Any] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_location()
        return self.async_show_form(
            step_id="init", data_schema=_weather_schema(self._current, self.hass)
        )

    async def async_step_location(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_zone_count()
        return self.async_show_form(
            step_id="location", data_schema=_location_schema(self._current, self.hass)
        )

    async def async_step_zone_count(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_zones()
        return self.async_show_form(
            step_id="zone_count", data_schema=_zone_count_schema(self._current)
        )

    async def async_step_zones(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            merged = {**self._current, **self._data, **user_input}
            return self.async_create_entry(title="", data=merged)

        zone_count = int(self._data.get(CONF_ZONE_COUNT, self._current.get(CONF_ZONE_COUNT, DEFAULT_ZONE_COUNT)))
        return self.async_show_form(
            step_id="zones",
            data_schema=_zones_schema(zone_count, self._current, self.hass, self._config_entry.entry_id),
        )
