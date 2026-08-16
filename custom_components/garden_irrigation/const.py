"""Stałe dla integracji Garden Irrigation."""
from __future__ import annotations

DOMAIN = "garden_irrigation"

# --- konfiguracja globalna (pogoda) ---
CONF_TEMP_SENSOR = "temp_sensor"
CONF_SOLAR_SENSOR = "solar_sensor"          # W/m^2
CONF_WIND_SENSOR = "wind_sensor"            # m/s
CONF_HUMIDITY_SENSOR = "humidity_sensor"    # %
CONF_RAIN_SENSOR = "rain_sensor"            # mm, suma dobowa (rain_daily / dzisiejszy opad)
CONF_RAIN_FORECAST_SENSOR = "rain_forecast_sensor"  # mm, prognoza opadu (np. najbliższe 12h)
CONF_RAIN_SKIP_THRESHOLD_MM = "rain_skip_threshold_mm"  # próg, powyżej którego CAŁKOWICIE pomijamy podlewanie
CONF_RAIN_FORECAST_LOOKBACK_MIN = "rain_forecast_lookback_min"  # ile minut wstecz pamiętać MAKSYMALNĄ odczytaną prognozę (łapanie krótkotrwałych, ulotnych skoków prognozy między kolejnymi sprawdzeniami)
CONF_RAIN_PAUSE_THRESHOLD_MM = "rain_pause_threshold_mm"  # ile mm w trakcie podlewania wywołuje pauzę
CONF_RAIN_PAUSE_CHECK_INTERVAL_MIN = "rain_pause_check_interval_min"  # co ile sprawdzać podczas pracy/pauzy
CONF_RAIN_PAUSE_MAX_WAIT_MIN = "rain_pause_max_wait_min"  # po jakim czasie przestajemy czekać na potwierdzenie ciszy i wznawiamy mimo to (z pomniejszonym celem) - NIE anulujemy z powodu samego czasu, tylko z powodu pokrycia zapotrzebowania przez deszcz
CONF_RAIN_STOP_CONFIRMATION_MIN = "rain_stop_confirmation_min"  # ile MINUT NIEPRZERWANEGO braku opadu wymagane, zanim uznamy deszcz za zakończony i wznowimy (nie pierwsze czyste sprawdzenie)
CONF_AUTO_MODE_ENABLED = "auto_mode_enabled"
CONF_AUTO_TRIGGER_BUFFER_MIN = "auto_trigger_buffer_min"
CONF_RAIN_DETECTED_SENSOR = "rain_detected_sensor"  # binary_sensor LUB sensor (mm/h) - szybki detektor "czy pada TERAZ", opcjonalny
CONF_RAIN_RATE_THRESHOLD_MMH = "rain_rate_threshold_mmh"  # próg intensywności (mm/h) dla numerycznego czujnika deszczu
CONF_WEATHER_ENTITY = "weather_entity"  # weather.* - integracja sama pobiera prognozę, zamiast szablonu
CONF_WEATHER_FORECAST_INTERVAL_MIN = "weather_forecast_interval_min"  # jak rzadko odpytywać usługę pogodową (niezależnie od reszty)
CONF_WEATHER_FORECAST_HOURS = "weather_forecast_hours"  # ile najbliższych godzin prognozy sumować
CONF_PRESSURE_SENSOR = "pressure_sensor"  # opcjonalnie: realny pomiar ciśnienia zamiast wzoru ze wysokości
CONF_GARDEN_LOCATION = "garden_location"  # lokalizacja ogrodu (mapa, promień=0) - opcjonalna korekta względem domu
CONF_ZONE_TRANSITION_DELAY_SEC = "zone_transition_delay_sec"  # przerwa między zamknięciem jednej strefy a otwarciem kolejnej
CONF_VALVE_VERIFY_TIMEOUT_SEC = "valve_verify_timeout_sec"  # ile czekać na potwierdzenie otwarcia/zamknięcia zaworu
CONF_START_MODE = "start_mode"
CONF_START_OFFSET_MIN = "start_offset_min"
CONF_START_CLOCK_TIME = "start_clock_time"  # stała godzina - punkt odniesienia dla trybów "_at_clock"

