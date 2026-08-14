# Garden Irrigation

*[Polski / Polish version: README.md](README.md)*

[![Validate with hassfest](https://github.com/JarDol/garden_irrigation/actions/workflows/hassfest.yml/badge.svg)](https://github.com/JarDol/garden_irrigation/actions/workflows/hassfest.yml)
[![HACS Validation](https://github.com/JarDol/garden_irrigation/actions/workflows/hacs.yml/badge.svg)](https://github.com/JarDol/garden_irrigation/actions/workflows/hacs.yml)
[![GitHub release](https://img.shields.io/github/v/release/JarDol/garden_irrigation)](https://github.com/JarDol/garden_irrigation/releases)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

A custom Home Assistant integration for smart, multi-sensor garden irrigation. Instead of a
time-based schedule, the integration keeps a per-zone **soil water balance**: it calculates how
much water each plant loses through evapotranspiration (from real data provided by your weather
station), subtracts actually measured rainfall, and decides on its own when and for how long to
water - taking into account the soil, the selected plants, the rain forecast, and any rain
falling during the watering itself.

## What the integration does

- Calculates daily **ET0** (reference evapotranspiration) using the FAO-56 Penman-Monteith
  method, based on temperature, solar radiation, wind, and humidity from your weather station.
  When full data isn't available, it automatically falls back to the Hargreaves method.
- Maintains a balance for each zone: the **soil water deficit** grows by ETc (= ET0 × plant Kc)
  and shrinks by measured rainfall and by water actually delivered during watering.
- When the deficit exceeds a threshold that depends on the soil and the selected plants, the
  zone gets a "needs watering" status with a concrete recommendation in minutes.
- Can run **fully automatically** (no clicking anything) or **manually** (you decide when to
  approve) - selectable in the configuration.
- Opens valves **sequentially, one after another**, calculating the start time backwards from
  sunrise so that the last zone finishes watering roughly at sunrise.
- If it starts raining during watering - it **pauses** the valve, waits to see whether it's just
  a brief shower, and either resumes from where it left off or cancels the rest if the rain
  persists.
- Recognizes both `switch.*` and `valve.*` entities (e.g. Tuya controllers).
- Can set a hardware watchdog on the controller (a `number.*` timer entity) so the valve closes
  itself even if Home Assistant were to hang.
- Skips watering in strong wind (sprinkler zones) and in frost-risk conditions (the whole
  system), respects a minimum interval between waterings for a given zone (to encourage roots to
  grow deeper), and has a single switch for globally pausing everything (e.g. while on holiday).
- Corrects the MAD threshold every night using the official FAO-56 formula based on yesterday's
  water-use rate - in hot/dry conditions the threshold is automatically lower (and the minimum
  interval between waterings is skipped for that day), in cool weather it's higher.
- Tracks water-usage statistics (daily/monthly, per zone and total) and reports hardware problems
  (missing entity, unresponsive valve) through Home Assistant's built-in Repairs mechanism.
- Has a separate, more frequent watering mode for freshly seeded grass/new plantings (reseeding)
  - automatically returns to standard once the growth stages finish.
- Guarantees that no two valves are ever open at the same time (unless you deliberately allow
  it) - no matter what specifically triggered a given watering.

## Installation

1. Copy the `custom_components/garden_irrigation` folder into `config/custom_components/` on
   your Home Assistant instance.
2. Restart Home Assistant.
3. Settings → Devices & Services → Add Integration → search for
   **"Ogród - Inteligentne Nawadnianie"** (Garden Irrigation).
4. Go through the three wizard steps: weather → number of zones → zone details (described
   below).

The configuration can be changed at any later time: the integration's card → **Configure**. This
opens the exact same wizard, pre-filled with the current values - you only change what you want.

## Step 1: weather station and global settings

**All fields in this step are optional** - the integration can be set up with zero weather
sensors and have them added gradually. Without temperature (the one truly required sensor - even
the fallback ET0 method needs it), the water balance won't run, but the integration will tell you
about it via Settings → System → Repairs instead of silently doing nothing.

| Field | Meaning |
|---|---|
| Temperature | The temperature entity from your weather station |
| Solar radiation (W/m²) | Used for the Penman-Monteith ET0 calculation |
| Wind speed (m/s) | Used for ET0. **Automatically converts the unit** (km/h, mph, knots) to m/s based on the sensor's `unit_of_measurement` - most weather stations report wind in km/h, so you don't need to convert anything yourself |
| Relative humidity (%) | Used for ET0 |
| Rainfall - cumulative counter / total rain (mm) | **Must be a counter that never resets** (only ever increases) - NOT a typical "daily rainfall" value that resets at midnight. The integration checks it every update cycle and computes the difference from the previous reading, so it can reduce the water deficit continuously (not just once a day). If your station only offers a daily variant, you can add an HA `utility_meter` helper with no reset cycle to get a cumulative version |
| Weather service entity (`weather.*`) | Optional - the integration fetches the rain forecast itself via the `weather.get_forecasts` service, no need to build your own template |
| How many upcoming forecast hours to sum | Time horizon for summing the forecast rainfall (default 6h) |
| How often to poll the weather service | A separate, independent polling interval for the forecast (default 60 min) - the forecast doesn't need to be very fresh, and some weather services have rate limits |
| Rain forecast (mm) - legacy option | An alternative to the above: your own template/sensor with the forecast, used only if the `weather_entity` field is left empty |
| Rain threshold for SKIPPING watering entirely (mm) | If the forecast shows rainfall ≥ this threshold, the zone is skipped entirely for that day (not just given a smaller dose) |
| Start mode | See the "When exactly does watering start" section below |
| Offset in minutes | Only used for the "before/after sunrise" modes |
| Fixed start time | Only used for the "at the set time" modes |
| Fast "is it raining now" detector | Optional - a `binary_sensor` (dedicated rain sensor) OR a plain numeric `sensor` with rain intensity in mm/h (e.g. `sensor.your_weather_station_rain_rate`) - the integration recognizes the type from the entity's domain. For a numeric sensor, it compares the value against the "Rain intensity threshold (mm/h)". Speeds up detecting the start of rain during watering (see the pause section) |
| Rain threshold that triggers a pause DURING watering (mm) | How much rain (mm) must fall before the integration interrupts active watering (default 0.3 mm) |
| How often to check rainfall while running/paused | Check frequency during active watering and during a pause (default 2 min) |
| Max wait time for rain to stop | After this time the integration stops waiting for confirmation of quiet and resumes anyway (default 30 min) |
| Enable fully automatic watering | See the "Automatic mode" section below |
| Safety buffer for the trigger calculation (min) | See the "Automatic mode" section |
| Weather data polling frequency (min) | How often the REMAINING sensors are polled (temperature, wind, total rain, etc.) - default 10 min |
| Atmospheric pressure sensor | Optional - the list is filtered to entities with `device_class: pressure`. If you provide a real measurement, the integration uses it instead of the barometric formula computed from elevation. **Choose ABSOLUTE/station pressure** (for Ecowitt/WS stations usually `sensor.your_station_absolute_pressure`), **not "relative"** (relative pressure is sea-level-adjusted - not correct for the FAO-56 formula). **Note:** the device-class filter can NOT distinguish absolute/relative/VPD if all three share the same `device_class: pressure` (a common case with templates) - a deliberate choice by entity name matters, not the class. `sensor.*vapour_pressure_deficit` (VPD) is a completely different physical quantity and is not suitable as a pressure sensor despite sharing the same class/unit. Recognizes hPa/mbar/kPa/inHg/mmHg units - assumes hPa (the most common in HA) for an unrecognized unit |
| Delay between closing one zone and opening the next (s) | Default 5s - the integration waits this long after a confirmed valve closure before opening the next one in sequence |
| Valve open/close confirmation timeout (s) | Default 15s - how long the integration polls the valve entity's state before considering the command to have failed |
| Main flow meter - cumulative liters | Optional - if you have ONE shared meter for the whole system (typical with sequential watering, where only one zone runs at a time anyway), point it here. Zones without their own flow meter will use it automatically |
| Main flow meter - INSTANTANEOUS flow | Same, but for instantaneous measurement (e.g. L/min) - used for extra verification that the valve actually opened/closed (see "Sequential zone activation with verification") |
| No-flow threshold | Below this flow value, the integration considers there to be no water (valve actually closed) |
| Wind threshold above which... | Wind threshold (m/s) above which zones marked as wind-sensitive are skipped (typically sprinklers - drift/uneven coverage) |
| Temperature threshold below which... | Temperature threshold (°C) below which ALL watering is paused (frost risk - hoses, valves) |

## Step 2: garden location

Defaults to your home (from HA's general configuration) - drag the pin if the garden is
elsewhere. Used to calculate ET0 and sunrise.

## Step 3: number of zones

How many irrigation zones do you want to configure? In the next step you'll only fill in the
ones you actually use - leave the rest blank.

## Step 4: details for each zone

| Field | Meaning |
|---|---|
| Zone name | E.g. "Lawn", "Pots" - if left blank, defaults to "Zone N" |
| Valve / switch entity | `switch` or `valve` - blank = zone inactive |
| Flow meter | Optional, a more accurate measurement of water used |
| Soil type | Determines how much water the soil can retain (see the soil table below) |
| Plants | One or more from the list (see the plant table below) - determine Kc, root depth, and the drought-sensitivity threshold |
| Manual Kc calibration | Optional - a numeric value entirely replaces the Kc calculated from the selected plants. Blank = use the calculated value |
| Manual MAD calibration | Same, for the MAD threshold |
| Root depth from a selected plant | Optional - a dropdown built from plants **already saved** for this zone (sorted ascending by Kc, with Kc shown in the label), letting you deliberately replace the automatic maximum with one specific plant - useful when one deep-rooted plant in the mix (e.g. a single tree among shrubs/perennials) would artificially inflate the whole zone's capacity for the rest. **The list is empty on the first configuration of a zone** (the form cannot read plants being selected in the same step) - it appears only after saving and re-entering "Configure". Blank = automatic maximum (as before) |
| Area (m²) | For sprinklers - the whole zone area; for drip lines - the estimated **wetted strip along the line** (length × wetted-strip width), not the whole ground area |
| Irrigation type | Sprinklers / Micro-sprinklers / Drip line / Individual emitters - affects how the **default, suggested** value of the "Application rate" field below is calculated (see the "Irrigation type" section below) |
| Drip line length (m) | Only for the "Drip line" type - ignored for other types (visible in the form, but has no effect) |
| Emitter spacing (cm) | Only for "Drip line" - the distance between emitters along the line |
| Single emitter flow rate (L/h) | For "Drip line" OR "Individual emitters" - usually printed on the packaging |
| Number of emitters (units) | Only for "Individual emitters" - when you don't have a line, just individual emitters in the bed |
| Application rate (mm/h) | **Suggested automatically** based on the irrigation type and its parameters (see below) - a starting point, editable by hand, **self-corrected later** based on real flow-meter measurements, if enabled (see "Learn from flow meter" below). If you don't have a flow meter, this value stays fixed. **Allowed range: 0.5-500 mm/h** - that may look like a lot, but small zones (e.g. pots) with a decent flow can legitimately reach 200+ mm/h - it's just the math (L/h ÷ a small area), not a bug |
| Learn the application rate from the flow meter | Enabled by default (if the zone has a flow meter) - disable it if you want the application rate to ALWAYS stay exactly what you typed manually, even when the flow meter says otherwise |
| Maximum watering time (min) | A hard safety limit - the integration will never exceed this value, regardless of any calculation |
| Watchdog timer (`number.*`) | Optional - if the controller has a hardware per-zone timer, the integration writes the current, remaining time to it just before every valve opening (see "Hardware watchdog") |
| Minimum interval between waterings (days) | Default 0 (no limit). Even if the deficit crosses the threshold earlier, the zone won't be watered more often than every this many days - this encourages the root system to grow deeper for water instead of getting used to shallow, daily watering |
| Wind-sensitive zone | Check this for sprinklers (doesn't make much sense for drip) - the zone will be skipped in strong wind (global threshold) |

### How demand is calculated with several plants in one zone

When you select several plants with different needs in one zone (e.g. conifers + hydrangeas on
one drip line), the integration takes a **conservative** approach:
- **Kc** and **root depth** are taken from the most demanding of the selected plants (so none of
  them dries out) - **root depth can be deliberately overridden** by picking from the list (see
  "Root depth from a selected plant" above), if one deep-rooted plant in a small proportion is
  distorting the whole zone's capacity for the rest of the plants,
- the **MAD threshold** is taken from the most sensitive plant (the lowest threshold = watering
  kicks in earliest) - **this parameter deliberately has no equivalent manual dropdown selection**
  (only the numeric manual calibration above, if genuinely needed) - it's the one parameter that
  directly protects the most sensitive plant from drying out, so keeping it fully automatic
  minimizes the risk of accidentally picking too tolerant a value.

This may mean slightly overwatering the most drought-tolerant plants in the zone, in exchange for
certainty that the sensitive ones don't dry out. Which specific parameter was taken from which
plant is visible in the diagnostic sensors described below - if, after watching the garden, you
want to correct this, use the manual Kc/MAD calibration fields rather than changing the plant
selection.

### Soil types

| Soil | Available water (mm per meter of depth) |
|---|---|
| Sand | 80 |
| Loamy sand | 120 |
| Sandy loam (light) | 130 |
| Loam (medium, all-purpose) | 155 |
| Silt loam (heavy, dense) | 180 |
| Clay / heavy clay | 185 |
| Potting mix / general-purpose soil | 100 |

### Plants

| Plant | Kc | Root depth | MAD |
|---|---|---|---|
| Ornamental lawn | 0.80 | 150 mm | 0.40 |
| Leafy vegetables | 1.00 | 300 mm | 0.50 |
| Root vegetables | 0.90 | 350 mm | 0.50 |
| Strawberries / wild strawberries | 0.85 | 200 mm | 0.40 |
| Roses | 0.60 | 400 mm | 0.50 |
| Garden perennials (general) | 0.70 | 300 mm | 0.45 |
| Hydrangeas | 0.80 | 300 mm | 0.35 |
| Hostas | 0.70 | 250 mm | 0.40 |
| Tall ornamental grasses | 0.55 | 400 mm | 0.55 |
| Ornamental deciduous shrubs | 0.55 | 400 mm | 0.50 |
| Formal deciduous hedge | 0.60 | 400 mm | 0.45 |
| Coniferous hedge / shrubs | 0.45 | 450 mm | 0.55 |
| Large conifers (fir, pine, spruce) | 0.40 | 600 mm | 0.60 |
| Yews | 0.45 | 450 mm | 0.55 |
| Creeping conifers | 0.40 | 300 mm | 0.55 |
| Mature deciduous trees | 0.50 | 700 mm | 0.60 |
| Fruit trees | 0.65 | 600 mm | 0.50 |
| Potted plants (general) | 0.90 | 200 mm | 0.30 |

## Rain measurement (total rain)

The rainfall entity **must be a cumulative counter that never resets**. The integration checks
it on every update cycle (every 10 minutes by default) and computes the difference from the
previous reading - if more water has accumulated, it's immediately subtracted from every zone's
deficit. This means rain falling at, say, 2:00 AM is already accounted for before the integration
would start watering at 4:00 AM - there's no need to wait for the next midnight.

Additionally, right before every approval/start, the integration checks this counter freshly
again (it doesn't rely on a reading that could be several minutes old). If the counter resets
(e.g. the weather station restarts), the integration detects the drop and simply starts counting
the difference again from scratch, without a false "negative rainfall".

## Rain forecast and skipping watering entirely

Independent of measured rainfall, the integration also checks the forecast (from a `weather.*`
entity or your own template) and compares it against the `rain_skip_threshold_mm` threshold. If
the forecast shows more rain than this threshold, that zone is **skipped entirely** for the day -
the water deficit is remembered and will be caught up the next day if the rain doesn't
materialize. The forecast is checked at several points: during the nightly recalculation, when a
single zone is approved, and freshly right before the whole sequence starts.

Short-term forecasts can be very volatile (e.g. an approaching storm cell can briefly push the
forecast up to several dozen mm, only for the model to walk it back shortly after). So a
short-lived spike doesn't get missed just because it had already faded from the forecast by the
time the next check happened, the integration **doesn't rely only on the freshest reading** -
instead it keeps a history of forecast samples from the last `rain_forecast_lookback_min` minutes
(180 by default, i.e. 3h) and bases the skip decision on the **maximum within that window**. Both
values - the freshest reading and the window maximum - are exposed separately on
`sensor.garden_irrigation_weather_inputs` (attributes `prognoza_opadu_mm` and
`prognoza_max_w_oknie_mm`).

## Forced watering ahead of a heatwave

Optional per-zone feature (off by default) - a "preventive" soil top-up ahead of an
expected heatwave, instead of waiting for the deficit to reach the normal MAD threshold on
its own. Well-watered soil going into a heatwave buffers heat stress better.

Works in two stages, both reusing existing mechanisms instead of building a parallel system:

1. **Qualification (nightly recalculation, at midnight)** - a zone becomes a CANDIDATE if:
   "Force watering before heatwave" is enabled, it is NOT already normally qualified (the
   regular MAD threshold will cover it anyway), its current deficit is ≤ the configured %
   threshold (e.g. 50% - "there's still a buffer, worth topping up preventively"), and its
   last forced watering was longer ago than the configured minimum days between (a safeguard
   against forcing every night during a multi-day heatwave). This happens WITHOUT querying
   the weather - purely from the local deficit state.
2. **Confirmation (right before the sequence starts)** - at the exact same point the
   integration already checks the rain forecast "right before the sequence", it additionally
   computes today's forecast ET0 (from the HOURLY forecast, aggregated to today's calendar
   day - see below). If "Forecasted rain takes priority" is enabled (default: yes) and the
   rain forecast is already holding watering anyway, the forced watering is cancelled
   regardless of heat. Otherwise: if forecast ET0 ≥ the global threshold (mm/day, default
   6.0), all candidates are confirmed and topped up TO FULL (deficit zeroed out, not just to
   the MAD threshold) - otherwise they're rejected for the day.

The two-stage split is intentional: the sequence start schedule (counted back from sunrise)
needs to know the FULL, potential queue composition up front (hence qualifying at midnight) -
adding candidates right before the start would break the already-computed timing for the
other zones.

**Why hourly forecast, not daily, for ET0:** the "temperature" field in the DAILY forecast is
a genuine daily Tmax (verified - matches the hourly forecast), but the humidity/wind/cloud
fields in that same record can be a single snapshot from one, not necessarily representative
hour (e.g. noon), not a true daily average. So those three values are computed independently
as an average of the hourly samples falling on today's local date. Solar radiation isn't
directly available in either forecast - estimated from cloud cover against clear-sky
radiation (Rso), the same approach verified against real data.

`sensor.garden_irrigation_weather_inputs` shows: the ET0 threshold, the current candidate
list, and the full inputs of the last computed forecast ET0 (Tmax/Tmin/humidity/wind/cloud/
sample count). `sensor.garden_irrigation_zone_XX_recommended_watering` shows per zone
whether it's currently a candidate and whether today's watering was forced.

## Pause during watering

The integration watches the weather not just before starting, but **throughout the entire active
watering session**:

- Every `rain_pause_check_interval_min` minutes it checks whether it has started raining - first
  via a fast binary detector (if configured), otherwise via the total-rain difference.
- If so - it **immediately closes the valve**.
- During the pause the integration **sums up all the rain that has fallen** and compares it with
  that zone's target - **if the rain alone already covers the need**, watering is considered
  unnecessary (status: `deficit covered by rain during the pause`), regardless of whether it's
  still raining at that moment.
- If the rain has **not** yet covered the whole need, the integration waits for
  `rain_stop_confirmation_min` minutes of **uninterrupted** absence of rain before considering
  the rain to be over (not after the first clean check - rain often falls in waves rather than
  continuously; without this safeguard the valve would keep opening and closing with every gap
  between waves, needlessly wearing out the solenoid valve mechanically).
- **The integration never gives up on watering purely because of how long it's raining.** If
  waiting for confirmation of quiet exceeds `rain_pause_max_wait_min`, it simply stops waiting and
  **resumes anyway** - the only reason to abandon watering entirely is that the rain itself has
  already covered the need (see above).
- **After resuming, the target is recalculated** - reduced by exactly how many mm fell during
  THIS particular pause. Water already delivered from the mains during this session (before the
  pause) keeps being counted without interruption (volume-based control tracks this across the
  whole session, regardless of how many pauses occur) - **nothing starts over from scratch**,
  neither because of rain nor because of water already delivered before the pause.

## Sunrise calculated independently

The integration **does not rely on any external entity** (e.g. `sensor.sun_next_rising`) to
determine sunrise time - it calculates it itself, based on the garden's location and elevation
(see the ET0 section above), using the `astral` library (the same one the built-in Sun
integration in Home Assistant is based on). `astral` is a hard dependency of the built-in Sun
integration, so it's already present on your system - this integration doesn't declare it as its
own requirement (so that HA doesn't try to additionally install it from PyPI on startup, which
could fail e.g. if there's no internet access at that moment, and would crash the whole
integration with a "Requirements ... not found" error). If `astral` were somehow unavailable
anyway, the rest of the integration (water balance, manual watering) still works normally - only
the sunrise-dependent features (the sequence, automatic mode) turn themselves off, with a clear
message in the logs.

## When exactly does watering start

Zones are always started **one after another**, never in parallel (useful with limited water
pressure). Exactly when the first zone starts is determined by the "Start mode" field in the
configuration:

| Mode | How the start is calculated |
|---|---|
| Finish the last zone at sunrise (default) | `start = sunrise − total_minutes_of_all_zones` - so the last zone finishes roughly at sunrise. The total changes every day depending on how many zones actually need water |
| Start exactly at sunrise | `start = sunrise`, regardless of how long it takes |
| Start X minutes BEFORE sunrise | `start = sunrise − X` (fixed offset, set by the "Offset in minutes" field) |
| Start X minutes AFTER sunrise | `start = sunrise + X` (fixed offset) |
| Finish the last zone at the set time | same as above, but the reference point is a fixed time (the "Fixed start time" field) instead of sunrise - useful for a predictable time that doesn't drift with the season |
| Start exactly at the set time | `start = the set time`, regardless of how long it takes |

The "at the set time" modes intentionally have no "X minutes before/after" variant - with a fixed
time that would just be another fixed time, so you can set the difference directly in the time
field. Unlike sunrise, a fixed time doesn't depend on the `astral` library or the garden's
location - it works even if computing sunrise would fail for some reason.

If the calculated start would fall in the past (e.g. the total time is too large for a "finish at
..." mode), the sequence starts immediately, without waiting.

This can also be triggered manually: the "Schedule sequence before sunrise" button, or the
`garden_irrigation.run_sequence_before_sunrise` service.

## Fully automatic mode

Enabled by default (`auto_mode_enabled`). With no external automation at all, the integration
does the following every day:

1. Calculates the "wake up" moment as the reference point of the selected start mode (see above)
   minus a safety buffer. For the "finish at sunrise" mode, the reference point is deliberately
   an UPPER estimate (the sum of the MAXIMUM times of all zones) - the exact start is
   recalculated precisely in step 2 anyway.
2. At that moment, freshly recalculates the water balance and checks rainfall, the forecast,
   wind, and frost.
3. Starts the sequence with the exact start time calculated from the current data.

The trigger is automatically recalculated every night during the nightly recalculation (nothing
needs to be listened to externally - the integration calculates tomorrow's sunrise itself). To
disable automatic mode and go back to manual approval - uncheck `auto_mode_enabled` in the
configuration, or enable the global pause switch (see below). The manual approval buttons and
services always work, regardless of these settings.

**Catching up after an HA restart in the trigger window.** The integration's internal timer
(the `async_track_point_in_time` mechanism) **does not survive an HA restart** - that's normal,
no timer scheduled in a process's memory survives a restart. If a restart happens exactly within
the narrow window between the calculated "wake up" moment and the actual sunrise, the integration
**detects this** on startup (the scheduled time has already passed, but today's sequence hasn't
run yet and sunrise hasn't happened yet) and starts the sequence **right away, with a few
seconds' delay**, instead of silently waiting until tomorrow and losing a whole day's watering.
If, on the other hand, sunrise has already passed, or the sequence has already run today -
nothing further happens, it waits for the next sunrise as usual.

**Second layer of safety - a periodic safety net.** The above only protects against a restart in
the critical window - but what if the scheduled timer, for any OTHER reason, simply doesn't fire
(an unhandled exception, a brief HA hang), without any restart at all? To guard against that
scenario, on **every** main update cycle (roughly every 10 min) the integration checks: is
automatic mode enabled, has today's sequence not run yet, and is there no live scheduled timer -
if all three conditions are met, it re-invokes the same scheduling logic (with the same
catch-up mechanism described above). Deliberately, there is **no hard-coded time window** here
(e.g. "1:00-7:00") - the window in which the safety net can act follows **directly from your
configuration** (start mode, sunrise, buffer), so it automatically adapts to the season and your
settings, instead of being a guess on my part.

## Hardware watchdog

If your irrigation controller has a hardware per-zone timer (typically a `number.*` entity, where
the written value causes the controller itself to close the valve automatically, independent of
Home Assistant), point it out in the "Watchdog timer" field for that zone. The behavior depends
on a single switch: **"Automatically adjust the watering duration based on measured
consumption"** (enabled by default, requires a flow meter) - this one decision controls two
related things at once, not separately:

- **Enabled**: the watering duration can be extended/shortened live according to the flow meter
  (see "Volume-based control" above), and the watchdog is set to the **whole configured safety
  limit of the zone** (`max_runtime_min`, minus time already used in this session) - so the
  controller never physically cuts off the valve before the integration has had a chance to reach
  the volume target. Still protects against an HA hang - if HA stops responding, the controller
  will close the valve itself, at the latest once that limit elapses.
- **Disabled**: purely time-based, with no live extension/shortening (even if the zone has a flow
  meter - it's still used for measuring consumption and self-calibration, just not for adjusting
  this particular session's duration), and the watchdog is set exactly to the calculated/
  remaining time of this session - tighter protection, consistent with the fact that the
  integration never intends to water longer than that anyway.

**Important caveat with adjustment enabled:** the total time of the whole sequence may not finish
exactly at sunrise or at the scheduled start time, if the "start before sunrise" mode is selected
- delivering the correct amount of water takes priority over sticking to the schedule to the
minute.

## Where the data for the ET0 calculation comes from

Besides the data from your weather station, the FAO-56 Penman-Monteith method requires two
additional quantities: **atmospheric pressure** (for the psychrometric constant) and, indirectly,
**elevation above sea level** (because standard pressure depends on elevation). The integration
handles this as follows:

- **Pressure**: if you provide a pressure sensor in the configuration, a **real measurement** is
  used (more accurate, since it accounts for the current weather system, not just elevation). If
  you don't provide one - pressure is calculated with the standard FAO-56 barometric formula from
  elevation above sea level (still accurate enough for irrigation purposes).
- **Latitude**: from the selected garden location (Step 2 - the map), if set; otherwise directly
  from HA's general configuration. **Elevation** is always taken directly from HA's general
  configuration (Settings → System → General) - the map step doesn't cover it.

In practice, for most home gardens the difference between the home's location and the garden's
actual location is negligible. **The same location is also used to calculate sunrise
independently** (see the section below) - the integration doesn't need any additional entity for
that.

## Irrigation type

Four types per zone, each calculated differently:

- **Sprinklers** / **Micro-sprinklers** - no conceptual changes compared to the rest of the
  model: the whole zone area, application rate in mm/h directly. The type only changes the
  **suggested default value** of the application rate (sprinklers ~12 mm/h, micro-sprinklers
  ~6 mm/h) - a starting point for adjustment, not something enforced.

- **Drip line** - a different model: **the zone area is ignored**, only the line length matters.
  Assumed simplification: the line is run right next to the plants. From the length and spacing,
  the integration calculates the number of emitters, and from that and their flow rate - the
  total flow, and from the **effective area** (length × an assumed wetted-strip width of 40 cm) -
  the application rate in mm/h, so it can be tied into the common water-balance model (Kc/MAD/
  soil all operate purely in mm). That same effective area (not the "zone area" field) is also
  used to convert actually delivered liters into mm - so both sides of the calculation stay
  consistent.

- **Individual emitters** - for beds with a few individual emitters (typically pots/planters),
  with no line and no spacing: number of emitters × their flow rate, divided by the **zone area
  from the form** (used normally, just like for sprinklers).

**All four types only produce a SUGGESTED value** in the "Application rate" field - you can
always override it manually, and if the zone has a flow meter and learning is enabled, it will
still be corrected over time based on real measurements (see below).

**The "Automatically calculate the application rate from the irrigation type" field** (enabled by
default) applies **ONLY to this form** - what shows up as the suggestion in the "Application
rate" field below when you open the configuration. It does **not control** the actual rate used
for watering, nor the value shown on the zone's sensor (`sensor.<zone>_application_rate`) in Home
Assistant - that depends solely on what you actually save in the "Application rate" field, and on
the "Learn from flow meter" switch (see below), independent of this field. It applies to **all
four types** (sprinklers/micro-sprinklers get a table value, drip line/individual emitters get a
value calculated from their parameters). If you want to be sure your manually entered value is
**never** overwritten the next time you visit "Configure" (e.g. because you know the real
pressure in your setup differs from the nominal table value) - turn this field off. The value in
the "Application rate" field will then stay exactly what you last saved - in this form.

**Priority over the static formula: the self-learned value from the flow meter.** If the
integration has already learned something from real measurements (see "Self-calibration" below),
the form's suggestion shows the **learned** value instead of the generic table/formula value -
more trustworthy, since it's based on actual water usage in your garden, not on nominal packaging
data. **The calibration itself is never lost when you re-enter the configuration** - regardless
of what you save in the "Application rate" field, actual watering keeps using the learned value
(as long as "Learn from flow meter" stays enabled) - this mechanism lives in a separate,
persistent data store of the integration, not in the zone's configuration itself.

**Note - these two switches are INDEPENDENT of each other; one does not "disable" the other.**
Turning off "Automatically calculate" only protects what you see in this form - it has no effect
on "Learn from flow meter". If you want **complete, absolute certainty** that your manually
entered value governs actual watering, and the integration will never replace it with a learned
number - you must turn off **both** options, not just the first one.

**Technical limitation:** the suggested value for drip line/individual emitters is calculated
from parameters **already saved** in the zone's previous configuration (the HA form can't read
fields being filled in during the same step) - when first setting up a zone, fill in the
"Application rate" field manually; it will be calculated automatically only after saving and
re-entering "Configure".

## Self-calibration of the zone's application rate from the flow meter

If a zone has a flow meter attached, the integration **learns** its real application rate instead
of relying solely on the value entered manually in the configuration, which is often only a rough
"by eye" approximation from sprinkler/drip specifications.

After every watering in which the valve was open for at least one minute and a real flow-meter
reading is available (not an estimate), the integration calculates: `measured_rate =
delivered_depth (mm) / runtime (h)`, and updates it with an exponentially weighted moving average
(newer measurements count more than older ones, so the model keeps up with real changes - e.g. a
clogged emitter, a drop in mains pressure). A single, extremely unrealistic reading (e.g. a
flow-meter glitch) is rejected, so it doesn't corrupt the whole learned history.

**The learned value automatically replaces the manual one in all calculations** (the watering
threshold, the required time, the safety-limit check in Repairs) - nothing needs to be switched
manually. It's visible in `sensor.<zone>_application_rate`, together with the manual value, the
sample count, and the last individual measurement in the attributes - for comparison and
verification.

Without a flow meter, self-calibration doesn't work (there's nothing to learn from) - the manual
value keeps being used permanently, as before. **Even with a flow meter**, you can deliberately
turn this off per zone with the "Learn the application rate from the flow meter" switch (enabled
by default) - useful if you want full, predictable control over the manually entered value and
never want the integration to change it.

## Volume-based control (for zones with a flow meter and adjustment enabled)

Zones with a connected flow meter **and** the "Automatically adjust the watering duration based
on measured consumption" switch enabled (see "Hardware watchdog" below - it's one shared
decision) are no longer watered "by time" - the integration measures **actually delivered water
on the fly** (every `rain_pause_check_interval_min`, the same cycle used for checking rain) and
closes the valve once the delivered volume reaches the calculated target (recommended mm ×
zone area) - **regardless of whether that happens faster or slower than the initial time
estimate**:

- **Faster than estimated** (higher actual rate than assumed): the valve closes earlier - no
  overwatering.
- **Slower than estimated** (pressure drop, slower flow): watering is **automatically extended**
  beyond the original estimate, until the target is reached - limited only by the hard safety
  limit `max_runtime_min`, which is never exceeded regardless of anything else. If the limit is
  reached without delivering the full calculated amount, the integration logs a warning (worth
  checking the pressure/rate at that point).

This can mean a single watering (or the whole sequence, if this affects one of the queued zones)
runs past the originally intended start time, or even past sunrise itself - considered
acceptable, because delivering the correct amount of water matters more than sticking rigidly to
the schedule to the minute.

Zones **without** a flow meter, or with the adjustment switch disabled, work as before - purely
by time, with no ability to confirm or extend (in the first case there's simply nothing to
measure the actual delivered amount with; in the second, it's a deliberate choice of a tighter,
predictable duration).

Manually forcing a zone via the `garden_irrigation.run_zone` service **always** respects exactly
the given number of minutes, without volume-based control - it's a deliberate "water exactly this
much" command, not "water until enough".

How the last watering ended is visible in the `sensor.<zone>_recommended_watering` attributes:
- `last_watering_completion_method`: `volume_reached` / `time` / `safety_limit`
- `last_watering_planned_runtime_min` / `_actual_runtime_min` / `_extension_min`

## Sequential zone activation with verification

Valves are always opened **strictly one at a time, never in parallel**. For each zone, starting
with the first, the integration:

1. Sends the command to open the valve.
2. **Polls the entity's state every 1 second**, until it confirms the valve has actually opened
   (or `valve_verify_timeout_sec`, 15s by default, elapses). If you have an instantaneous flow
   meter configured (main or per-zone), verification **additionally** requires the flow to exceed
   the no-flow threshold - a stronger confirmation than the entity state alone, since it catches
   e.g. a valve that reports "open" but hasn't physically opened. A missing flow-meter reading
   doesn't block verification - in that case only the entity state is used, as if this option
   weren't set. If the valve doesn't open - it logs an error, skips that zone, and **continues
   with the next one** (one faulty zone doesn't block the rest of the garden).
3. After the watering time is up, it sends the close command.
4. **Polls the state again** (and the instantaneous flow, if configured - it must drop below the
   threshold), until it confirms closure. This is also the moment the state-change event triggers
   a reading of the CUMULATIVE flow meter (if connected) and calculates the water used. If the
   valve doesn't confirm closure within the time limit - the integration logs an ERROR-level
   message and **stops the rest of the sequence** (doesn't open the next zone until it's certain
   the previous one is safely closed - this avoids e.g. a pressure drop from two simultaneously
   open/leaking zones).
5. Only after confirmed closure does it wait `zone_transition_delay_sec` (5s by default) and move
   on to opening the next zone in order, repeating from step 1.

The same verification mechanism also applies to a single manual zone activation (button /
`run_zone` service), not just within a sequence.

## Watering queue (no simultaneous valves)

By default, the integration guarantees that **no two valves are ever open at the same time** -
regardless of whether they were triggered by manual approval, `approve_all`, the pre-sunrise
sequence, or a growth stage (new planting/reseeding, see below). Every valve opening goes
through a shared lock (FIFO) - if another zone is currently watering, the request simply waits
in line instead of opening a second valve in parallel.

This matters especially for growth stages, which can water several times a day independently
of the main schedule - without this lock they could overlap with the pre-sunrise sequence or a
manual approval of another zone and open a second valve at the same time.

This can be disabled with the `switch.garden_irrigation_allow_simultaneous_watering` switch
("Allow simultaneous watering of zones") - all zones can then start in parallel, as before.
Only enable it if you know your plumbing/water pressure can actually handle it - most home
irrigation mains can't hold full pressure with several valves open at once. Off by default (the
safer option).

## Minimum interval between waterings

The water-balance model itself already naturally leads to less frequent, deeper watering than a
time-based schedule - but if you want a hard guarantee (e.g. to deliberately train roots to
reach deeper), set `min_days_between_watering` for a given zone. Even if the water deficit
crosses the threshold earlier, the zone will wait until that many days have passed since the
last actual watering - the deficit keeps growing in the meantime (nothing is zeroed out or lost),
the recommendation is simply held back until the minimum interval has passed.

### Dynamic MAD threshold adjustment per FAO-56 (and automatic bypass in a heatwave)

The MAD threshold is **no longer a fixed number** from the selected plants - the integration
corrects it every night with the official FAO-56 formula (chapter 8), based on yesterday's
water-use rate (ETc):

```
adjusted_threshold = base_threshold + 0.04 × (5 − ETc)     [clamped to the 0.1-0.8 range]
```

The physical rationale: in hot/dry conditions (high ETc), the plant starts to suffer **earlier**,
because the roots can't keep up with such high atmospheric demand for water, even before the soil
dries out to a "normal" level - the threshold is then automatically **lower**, so watering kicks
in sooner. In cool, cloudy weather the threshold is **higher** - the soil can safely dry out more
before it becomes a problem.

**This automatically resolves the tension between the minimum interval and a heatwave**, with no
manual intervention: when yesterday's ETc exceeds 5 mm/day (exactly the threshold at which the
FAO-56 correction turns negative - the official definition of "hot, dry conditions"), **the
minimum interval between waterings is automatically bypassed for that day**, for that zone. You
don't need to manually raise or lower anything ahead of an expected heatwave - the model detects
it itself from real weather data and lifts the rigid limit for one day, instead of waiting until
the plant actually starts to suffer.

The effective (adjusted) threshold, the base value, yesterday's ETc, and whether the bypass
kicked in today are all visible in the `sensor.<zone>_mad_threshold` attributes.

This whole mechanism can be turned off **on the fly**, without reconfiguring the integration -
via the `switch.garden_irrigation_dynamic_mad_enabled` switch ("Dynamic MAD adjustment
(FAO-56)"). Disabling it restores the fixed, base MAD threshold (from the selected plants/manual
calibration), with no daily adjustment and no automatic bypass of the minimum interval. The
`dynamic_mad_enabled` field in the setup wizard only sets the **initial** value on first
installation - later changes are actually controlled by this switch, not the wizard.

## New planting / reseeding (growth stages)

Freshly seeded grass or newly planted plants need much more frequent, shallower watering than
already established vegetation in the same zone - the standard soil-water-balance model (tuned
for a mature plant) would miss that entirely. For this situation, every plant in the
integration's catalog also has a **growth-stage schedule** defined:

1. **Germination** - the most frequent, shortest waterings (typically several times a day for
   1-2 weeks, depending on the plant).
2. **Young plants** - less often, but still more frequent than standard (typically once a day
   for another 2-4 weeks).
3. **Standard** - the integration automatically returns to the normal soil-water balance.

For the whole duration of the growth stages, the zone **bypasses** the normal soil-moisture-
deficit (SMD) decision logic - it waters purely on the frequency defined for the current stage,
regardless of what the actual deficit would be. It still respects the global pause
(`switch.garden_irrigation_irrigation_paused`) and frost risk, but deliberately **not** rain,
the rain forecast, or wind - freshly planted vegetation needs regularity more than water
savings at this stage.

### How to start it

**From the GUI** (since version 1.17.2) - available only in the **Options** of an already
installed integration (not in the first-install wizard, since the step needs a running
coordinator): Settings → Devices & services → Garden - Smart Irrigation → **Configure** → pick
**"New planting / reseeding"** from the main menu. For each configured zone there's a toggle
(reflects whether the zone currently has an active growth stage) and a plant picker limited to
the plants **already assigned** to that zone. Turning the toggle on, picking plants, and saving
**starts** the new planting; turning the toggle off for a zone with an already-running stage
**cancels** it and immediately returns to standard.

**Via services** (e.g. from an automation, or Developer Tools → Actions):

| Service | Parameters | Effect |
|---|---|---|
| `garden_irrigation.start_new_planting` | `zone_id`, `plant_keys` (plants already assigned to the zone) | Starts the growth stage for the zone |
| `garden_irrigation.cancel_new_planting` | `zone_id` | Immediately ends the growth stage, returns to standard |

### Several plants at once in one zone

A zone has a single, shared stage schedule, not one per plant. If you select several plants at
once (e.g. reseeding the lawn while planting new shrubs next to it), the integration picks the
**"weakest"** one - the one with the lowest MAD threshold (the same sensitivity indicator the
integration already uses for mixed plantings in normal mode) - and ITS schedule (both stages'
durations and frequencies) governs the whole zone cycle from start to finish.

### Live status

`sensor.<zone>_growth_stage` - the value is the current stage ("Germination" / "Young plants" /
"standard"), attributes: whether active, the leading plant (the one whose schedule was used),
selected plants, when it started, end of the current stage, when it returns to standard, next
scheduled watering, last watering.

## Protection against wind and frost

- **Wind**: zones marked as `wind_sensitive` (typically sprinklers - drift, uneven coverage) are
  skipped when the current wind speed exceeds `wind_skip_threshold_ms`. Checked freshly right
  before starting (just like rain).
- **Frost**: if the current temperature drops below `frost_threshold_c`, **all** watering (every
  zone) is paused for that day - this is a risk to the whole system (hoses, valves), not just a
  particular plant. Checked every night and freshly before starting.

Neither check resets the deficit - if watering is skipped on a given day, it will catch up at the
next opportunity, once conditions allow.

## Global switch (holiday mode)

The `switch.wstrzymaj_cale_podlewanie` entity ("pause all watering") - when on, it blocks
EVERYTHING: manual approval, `approve_all`, the pre-sunrise sequence, and automatic mode, until
it's turned off. Useful while traveling, during garden work, or when the water is physically shut
off. The water deficit keeps being calculated during this time (nothing is lost) - once the pause
is turned off, the integration will simply propose watering according to the current state.

## Water-usage statistics

Available as separate sensors (see below) - daily, monthly, and yearly usage per zone and for
the whole garden combined, calculated from the same data as the water balance (a real flow-meter
reading if connected, otherwise an estimate from runtime and the application rate). Daily
counters reset at midnight, monthly on the first of the month, yearly on January 1st. **Rounded
to 0.1 L** (not 0.01 L) - this is the real precision ceiling of a typical water meter in Home
Assistant (`device_class: water`), which itself reports volume in m³ with a limited number of
decimal places; showing a second decimal place would suggest a precision the reading physically
doesn't have.

**Last watering - scheduled vs. any.** The "water used during last watering" sensor gets
overwritten by EVERY valve opening, including a short, manual test via the `run_zone` service
(e.g. a few seconds to check the valve works) - which makes it useless for telling when a zone
actually last got a full, scheduled watering. A separate sensor
`sensor.<zone>_water_used_last_scheduled_watering` is written to ONLY by waterings that come
from the integration's own schedule (approval/`approve_all`, the pre-sunrise sequence, growth
stages) - manual `run_zone` tests never touch it, so it always reflects the real history of
when the zone was last watered according to plan, no matter how many times someone manually
checked the valve in between.

## Home Assistant Repairs notices

The integration uses HA's built-in Repairs mechanism (Settings → System → Repairs) to report
issues that need your attention, instead of hiding them only in the logs:

- **Missing zone entity** - checked at integration startup, if a configured valve doesn't exist
  in HA.
- **Zone watering time limit too low** - checked at startup: if the configured `max_runtime_min`
  is shorter than the time needed to fully refill the root zone from empty (at the current
  sprinkler/drip application rate), the integration will never manage to deliver the full dose
  after a longer break (holiday, a series of days skipped due to rain) - the notice includes the
  exact, calculated value the limit should be raised to.
- **Valve did not confirm opening** - informational, that one zone was skipped, the rest continue
  normally.
- **Valve did not confirm closing** - more serious, since it may have been left physically open;
  the rest of the sequence is stopped for safety, worth checking manually as soon as possible.

Notices disappear automatically once the problem is resolved (e.g. the valve starts responding
correctly again).

## Predictable entity IDs

Every entity gets a forced, stable `entity_id` in the format
`<domain>.garden_irrigation_<zone_NN>_<english_suffix>` (e.g.
`sensor.garden_irrigation_zone_01_recommended_watering`,
`switch.garden_irrigation_irrigation_paused`) - the **integration prefix** minimizes the risk of
colliding with other entities in your HA, and using **the zone's number instead of its
descriptive name** (`zone_01`, `zone_02`...) avoids absurdly long identifiers if you give a zone
a long name, and doesn't change even if you rename it later - only the displayed label
(`friendly_name`) changes, not the technical identifier. The zone number corresponds to its
position in the configuration (the `zoneN_*` field), not its display order. Entity names
(`friendly_name`, shown in the UI) stay fully translated and are built from the name you gave the
zone - only the technical `entity_id` behind the scenes stays fixed.

**Important:** this only works reliably for **newly created** entities - HA's entity registry
keeps an `entity_id` permanently once assigned, even after the integration's code changes. If
you're upgrading from an earlier version (rather than installing from scratch), existing entities
keep their current identifiers - to get the new ones, you'd need to remove the integration and
add it again (a fresh registry).

## Intraday preview (the "projected" sensors)

The main water deficit and watering recommendation are recalculated **once a day** (the nightly
recalculation) plus **freshly right before starting** - these are the only values that actually
drive watering, and deliberately don't change during the day outside those two moments.

Alongside them, there's a **separate, purely informational pair of sensors** per zone:
`sensor.<zone>_projected_soil_water_deficit` and `sensor.<zone>_projected_watering_time`. They
grow **smoothly throughout the day** - the integration spreads the daily water loss (ETc) into
small increments every update cycle (together with rainfall subtracted on the fly), instead of
waiting for the next midnight. This lets you see "live" how the system is assessing the
situation at any given moment of the day.

**Important details about these sensors** (so you know where you stand):
- The intraday spread of water loss is **uniform over time**, not weighted by the real rhythm of
  evapotranspiration (which in nature is concentrated during the day, nearly zero at night) -
  this is a deliberate simplification, not an attempt at maximum accuracy.
- **The minute value in `_projected_watering_time` is ALWAYS a pure function of the projected
  deficit** - exactly the same relationship as in the main sensor (time = required mm /
  application rate), with no exceptions and never zeroed by anything. Information about what
  *currently* would block approval (rain/forecast/wind/frost/minimum interval) is a **separate
  `blocked_by` attribute** (a list of reasons, or `null`) - it never changes the minute value
  itself, only adds context alongside it.
- `blocked_by` is refreshed **once an hour**, not every cycle (10 min) - wind and temperature
  naturally jump around from minute to minute, so checking more often would give a flickering
  result (blocked → not blocked → blocked within a single hour). The deficit and the minute
  value itself still update smoothly every 10 minutes - the throttling only applies to this one
  contextual attribute.
- **They don't affect any actual decision** - this is purely a preview. The only source of truth
  for whether and when watering actually happens remains the main sensors
  (`_recommended_watering`, `_soil_water_deficit`) and the logic described in the rest of this
  document.

## Available entities

**Sensors:**
- `sensor.garden_irrigation_et0_yesterday` - ET0 calculated for the previous day
- `sensor.garden_irrigation_weather_inputs` ("Weather inputs") - for verifying nothing is being
  missed: the main value is the method used yesterday (`penman_monteith` / `hargreaves` /
  `no_data`); attributes: a live reading right now (temperature, solar radiation, humidity,
  wind), the exact inputs from yesterday (tmax/tmin/tmean, averaged solar/wind/humidity, sample
  count for each), the rain forecast (mm and when it was fetched), the raw total-rain counter,
  `rain_measured_today_mm` (the sum of counter increments since the last midnight, actually
  subtracted from every zone's deficit - not a raw reading, a genuinely computed daily total),
  `nightly_forecast` (a persistent snapshot from the last nightly recalculation - the forecast
  value, the threshold, whether it was held back - overwritten only at the NEXT nightly
  recalculation, not during the day), and `last_forecast_check` (the most recent forecast check
  from ANY source - night / before zone approval / before the sequence / hourly refresh - with a
  description of when and from where, overwritten at every subsequent check)
- per zone, `sensor.<zone>_recommended_watering` additionally has a
  `rain_during_current_pause_mm` attribute - a live sum of rain measured since this specific zone
  was paused for rain (updated every check cycle, visible during the pause itself, not just
  afterwards)
- `sensor.next_sequence_start_time` - the start time of the nearest scheduled sequence (a
  timestamp entity). Attributes: status (`scheduled`/`running`/`done`/`cancelled_rain`/
  `no_zones`), the planned sunrise, the total duration, and the full order and planned start
  time of every zone
- per zone, `sensor.<zone>_recommended_watering` - a value in minutes, attributes: status, mm,
  the reason for skipping, how the last watering ended (see "Volume-based control")
- per zone, `sensor.<zone>_soil_water_deficit` - the current deficit in mm
- per zone, `sensor.<zone>_soil_water_level` / `_soil_water_level_live` - the inverse of the
  deficit: how much water is actually present in the root zone right now (mm and % of capacity
  in the attributes) - the first updates at the same rate as the main deficit, the second
  smoothly through the day like the "live" sensors
- per zone, `sensor.<zone>_projected_soil_water_deficit` / `_projected_watering_time` - a
  purely informational, intraday-growing preview (see the section above)
- per zone, `sensor.<zone>_soil_plant_parameters` - the value is the list of selected plants;
  attributes show the soil, the adopted Kc/depth/MAD, and the full breakdown of ALL selected
  plants with their individual parameters
- per zone, `sensor.<zone>_kc_value` - the numeric Kc used in the balance, with a "taken from"
  attribute (the plant name, or "manual calibration") and a full plant→Kc list for every plant
  selected in that zone
- per zone, `sensor.<zone>_mad_threshold` - the same, for the (FAO-56-adjusted) MAD threshold
- per zone, `sensor.<zone>_min_days_between_watering` - the configured number of days (0 = no
  limit), with attributes: the date of the last watering, days elapsed, whether it's active today
- per zone, `sensor.<zone>_max_runtime` - the configured safety limit (min), with a
  `required_full_refill_min` attribute (how much is actually needed to fully refill the root
  zone from empty) and `too_low` (True/False)
- per zone, `sensor.<zone>_area` (m²)
- per zone, `sensor.<zone>_application_rate` (mm/h) - the effective rate (learned if already
  available, otherwise manual), with attributes: manual value, learned value, sample count, last
  measurement
- per zone, `sensor.<zone>_water_used_today` / `_water_used_this_month` / `_water_used_this_year`
  (liters)
- per zone, `sensor.<zone>_water_used_last_watering` (liters) - just the most recent, single
  watering (not a sum), with a `when` attribute - overwritten by EVERY watering, including
  manual `run_zone` tests (see "Water-usage statistics")
- per zone, `sensor.<zone>_water_used_last_scheduled_watering` (liters) - the same, but ONLY for
  waterings coming from the integration's own schedule (approval/`approve_all`, the pre-sunrise
  sequence, growth stages) - manual `run_zone` tests never overwrite it
- `sensor.total_water_today` / `_this_month` / `_this_year` (liters, whole garden)
- `sensor.garden_irrigation_total_water_last` - the sum of the most recent single watering of
  EVERY zone individually (not necessarily the same day for all of them), with a per-zone
  breakdown in the attributes
- per zone, `sensor.<zone>_growth_stage` - the new-planting/reseeding state (see "New planting /
  reseeding (growth stages)")

**Switches:**
- `switch.garden_irrigation_irrigation_paused` - global pause (holiday mode), see above
- `switch.garden_irrigation_dynamic_mad_enabled` - turns the dynamic FAO-56 MAD adjustment on/off
  (see "Minimum interval between waterings")
- `switch.garden_irrigation_allow_simultaneous_watering` - lets zones water in parallel instead
  of queuing (see "Watering queue")

**Binary sensors:**
- per zone, `binary_sensor.<zone>_rain_paused` - on when THAT zone is currently paused because of
  rain during watering
- `binary_sensor.any_zone_rain_paused` - on when ANY zone is paused; an attribute lists the paused
  zones

**Buttons:**
- per zone "approve and run" / "skip today"
- "Approve all pending zones"
- "Schedule sequence before sunrise"

## Services

| Service | Parameters | Action |
|---|---|---|
| `garden_irrigation.approve_zone` | `zone_id` | Approves and starts the recommendation for one zone (with a fresh rain/forecast check) |
| `garden_irrigation.approve_all` | - | Approves all pending zones, one after another |
| `garden_irrigation.skip_zone` | `zone_id` | Cancels today's recommendation without watering |
| `garden_irrigation.run_zone` | `zone_id`, `minutes` | Manually runs a zone for a given time, independent of the recommendation |
| `garden_irrigation.run_sequence_before_sunrise` | - | Builds and schedules the sequence of all approved zones, calculating the start backwards from sunrise |
| `garden_irrigation.start_new_planting` | `zone_id`, `plant_keys` | Starts new planting/reseeding for a zone - see "New planting / reseeding" |
| `garden_irrigation.cancel_new_planting` | `zone_id` | Ends new planting/reseeding early, returns to standard |

## Calibration

The system starts with reasonable default values (Kc, MAD, soil water capacity), but these are
approximations - your garden, microclimate, and actual soil conditions may differ. After the
first 2-3 weeks of observation:

- If a plant is drying out despite regular watering - lower the MAD threshold for that zone (the
  "Manual MAD calibration" field, e.g. from 0.45 to 0.35) - this will make watering start
  earlier.
- If a zone is being overwatered - raise the MAD threshold, or lower Kc (the "Manual Kc
  calibration" field) - this will slow the growth of the deficit and make watering less frequent.
- `sensor.<zone>_kc_value` and `sensor.<zone>_mad_threshold` show exactly which value is
  currently in use and where it came from (which plant, or manual calibration) - a good starting
  point for deciding what to adjust.

## Things worth being aware of

- The watering sequence and the "wake up" wait in automatic mode run as background tasks inside a
  running Home Assistant instance - they are **not** persisted to a database or replayed after a
  restart. An HA restart while waiting for the start will interrupt that night's scheduled
  watering.
- The exact shape of the data returned by `weather.get_forecasts` can differ between weather
  integrations - if a warning about a failed forecast fetch appears in the logs after configuring
  a `weather.*` entity, check manually in Developer Tools → Services by calling
  `weather.get_forecasts` with `type: hourly` on your entity (some integrations only support a
  daily forecast, not hourly).
- The integration deliberately does **not** send push notifications (e.g. on a rain pause) - the
  state is always visible in the sensors/attributes, but nobody gets woken up at night by their
  phone. If you'd still like notifications, the simplest approach is to add your own HA
  automation listening for changes to `binary_sensor.any_zone_rain_paused` or the state of
  `sensor.*_recommended_watering`.
- The zone fields in the setup wizard have translated, descriptive labels for the first 12 zones
  - with more zones, the additional fields still work, just without a translated label.
