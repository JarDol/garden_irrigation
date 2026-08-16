"""Config flow dla Garden Irrigation.

Architektura (od 1.15.0): zamiast jednego, liniowego kreatora ze wszystkimi
~30 polami na kilku zbitych ekranach, formularz jest podzielony na 6
tematycznych kategorii + lokalizację + liczbę stref + osobny ekran per
strefa. Nawigacja odbywa się przez menu (async_show_menu) - po wypełnieniu
dowolnej kategorii wracasz do tego samego menu i możesz wybrać cokolwiek
innego, w dowolnej kolejności (to jest nasz odpowiednik "Wstecz" - sam
przycisk "Wstecz" w kreatorach HA NIE istnieje jako oficjalna funkcja,
sprawdzone w aktualnej dokumentacji deweloperskiej). Ten sam mechanizm
działa identycznie przy pierwszej instalacji (ConfigFlow) i przy edycji
później (OptionsFlow) - obie klasy współdzielą logikę przez
_GardenFlowMixin poniżej.
"""
from __future__ import annotations

from typing import Any, Callable

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
    CONF_HEAT_ET0_THRESHOLD_MM,
    CONF_RAIN_PRIORITY_OVER_HEAT,
    CONF_DYNAMIC_MAD_ENABLED,
    CONF_GARDEN_LOCATION,
    CONF_PRESSURE_SENSOR,
    CONF_RAIN_DETECTED_SENSOR,
    CONF_RAIN_FORECAST_SENSOR,
    CONF_RAIN_FORECAST_LOOKBACK_MIN,
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
    CONF_START_CLOCK_TIME,
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
    DEFAULT_START_CLOCK_TIME,
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
    ZONE_FIELD_GERMINATION_DEPTH_OVERRIDE_MM,
    ZONE_FIELD_YOUNG_DEPTH_OVERRIDE_MM,
    ZONE_FIELD_ROOT_DEPTH_OVERRIDE_PLANT,
    ZONE_FIELD_MIN_DAYS_BETWEEN,
    ZONE_FIELD_WIND_SENSITIVE,
    ZONE_FIELD_FORCE_HEAT_ENABLED,
    ZONE_FIELD_FORCE_HEAT_DEFICIT_PCT,
    ZONE_FIELD_FORCE_HEAT_MIN_DAYS,
    DEFAULT_FORCE_HEAT_ENABLED,
    DEFAULT_FORCE_HEAT_DEFICIT_PCT,
    DEFAULT_FORCE_HEAT_MIN_DAYS,
)


# ---------------------------------------------------------------------------
# 6 kategorii ustawień globalnych - każda to osobny krok kreatora, osiągalny
# z menu głównego w dowolnej kolejności.
# ---------------------------------------------------------------------------

def _schema_tryb_start(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(
                CONF_AUTO_MODE_ENABLED, default=defaults.get(CONF_AUTO_MODE_ENABLED, True)
            ): selector.BooleanSelector(),
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
                        selector.SelectOptionDict(
                            value="finish_at_clock",
                            label="Zakończ ostatnią strefę o wskazanej godzinie (wstecz od sumy czasów)",
                        ),
                        selector.SelectOptionDict(value="at_clock", label="Start dokładnie o wskazanej godzinie"),
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
                CONF_START_CLOCK_TIME,
                default=defaults.get(CONF_START_CLOCK_TIME, DEFAULT_START_CLOCK_TIME),
            ): selector.TimeSelector(),
            vol.Optional(
                CONF_AUTO_TRIGGER_BUFFER_MIN,
                default=defaults.get(CONF_AUTO_TRIGGER_BUFFER_MIN, DEFAULT_AUTO_TRIGGER_BUFFER_MIN),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=60, step=1, unit_of_measurement="min")
            ),
        }
    )


def _schema_zawory_przeplyw(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
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
        }
    )


def _schema_stacja_pogody(defaults: dict[str, Any]) -> vol.Schema:
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
                CONF_PRESSURE_SENSOR, description={"suggested_value": defaults.get(CONF_PRESSURE_SENSOR)}
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="pressure")
            ),
            vol.Optional(
                CONF_RAIN_SENSOR, description={"suggested_value": defaults.get(CONF_RAIN_SENSOR)}
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
        }
    )