START_MODE_FINISH_AT_SUNRISE = "finish_at_sunrise"  # start wyliczony wstecz, żeby OSTATNIA strefa skończyła o wschodzie
START_MODE_AT_SUNRISE = "at_sunrise"                # start dokładnie o wschodzie
START_MODE_BEFORE_SUNRISE = "before_sunrise"        # start X minut PRZED wschodem (stały offset)
START_MODE_AFTER_SUNRISE = "after_sunrise"          # start X minut PO wschodzie (stały offset)
START_MODE_FINISH_AT_CLOCK = "finish_at_clock"      # start wyliczony wstecz, żeby OSTATNIA strefa skończyła o wskazanej godzinie
START_MODE_AT_CLOCK = "at_clock"                    # start dokładnie o wskazanej godzinie
START_MODES = [
    START_MODE_FINISH_AT_SUNRISE,
    START_MODE_AT_SUNRISE,
    START_MODE_BEFORE_SUNRISE,
    START_MODE_AFTER_SUNRISE,
    START_MODE_FINISH_AT_CLOCK,
    START_MODE_AT_CLOCK,
]
DEFAULT_START_MODE = START_MODE_FINISH_AT_SUNRISE
DEFAULT_START_CLOCK_TIME = "06:00:00"
DEFAULT_START_OFFSET_MIN = 30
CONF_MAIN_FLOW_SENSOR = "main_flow_sensor"  # główny przepływomierz - suma litrów (skumulowany), domyślny dla stref bez własnego
CONF_MAIN_FLOW_RATE_SENSOR = "main_flow_rate_sensor"  # główny przepływomierz - przepływ CHWILOWY (np. l/min), domyślny dla stref bez własnego
CONF_FLOW_RATE_ZERO_THRESHOLD = "flow_rate_zero_threshold"  # poniżej tej wartości uznajemy, że przepływu nie ma
CONF_WIND_SKIP_THRESHOLD_MS = "wind_skip_threshold_ms"  # powyżej tej prędkości wiatru pomijamy strefy wrażliwe (zraszacze)
CONF_FROST_THRESHOLD_C = "frost_threshold_c"  # poniżej tej temperatury pomijamy CAŁE podlewanie (ryzyko przymrozku)
CONF_HEAT_ET0_THRESHOLD_MM = "heat_et0_threshold_mm"  # prognozowane ET0 (mm/dobę) od którego dzień kwalifikuje się jako "upał" na potrzeby wymuszonego podlewania
CONF_RAIN_PRIORITY_OVER_HEAT = "rain_priority_over_heat"  # jeśli prognoza opadu wstrzymuje podlewanie, to ma pierwszeństwo nad wymuszeniem przed upałem
CONF_DYNAMIC_MAD_ENABLED = "dynamic_mad_enabled"  # koryguj próg MAD codziennie wg wzoru FAO-56 (p = p_tabela + 0,04*(5-ETc))
CONF_UPDATE_INTERVAL = "update_interval_minutes"
CONF_ZONE_COUNT = "zone_count"