def _schema_deszcz_pauza(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
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
        }
    )


def _schema_ochrona(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
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
                CONF_HEAT_ET0_THRESHOLD_MM,
                default=defaults.get(CONF_HEAT_ET0_THRESHOLD_MM, DEFAULT_HEAT_ET0_THRESHOLD_MM),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=3, max=10, step=0.5, unit_of_measurement="mm/dobę")
            ),
            vol.Optional(
                CONF_RAIN_PRIORITY_OVER_HEAT,
                default=defaults.get(CONF_RAIN_PRIORITY_OVER_HEAT, DEFAULT_RAIN_PRIORITY_OVER_HEAT),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_DYNAMIC_MAD_ENABLED,
                default=defaults.get(CONF_DYNAMIC_MAD_ENABLED, DEFAULT_DYNAMIC_MAD_ENABLED),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_UPDATE_INTERVAL,
                default=defaults.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=5, max=60, step=5, unit_of_measurement="min")
            ),
        }
    )


def _schema_prognoza(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
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
                CONF_RAIN_SKIP_THRESHOLD_MM,
                default=defaults.get(CONF_RAIN_SKIP_THRESHOLD_MM, DEFAULT_RAIN_SKIP_THRESHOLD_MM),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=20, step=0.5, unit_of_measurement="mm")
            ),
            vol.Optional(
                CONF_RAIN_FORECAST_LOOKBACK_MIN,
                default=defaults.get(
                    CONF_RAIN_FORECAST_LOOKBACK_MIN, DEFAULT_RAIN_FORECAST_LOOKBACK_MIN
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=15, max=360, step=15, unit_of_measurement="min", mode="slider"
                )
            ),
        }
    )


CATEGORY_SCHEMAS = {
    "tryb_start": _schema_tryb_start,
    "zawory_przeplyw": _schema_zawory_przeplyw,
    "stacja_pogody": _schema_stacja_pogody,
    "deszcz_pauza": _schema_deszcz_pauza,
    "ochrona": _schema_ochrona,
    "prognoza": _schema_prognoza,
}


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


def _nasadzenia_schema(
    configured_zones: list[int],
    merged: dict[str, Any],
    state_fn: Callable[[int], tuple[bool, list[str]]],
) -> dict:
    """Krok 'Dosiewka / nowe nasadzenie' - dla każdej JUŻ SKONFIGUROWANEJ
    strefy (ma przypisany zawór) dwa pola: przełącznik, którego domyślna
    wartość odzwierciedla REALNY stan strefy (włączony, jeśli dosiewka już
    trwa - patrz state_fn/_zone_growth_stage_state) i lista roślin do
    wyboru, ograniczona do roślin JUŻ przypisanych do tej strefy (tak samo
    jak _root_depth_override_options), wstępnie zaznaczona na te aktualnie
    wybrane w trwającej dosiewce, jeśli jakaś trwa."""
    schema: dict[Any, Any] = {}
    for i in configured_zones:
        plant_keys = merged.get(f"zone{i}_{ZONE_FIELD_PLANTS}") or []
        options = [
            selector.SelectOptionDict(value=key, label=PLANTS[key]["label"])
            for key in plant_keys
            if key in PLANTS
        ]
        active, selected_keys = state_fn(i)
        default_selected = [key for key in selected_keys if key in plant_keys]
        schema[vol.Optional(f"nasadzenie_zone{i}_start", default=active)] = selector.BooleanSelector()
        schema[vol.Optional(f"nasadzenie_zone{i}_rosliny", default=default_selected)] = selector.SelectSelector(
            selector.SelectSelectorConfig(options=options, mode="dropdown", multiple=True)
        )
    return schema


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
            prefix + ZONE_FIELD_GERMINATION_DEPTH_OVERRIDE_MM,
            default=defaults.get(prefix + ZONE_FIELD_GERMINATION_DEPTH_OVERRIDE_MM, ""),
        ): selector.TextSelector(),
        vol.Optional(
            prefix + ZONE_FIELD_YOUNG_DEPTH_OVERRIDE_MM,
            default=defaults.get(prefix + ZONE_FIELD_YOUNG_DEPTH_OVERRIDE_MM, ""),
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
        vol.Optional(
            prefix + ZONE_FIELD_FORCE_HEAT_ENABLED,
            default=defaults.get(prefix + ZONE_FIELD_FORCE_HEAT_ENABLED, DEFAULT_FORCE_HEAT_ENABLED),
        ): selector.BooleanSelector(),
        vol.Optional(
            prefix + ZONE_FIELD_FORCE_HEAT_DEFICIT_PCT,
            default=defaults.get(
                prefix + ZONE_FIELD_FORCE_HEAT_DEFICIT_PCT, DEFAULT_FORCE_HEAT_DEFICIT_PCT
            ),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=5, max=100, step=5, unit_of_measurement="%", mode="slider")
        ),
        vol.Optional(
            prefix + ZONE_FIELD_FORCE_HEAT_MIN_DAYS,
            default=defaults.get(prefix + ZONE_FIELD_FORCE_HEAT_MIN_DAYS, DEFAULT_FORCE_HEAT_MIN_DAYS),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=1, max=7, step=1, unit_of_measurement="dni", mode="slider")
        ),
    }