DEFAULT_UPDATE_INTERVAL = 10  # minut
DEFAULT_RAIN_SKIP_THRESHOLD_MM = 1.5
DEFAULT_RAIN_FORECAST_LOOKBACK_MIN = 180  # 3h - wystarcza, by złapać krótkotrwały skok prognozy (np. nadciągającą komórkę burzową), nawet jeśli sama prognoza zdąży się cofnąć zanim wypadnie kolejne "oficjalne" sprawdzenie
DEFAULT_ZONE_COUNT = 8
MAX_ZONE_COUNT = 32  # rozsądny górny limit dla formularza konfiguracji
DEFAULT_RAIN_PAUSE_THRESHOLD_MM = 0.3
DEFAULT_RAIN_PAUSE_CHECK_INTERVAL_MIN = 2
DEFAULT_RAIN_PAUSE_MAX_WAIT_MIN = 30
DEFAULT_RAIN_STOP_CONFIRMATION_MIN = 15
DEFAULT_AUTO_TRIGGER_BUFFER_MIN = 10
DEFAULT_WEATHER_FORECAST_INTERVAL_MIN = 60
DEFAULT_WEATHER_FORECAST_HOURS = 6
DEFAULT_ZONE_TRANSITION_DELAY_SEC = 5
DEFAULT_VALVE_VERIFY_TIMEOUT_SEC = 15
DEFAULT_FLOW_RATE_ZERO_THRESHOLD = 0.1
DEFAULT_WIND_SKIP_THRESHOLD_MS = 8.0
DEFAULT_RAIN_RATE_THRESHOLD_MMH = 0.2
DEFAULT_FROST_THRESHOLD_C = 2.0
DEFAULT_HEAT_ET0_THRESHOLD_MM = 6.0  # "upał" wg wspólnie ustalonej klasyfikacji (5-6 wysoki, >6-7 upał, >7 ekstremalny)
DEFAULT_RAIN_PRIORITY_OVER_HEAT = True
DEFAULT_DYNAMIC_MAD_ENABLED = True

# --- pola konfiguracyjne pojedynczej strefy (klucze budowane jako zoneN_xxx) ---
ZONE_FIELD_NAME = "name"
ZONE_FIELD_SWITCH = "switch_entity"
ZONE_FIELD_FLOW = "flow_sensor"
ZONE_FIELD_FLOW_RATE = "flow_rate_sensor"
ZONE_FIELD_SOIL = "soil_type"
ZONE_FIELD_PLANTS = "plants"
ZONE_FIELD_AREA = "area_m2"
ZONE_FIELD_RATE = "application_rate_mmh"
ZONE_FIELD_MAX_RUNTIME = "max_runtime_min"
ZONE_FIELD_TIMER = "timer_entity"
ZONE_FIELD_KC_OVERRIDE = "kc_override"
ZONE_FIELD_MAD_OVERRIDE = "mad_override"
# ręczna korekta depth_mm etapu wzrostu (kiełkowanie/młode) TEJ KONKRETNEJ strefy,
# niezależna od katalogu roślin (patrz PLANTS[...]["growth_stages"] niżej) - puste
# = użyj wartości katalogowej rośliny wiodącej (patrz coordinator._build_zone_config)
ZONE_FIELD_GERMINATION_DEPTH_OVERRIDE_MM = "germination_depth_override_mm"
ZONE_FIELD_YOUNG_DEPTH_OVERRIDE_MM = "young_depth_override_mm"
ZONE_FIELD_ROOT_DEPTH_OVERRIDE_PLANT = "root_depth_override_plant"  # wybór z listy roślin już dodanych do strefy
ZONE_FIELD_MIN_DAYS_BETWEEN = "min_days_between_watering"
ZONE_FIELD_WIND_SENSITIVE = "wind_sensitive"
ZONE_FIELD_FORCE_HEAT_ENABLED = "force_heat_enabled"
ZONE_FIELD_FORCE_HEAT_DEFICIT_PCT = "force_heat_deficit_pct"
ZONE_FIELD_FORCE_HEAT_MIN_DAYS = "force_heat_min_days"
DEFAULT_FORCE_HEAT_ENABLED = False
DEFAULT_FORCE_HEAT_DEFICIT_PCT = 50
DEFAULT_FORCE_HEAT_MIN_DAYS = 3
ZONE_FIELD_IRRIGATION_TYPE = "irrigation_type"
ZONE_FIELD_DRIP_LINE_LENGTH_M = "drip_line_length_m"
ZONE_FIELD_DRIP_SPACING_CM = "drip_spacing_cm"
ZONE_FIELD_DRIP_EMITTER_LPH = "drip_emitter_lph"
ZONE_FIELD_DRIP_COUNT = "drip_count"
ZONE_FIELD_LEARN_RATE_FROM_FLOW = "learn_rate_from_flow"  # czy uczyć się wydajności z pomiaru wodomierza
ZONE_FIELD_AUTO_CALC_RATE = "auto_calc_rate"  # czy pole "Wydajność" ma być automatycznie przeliczane z typu nawadniania przy każdym wejściu w konfigurację
ZONE_FIELD_ADJUST_RUNTIME_FROM_FLOW = "adjust_runtime_from_flow"  # czy dostosowywać czas podlewania na żywo do pomiaru z przepływomierza (i odpowiednio - watchdog na cały limit strefy zamiast wyliczonego czasu)
DEFAULT_ADJUST_RUNTIME_FROM_FLOW = True

# --- typy nawadniania per strefa ---
IRRIGATION_TYPE_SPRINKLER = "zraszacze"
IRRIGATION_TYPE_MICRO_SPRINKLER = "mikrozraszacze"
IRRIGATION_TYPE_DRIP_LINE = "linia_kroplujaca"
IRRIGATION_TYPE_DRIP_POINTS = "pojedyncze_kroplowniki"

IRRIGATION_TYPES = {
    IRRIGATION_TYPE_SPRINKLER: {"label": "Zraszacze", "default_rate_mmh": 12.0},
    IRRIGATION_TYPE_MICRO_SPRINKLER: {"label": "Mikrozraszacze", "default_rate_mmh": 6.0},
    IRRIGATION_TYPE_DRIP_LINE: {"label": "Linia kroplująca", "default_rate_mmh": None},
    IRRIGATION_TYPE_DRIP_POINTS: {"label": "Pojedyncze kroplowniki", "default_rate_mmh": None},
}

# umowna szerokość zwilżanego pasa wokół linii kroplującej (m) - upraszczające
# założenie: linia prowadzona tuż obok roślin, więc powierzchnia strefy dla
# tego typu nie jest używana - efektywna powierzchnia liczona z samej linii
DRIP_LINE_WETTED_STRIP_WIDTH_M = 0.4

DEFAULT_IRRIGATION_TYPE = IRRIGATION_TYPE_SPRINKLER
DEFAULT_LEARN_RATE_FROM_FLOW = True
DEFAULT_AUTO_CALC_RATE = True

# --- gleby: dostępna woda glebowa (AWC, mm wody na metr głębokości korzeni) ---
# wartości orientacyjne wg FAO-56 (Allen i in.), środek typowego zakresu dla danej klasy tekstury
SOIL_TYPES = {
    "piasek": {"label": "Piasek", "awc_mm_per_m": 80},
    "piasek_gliniasty": {"label": "Piasek gliniasty", "awc_mm_per_m": 120},
    "glina_piaszczysta": {"label": "Glina piaszczysta (lekka)", "awc_mm_per_m": 130},
    "glina": {"label": "Glina (średnia, uniwersalna)", "awc_mm_per_m": 155},
    "pyl_gliniasty": {"label": "Pył gliniasty (ciężka, zwięzła)", "awc_mm_per_m": 180},
    "il": {"label": "Ił / glina ciężka", "awc_mm_per_m": 185},
    "substrat_donicowy": {"label": "Substrat donicowy / ziemia uniwersalna", "awc_mm_per_m": 100},
}
DEFAULT_SOIL = "glina"