# ---------------------------------------------------------------------------
# Wspólna logika nawigacji (menu) - używana zarówno przy pierwszej instalacji
# (ConfigFlow), jak i przy edycji później (OptionsFlow). Patrz docstring na
# górze pliku - to jest nasz zamiennik nieistniejącego w HA przycisku
# "Wstecz": każda kategoria po zapisaniu wraca do tego samego menu, z
# którego można wybrać cokolwiek innego, w dowolnej kolejności, dowolną
# liczbę razy, aż do wybrania "Zakończ i zapisz".
# ---------------------------------------------------------------------------

MENU_STEP_IDS = [
    "tryb_start",
    "zawory_przeplyw",
    "stacja_pogody",
    "deszcz_pauza",
    "ochrona",
    "prognoza",
    "location",
    "zone_count",
    "zones_menu",
    "finish",
]


class _GardenFlowMixin:
    """Współdzielona logika menu/kategorii dla ConfigFlow i OptionsFlow.

    Klasa pochodna musi ustawić w __init__:
      self._data: dict - dane zebrane z odwiedzonych w TEJ sesji kroków
      self._base: dict - punkt wyjścia (pusty dla nowej instalacji, albo
                          {**entry.data, **entry.options} przy edycji)
    oraz zaimplementować:
      self._finish(merged: dict) -> FlowResult - tworzy/aktualizuje wpis
    """

    _data: dict[str, Any]
    _base: dict[str, Any]

    def _merged(self) -> dict[str, Any]:
        return {**self._base, **self._data}

    def _learned_rate(self, index: int) -> float | None:
        """Nadpisywane w OptionsFlow - podpowiada wyuczoną wydajność z
        przepływomierza, jeśli integracja już się czegoś nauczyła. Przy
        pierwszej instalacji (ConfigFlow) koordynator jeszcze nie istnieje,
        więc zawsze None."""
        return None

    def _finish(self, merged: dict[str, Any]):
        raise NotImplementedError

    def _menu_step_ids(self) -> list[str]:
        """Nadpisywane w OptionsFlow - dokłada krok 'nasadzenia', który ma
        sens TYLKO przy edycji istniejącego wpisu (potrzebuje działającego
        koordynatora, żeby cokolwiek uruchomić - przy pierwszej instalacji
        koordynator jeszcze nie istnieje)."""
        return MENU_STEP_IDS

    def _zone_growth_stage_state(self, zid: int) -> tuple[bool, list[str]]:
        """Nadpisywane w OptionsFlow - patrz tam. W ConfigFlow (pierwsza
        instalacja) koordynator jeszcze nie istnieje, więc żadna strefa nie
        może mieć trwającej dosiewki."""
        return False, []

    async def _async_apply_new_plantings(
        self, user_input: dict[str, Any], configured_zones: list[int]
    ) -> None:
        """Nadpisywane w OptionsFlow - patrz tam. W ConfigFlow (pierwsza
        instalacja) krok 'nasadzenia' nigdy nie jest pokazywany (nie ma go
        w _menu_step_ids), więc to nigdy nie powinno się wywołać - no-op
        tylko dla bezpieczeństwa."""
        return

    # --- menu główne -------------------------------------------------

    async def async_step_menu(self, user_input: dict[str, Any] | None = None):
        return self.async_show_menu(step_id="menu", menu_options=self._menu_step_ids())

    # --- 6 kategorii ---------------------------------------------------

    async def _async_category_step(self, category: str, user_input: dict[str, Any] | None):
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_menu()
        schema_fn = CATEGORY_SCHEMAS[category]
        return self.async_show_form(step_id=category, data_schema=schema_fn(self._merged()))

    async def async_step_tryb_start(self, user_input: dict[str, Any] | None = None):
        return await self._async_category_step("tryb_start", user_input)

    async def async_step_zawory_przeplyw(self, user_input: dict[str, Any] | None = None):
        return await self._async_category_step("zawory_przeplyw", user_input)

    async def async_step_stacja_pogody(self, user_input: dict[str, Any] | None = None):
        return await self._async_category_step("stacja_pogody", user_input)

    async def async_step_deszcz_pauza(self, user_input: dict[str, Any] | None = None):
        return await self._async_category_step("deszcz_pauza", user_input)

    async def async_step_ochrona(self, user_input: dict[str, Any] | None = None):
        return await self._async_category_step("ochrona", user_input)

    async def async_step_prognoza(self, user_input: dict[str, Any] | None = None):
        return await self._async_category_step("prognoza", user_input)

    # --- lokalizacja i liczba stref ------------------------------------

    async def async_step_location(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_menu()
        return self.async_show_form(
            step_id="location", data_schema=_location_schema(self._merged(), self.hass)
        )

    async def async_step_zone_count(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_menu()
        return self.async_show_form(
            step_id="zone_count", data_schema=_zone_count_schema(self._merged())
        )

    # --- strefy: podmenu + osobny ekran na każdą ------------------------

    async def async_step_zones_menu(self, user_input: dict[str, Any] | None = None):
        zone_count = int(self._merged().get(CONF_ZONE_COUNT, DEFAULT_ZONE_COUNT))
        zone_count = max(1, min(zone_count, MAX_ZONE_COUNT))
        options: dict[str, str] = {}
        merged = self._merged()
        for i in range(1, zone_count + 1):
            name = merged.get(f"zone{i}_{ZONE_FIELD_NAME}")
            options[f"zone_{i}"] = f"Strefa {i} ({name})" if name else f"Strefa {i}"
        options["menu"] = "« Wróć do menu głównego"
        return self.async_show_menu(step_id="zones_menu", menu_options=options)

    async def _async_zone_step(self, index: int, user_input: dict[str, Any] | None):
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_zones_menu()
        return self.async_show_form(
            step_id=f"zone_{index}",
            data_schema=vol.Schema(_zone_schema(index, self._merged(), self._learned_rate(index))),
        )

    # --- dosiewka / nowe nasadzenie (tylko OptionsFlow, patrz _menu_step_ids)

    def _configured_zone_ids(self) -> list[int]:
        merged = self._merged()
        zone_count = int(merged.get(CONF_ZONE_COUNT, DEFAULT_ZONE_COUNT))
        zone_count = max(1, min(zone_count, MAX_ZONE_COUNT))
        return [i for i in range(1, zone_count + 1) if merged.get(f"zone{i}_{ZONE_FIELD_SWITCH}")]

    async def async_step_nasadzenia(self, user_input: dict[str, Any] | None = None):
        configured_zones = self._configured_zone_ids()
        if user_input is not None:
            # celowo NIE self._data.update(user_input) - te pola odzwierciedlają
            # realny, bieżący stan dosiewki per strefa (patrz
            # _zone_growth_stage_state), nie trwałą konfigurację wpisu; zmiana
            # przełącznika startuje/anuluje dosiewkę w koordynatorze
            # (_async_apply_new_plantings), a jego wartość przy następnym
            # wejściu w ten krok znowu jest wyliczana na nowo ze stanu strefy
            await self._async_apply_new_plantings(user_input, configured_zones)
            return await self.async_step_menu()
        return self.async_show_form(
            step_id="nasadzenia",
            data_schema=vol.Schema(
                _nasadzenia_schema(configured_zones, self._merged(), self._zone_growth_stage_state)
            ),
        )

    # --- zakończenie -----------------------------------------------------

    async def async_step_finish(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self._finish(self._merged())
        return self.async_show_form(step_id="finish", data_schema=vol.Schema({}))


def _make_zone_step_method(index: int):
    async def _step(self, user_input: dict[str, Any] | None = None):
        return await self._async_zone_step(index, user_input)

    return _step


# doklejamy async_step_zone_1 .. async_step_zone_{MAX_ZONE_COUNT} do miksiny -
# HA wymaga osobnej, realnej metody na każdy step_id używany w menu, więc
# generujemy je programistycznie zamiast pisać 32 razy to samo ręcznie
for _i in range(1, MAX_ZONE_COUNT + 1):
    setattr(_GardenFlowMixin, f"async_step_zone_{_i}", _make_zone_step_method(_i))
del _i


class GardenIrrigationConfigFlow(_GardenFlowMixin, config_entries.ConfigFlow, domain=DOMAIN):
    """Kreator pierwszej instalacji - menu z kategoriami, w dowolnej kolejności,
    zakończone krokiem 'finish'."""

    VERSION = 2

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._base: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        # pierwszy krok kreatora MUSI się nazywać 'user' (wymóg HA) - od razu
        # przekazujemy sterowanie do wspólnego menu
        return await self.async_step_menu()

    def _finish(self, merged: dict[str, Any]):
        # nazwa wyświetlana na karcie integracji pochodzi z tłumaczonego
        # klucza "config.title" w strings.json/translations - to ten sam
        # mechanizm, z którego korzysta np. integracja Tapo (stąd widoczna
        # nazwa dostosowuje się do języka HA automatycznie)
        return self.async_create_entry(title="Garden - Smart Irrigation", data=merged)

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return GardenIrrigationOptionsFlow(config_entry)


class GardenIrrigationOptionsFlow(_GardenFlowMixin, config_entries.OptionsFlow):
    """Edycja po instalacji - to samo menu co przy instalacji, wystartowane
    z aktualnymi wartościami jako punktem wyjścia."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry
        self._base: dict[str, Any] = {**config_entry.data, **config_entry.options}
        self._data: dict[str, Any] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        # pierwszy krok Opcji MUSI się nazywać 'init' (wymóg HA) - od razu
        # przekazujemy sterowanie do wspólnego menu
        return await self.async_step_menu()

    def _learned_rate(self, index: int) -> float | None:
        coordinator = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id)
        if coordinator is None:
            return None
        zstate = coordinator.data.get("zones", {}).get(str(index))
        if not zstate:
            return None
        return zstate.get("learned_rate_mmh")

    def _menu_step_ids(self) -> list[str]:
        ids = list(MENU_STEP_IDS)
        ids.insert(ids.index("finish"), "nasadzenia")
        return ids

    def _zone_growth_stage_state(self, zid: int) -> tuple[bool, list[str]]:
        coordinator = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id)
        if coordinator is None:
            return False, []
        zstate = coordinator.data.get("zones", {}).get(str(zid))
        if not zstate:
            return False, []
        active = bool(zstate.get("growth_stage"))
        selected_keys = zstate.get("growth_stage_selected_keys") or []
        return active, list(selected_keys)

    async def _async_apply_new_plantings(
        self, user_input: dict[str, Any], configured_zones: list[int]
    ) -> None:
        coordinator = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id)
        if coordinator is None:
            return
        for i in configured_zones:
            was_active, _ = self._zone_growth_stage_state(i)
            now_on = bool(user_input.get(f"nasadzenie_zone{i}_start"))
            if now_on and not was_active:
                plant_keys = user_input.get(f"nasadzenie_zone{i}_rosliny") or []
                if not plant_keys:
                    continue
                await coordinator.async_start_new_planting(i, list(plant_keys))
            elif was_active and not now_on:
                await coordinator.async_cancel_new_planting(i)

    def _finish(self, merged: dict[str, Any]):
        return self.async_create_entry(title="", data=merged)