# --- stadia wzrostu (dosiewka / nowe nasadzenie): każda roślina definiuje
#     WŁASNY harmonogram dwóch stadiów pośrednich, zanim strefa wróci do
#     standardowego (opartego na deficycie SMD) podlewania:
#     - "kielkowanie" - okres tuż po wysianiu/posadzeniu, podlewanie najczęstsze
#     - "mlode" - młoda roślina/trawnik, podlewanie rzadsze niż kiełkowanie,
#       ale nadal częstsze niż docelowe
#     duration_days - ile dni trwa dane stadium
#     frequency_per_day - ile razy dziennie podlewać w tym stadium
#     depth_mm - STAŁA, fizyczna ilość wody tego (płytkiego) podlewania,
#       NIEZALEŻNA od konkretnej strefy (mm głębokości = litry na m²).
#       Czas trwania zaworu potrzebny do dostarczenia tej ilości jest
#       wyliczany OSOBNO dla każdej strefy z jej bieżącej, samo-wyuczonej
#       wydajności (_effective_rate_mmh - uwzględnia rodzaj nawodnienia:
#       zraszacze/mikrozraszacze/kroplowanie) i powierzchni (area_m2). Jeśli
#       strefa ma przepływomierz, zawór zamyka się dokładnie po dostarczeniu
#       depth_mm (jako litry = depth_mm x powierzchnia) - NIE po czasie
#       (patrz _async_process_growth_stages / _async_run_zone_monitored).
#       Wartości domyślne poniżej przeliczone z poprzedniej wersji tabeli
#       (podanej w minutach) przy referencyjnej wydajności 12 mm/h (domyślna
#       dla zraszaczy - IRRIGATION_TYPE_SPRINKLER) - to tylko punkt startowy,
#       edytowalny wg realnych potrzeb konkretnych roślin.
GROWTH_STAGE_GERMINATION = "kielkowanie"
GROWTH_STAGE_YOUNG = "mlode"
GROWTH_STAGES_ORDER = [GROWTH_STAGE_GERMINATION, GROWTH_STAGE_YOUNG]
GROWTH_STAGE_LABELS = {
    GROWTH_STAGE_GERMINATION: "Kiełkowanie",
    GROWTH_STAGE_YOUNG: "Młode rośliny",
}

# --- rośliny: kc (współczynnik roślinny), głębokość korzeni (mm), MAD (frakcja
#     dostępnej wody, jaką można zużyć zanim uruchomimy podlewanie - niższa
#     wartość = roślina bardziej wrażliwa na przesuszenie, podlewana częściej) ---
PLANTS = {
    "trawnik": {
        "label": "Trawnik ozdobny", "kc": 0.80, "root_depth_mm": 150, "mad": 0.40,
        "growth_stages": {
            GROWTH_STAGE_GERMINATION: {"duration_days": 14, "frequency_per_day": 2, "depth_mm": 1},
            GROWTH_STAGE_YOUNG: {"duration_days": 21, "frequency_per_day": 1, "depth_mm": 1.6},
        },
    },
    "warzywa_liste": {
        "label": "Warzywa liściaste (sałata, kapusta...)", "kc": 1.00, "root_depth_mm": 300, "mad": 0.50,
        "growth_stages": {
            GROWTH_STAGE_GERMINATION: {"duration_days": 10, "frequency_per_day": 2, "depth_mm": 1},
            GROWTH_STAGE_YOUNG: {"duration_days": 21, "frequency_per_day": 1, "depth_mm": 2},
        },
    },
    "warzywa_korzeniowe": {
        "label": "Warzywa korzeniowe (marchew, ziemniaki...)", "kc": 0.90, "root_depth_mm": 350, "mad": 0.50,
        "growth_stages": {
            GROWTH_STAGE_GERMINATION: {"duration_days": 14, "frequency_per_day": 2, "depth_mm": 1},
            GROWTH_STAGE_YOUNG: {"duration_days": 21, "frequency_per_day": 1, "depth_mm": 2},
        },
    },
    "truskawki": {
        "label": "Truskawki / poziomki", "kc": 0.85, "root_depth_mm": 200, "mad": 0.40,
        "growth_stages": {
            GROWTH_STAGE_GERMINATION: {"duration_days": 10, "frequency_per_day": 2, "depth_mm": 1},
            GROWTH_STAGE_YOUNG: {"duration_days": 21, "frequency_per_day": 1, "depth_mm": 1.6},
        },
    },
    "roze": {
        "label": "Róże", "kc": 0.60, "root_depth_mm": 400, "mad": 0.50,
        "growth_stages": {
            GROWTH_STAGE_GERMINATION: {"duration_days": 14, "frequency_per_day": 1, "depth_mm": 1.6},
            GROWTH_STAGE_YOUNG: {"duration_days": 30, "frequency_per_day": 1, "depth_mm": 2},
        },
    },
    "byliny_ogolne": {
        "label": "Byliny ogrodowe (ogólnie)", "kc": 0.70, "root_depth_mm": 300, "mad": 0.45,
        "growth_stages": {
            GROWTH_STAGE_GERMINATION: {"duration_days": 10, "frequency_per_day": 1, "depth_mm": 1.2},
            GROWTH_STAGE_YOUNG: {"duration_days": 21, "frequency_per_day": 1, "depth_mm": 2},
        },
    },
    "hortensje": {
        "label": "Hortensje", "kc": 0.80, "root_depth_mm": 300, "mad": 0.35,
        "growth_stages": {
            GROWTH_STAGE_GERMINATION: {"duration_days": 14, "frequency_per_day": 1, "depth_mm": 1.6},
            GROWTH_STAGE_YOUNG: {"duration_days": 30, "frequency_per_day": 1, "depth_mm": 2},
        },
    },
    "funkie": {
        "label": "Funkie / hosty", "kc": 0.70, "root_depth_mm": 250, "mad": 0.40,
        "growth_stages": {
            GROWTH_STAGE_GERMINATION: {"duration_days": 10, "frequency_per_day": 1, "depth_mm": 1.2},
            GROWTH_STAGE_YOUNG: {"duration_days": 21, "frequency_per_day": 1, "depth_mm": 1.6},
        },
    },
    "trawy_ozdobne": {
        "label": "Wysokie trawy ozdobne", "kc": 0.55, "root_depth_mm": 400, "mad": 0.55,
        "growth_stages": {
            GROWTH_STAGE_GERMINATION: {"duration_days": 14, "frequency_per_day": 1, "depth_mm": 1.2},
            GROWTH_STAGE_YOUNG: {"duration_days": 21, "frequency_per_day": 1, "depth_mm": 2},
        },
    },
    "krzewy_liesciaste": {
        "label": "Krzewy liściaste ozdobne (ogólnie)", "kc": 0.55, "root_depth_mm": 400, "mad": 0.50,
        "growth_stages": {
            GROWTH_STAGE_GERMINATION: {"duration_days": 14, "frequency_per_day": 1, "depth_mm": 1.6},
            GROWTH_STAGE_YOUNG: {"duration_days": 30, "frequency_per_day": 1, "depth_mm": 2},
        },
    },
    "zywoplot_liesciasty": {
        "label": "Żywopłot liściasty formowany", "kc": 0.60, "root_depth_mm": 400, "mad": 0.45,
        "growth_stages": {
            GROWTH_STAGE_GERMINATION: {"duration_days": 14, "frequency_per_day": 1, "depth_mm": 1.6},
            GROWTH_STAGE_YOUNG: {"duration_days": 30, "frequency_per_day": 1, "depth_mm": 2},
        },
    },
    "zywoplot_iglasty": {
        "label": "Żywopłot / krzewy iglaste (tuje, cyprysiki)", "kc": 0.45, "root_depth_mm": 450, "mad": 0.55,
        "growth_stages": {
            GROWTH_STAGE_GERMINATION: {"duration_days": 14, "frequency_per_day": 1, "depth_mm": 1.6},
            GROWTH_STAGE_YOUNG: {"duration_days": 35, "frequency_per_day": 1, "depth_mm": 2},
        },
    },
    "iglaki_duze": {
        "label": "Duże iglaki (jodły, sosny, świerki)", "kc": 0.40, "root_depth_mm": 600, "mad": 0.60,
        "growth_stages": {
            GROWTH_STAGE_GERMINATION: {"duration_days": 14, "frequency_per_day": 1, "depth_mm": 2},
            GROWTH_STAGE_YOUNG: {"duration_days": 45, "frequency_per_day": 1, "depth_mm": 3},
        },
    },
    "cisy": {
        "label": "Cisy", "kc": 0.45, "root_depth_mm": 450, "mad": 0.55,
        "growth_stages": {
            GROWTH_STAGE_GERMINATION: {"duration_days": 14, "frequency_per_day": 1, "depth_mm": 1.6},
            GROWTH_STAGE_YOUNG: {"duration_days": 35, "frequency_per_day": 1, "depth_mm": 2},
        },
    },
    "plozence_iglaste": {
        "label": "Płożące iglaki (jałowce płożące itp.)", "kc": 0.40, "root_depth_mm": 300, "mad": 0.55,
        "growth_stages": {
            GROWTH_STAGE_GERMINATION: {"duration_days": 14, "frequency_per_day": 1, "depth_mm": 1.6},
            GROWTH_STAGE_YOUNG: {"duration_days": 30, "frequency_per_day": 1, "depth_mm": 2},
        },
    },
    "drzewa_liesciaste": {
        "label": "Drzewa liściaste dojrzałe", "kc": 0.50, "root_depth_mm": 700, "mad": 0.60,
        "growth_stages": {
            GROWTH_STAGE_GERMINATION: {"duration_days": 14, "frequency_per_day": 1, "depth_mm": 2},
            GROWTH_STAGE_YOUNG: {"duration_days": 45, "frequency_per_day": 1, "depth_mm": 3},
        },
    },
    "drzewa_owocowe": {
        "label": "Drzewa owocowe", "kc": 0.65, "root_depth_mm": 600, "mad": 0.50,
        "growth_stages": {
            GROWTH_STAGE_GERMINATION: {"duration_days": 14, "frequency_per_day": 1, "depth_mm": 2},
            GROWTH_STAGE_YOUNG: {"duration_days": 45, "frequency_per_day": 1, "depth_mm": 3},
        },
    },
    "donice": {
        "label": "Rośliny w donicach / pojemnikach (ogólnie)", "kc": 0.90, "root_depth_mm": 200, "mad": 0.30,
        "growth_stages": {
            GROWTH_STAGE_GERMINATION: {"duration_days": 7, "frequency_per_day": 2, "depth_mm": 0.6},
            GROWTH_STAGE_YOUNG: {"duration_days": 14, "frequency_per_day": 1, "depth_mm": 1},
        },
    },
}
DEFAULT_PLANT = "trawnik"

ZONE_STATUS_IDLE = "idle"
ZONE_STATUS_PENDING = "pending"
ZONE_STATUS_APPROVED = "approved"
ZONE_STATUS_RUNNING = "running"
ZONE_STATUS_PAUSED_RAIN = "paused_rain"
ZONE_STATUS_DONE = "done"
ZONE_STATUS_DISABLED = "disabled"

STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = f"{DOMAIN}_data"

SERVICE_APPROVE_ZONE = "approve_zone"
SERVICE_APPROVE_ALL = "approve_all"
SERVICE_SKIP_ZONE = "skip_zone"
SERVICE_RUN_ZONE = "run_zone"
SERVICE_RUN_SEQUENCE_BEFORE_SUNRISE = "run_sequence_before_sunrise"
SERVICE_START_NEW_PLANTING = "start_new_planting"
SERVICE_CANCEL_NEW_PLANTING = "cancel_new_planting"

ATTR_ZONE_ID = "zone_id"
ATTR_MINUTES = "minutes"
ATTR_PLANT_KEYS = "plant_keys"
