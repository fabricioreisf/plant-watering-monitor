"""Estimativa da umidade atual e recomendação de rega: funções puras, sem I/O.

Prioridade das fontes: leitura de sensor > registro do usuário > estimativa por clima.
A fonte usada define o nível de confiança informado na recomendação.
"""

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import StrEnum

from app.domain.water_balance import (
    DEFAULT_ET0_MM,
    DailyWeather,
    PlantProfile,
    Watering,
    apply_weather,
    simulate,
    water_capacity_liters,
)

# Umidade assumida no início do acompanhamento quando não há sensor nem registro.
ASSUMED_INITIAL_MOISTURE = 0.5
# Leituras mais antigas que isso ainda ancoram a estimativa, mas com confiança menor.
SENSOR_FRESHNESS = timedelta(hours=6)
# "Regar em breve" quando o limite de secagem deve ser atingido dentro desta janela.
WATER_SOON_WITHIN_DAYS = 1.0
# Horizonte máximo da projeção; além disso a próxima rega é "em mais de N dias".
MAX_PROJECTION_DAYS = 30
# Arredondamento da quantidade sugerida (ninguém mede 437 ml).
AMOUNT_ROUNDING_ML = 50


class MoistureSource(StrEnum):
    SENSOR = "sensor"
    WATERING_LOG = "watering_log"
    WEATHER_ESTIMATE = "weather_estimate"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Urgency(StrEnum):
    WATER_NOW = "water_now"
    WATER_SOON = "water_soon"
    OK = "ok"


@dataclass(frozen=True)
class SensorReading:
    at: datetime
    soil_moisture: float

    def __post_init__(self) -> None:
        if not 0 <= self.soil_moisture <= 1:
            raise ValueError(f"soil_moisture must be in [0, 1], got {self.soil_moisture}")


@dataclass(frozen=True)
class MoistureEstimate:
    moisture: float
    source: MoistureSource
    confidence: Confidence
    as_of: datetime
    missing_weather_days: tuple[date, ...] = ()


@dataclass(frozen=True)
class Recommendation:
    urgency: Urgency
    estimate: MoistureEstimate
    drying_threshold: float
    # Dias até atingir o limite de secagem; None se passar de MAX_PROJECTION_DAYS.
    days_until_threshold: float | None
    # Quantidade para levar o vaso de volta à capacidade; só quando é hora de regar.
    suggested_amount_ml: int | None
    # Sem registros e "provavelmente seco": perguntar ao usuário se ele regou.
    ask_if_watered: bool = field(default=False)


def estimate_current_moisture(
    *,
    profile: PlantProfile,
    now: datetime,
    tracking_since: datetime,
    weather: Mapping[date, DailyWeather],
    waterings: Iterable[Watering] = (),
    sensor_readings: Iterable[SensorReading] = (),
) -> MoistureEstimate:
    """Estima a umidade em `now` a partir da fonte mais confiável disponível.

    A leitura de sensor mais recente, se existir, é o ponto de partida. Sem sensor, parte de
    `tracking_since` (por exemplo, o cadastro da planta) com ASSUMED_INITIAL_MOISTURE. Em
    ambos os casos, regas posteriores e o clima são aplicados até `now`.
    """
    waterings = [w for w in waterings if w.at <= now]
    readings = [r for r in sensor_readings if r.at <= now]
    latest_reading = max(readings, key=lambda r: r.at, default=None)

    if latest_reading is not None:
        start, start_moisture = latest_reading.at, latest_reading.soil_moisture
        source = MoistureSource.SENSOR
        fresh = now - latest_reading.at <= SENSOR_FRESHNESS
        confidence = Confidence.HIGH if fresh else Confidence.MEDIUM
    else:
        start = min([tracking_since, *(w.at for w in waterings)])
        start_moisture = ASSUMED_INITIAL_MOISTURE
        if waterings:
            source, confidence = MoistureSource.WATERING_LOG, Confidence.MEDIUM
        else:
            source, confidence = MoistureSource.WEATHER_ESTIMATE, Confidence.LOW

    result = simulate(
        start_moisture=start_moisture,
        start=start,
        end=now,
        profile=profile,
        weather=weather,
        waterings=waterings,
    )
    if result.missing_weather_days and source is not MoistureSource.SENSOR:
        confidence = Confidence.LOW

    return MoistureEstimate(
        moisture=result.moisture,
        source=source,
        confidence=confidence,
        as_of=now,
        missing_weather_days=result.missing_weather_days,
    )


def days_until_threshold(
    moisture: float, profile: PlantProfile, forecast: Sequence[DailyWeather] = ()
) -> float | None:
    """Projeta, dia a dia, quando a umidade atinge o limite de secagem.

    Usa a previsão na ordem dada e DEFAULT_ET0_MM depois que ela acaba. Dentro do dia em
    que o limite é cruzado, interpola linearmente.
    """
    threshold = profile.drying_threshold
    if moisture <= threshold:
        return 0.0

    for day_index in range(MAX_PROJECTION_DAYS):
        if day_index < len(forecast):
            day_weather = forecast[day_index]
        else:
            day_weather = DailyWeather(day=date.min, et0_mm=DEFAULT_ET0_MM)
        next_moisture = apply_weather(moisture, day_weather, profile)
        if next_moisture <= threshold:
            return day_index + (moisture - threshold) / (moisture - next_moisture)
        moisture = next_moisture
    return None


def suggested_amount_ml(moisture: float, profile: PlantProfile) -> int:
    """Água para voltar à capacidade, arredondada para cima em AMOUNT_ROUNDING_ML."""
    deficit_ml = (1 - moisture) * water_capacity_liters(profile.pot_volume_liters) * 1000
    return max(AMOUNT_ROUNDING_ML, math.ceil(deficit_ml / AMOUNT_ROUNDING_ML) * AMOUNT_ROUNDING_ML)


def recommend(
    profile: PlantProfile, estimate: MoistureEstimate, forecast: Sequence[DailyWeather] = ()
) -> Recommendation:
    days = days_until_threshold(estimate.moisture, profile, forecast)

    if estimate.moisture <= profile.drying_threshold:
        urgency = Urgency.WATER_NOW
    elif days is not None and days <= WATER_SOON_WITHIN_DAYS:
        urgency = Urgency.WATER_SOON
    else:
        urgency = Urgency.OK

    needs_water = urgency is not Urgency.OK
    return Recommendation(
        urgency=urgency,
        estimate=estimate,
        drying_threshold=profile.drying_threshold,
        days_until_threshold=days,
        suggested_amount_ml=suggested_amount_ml(estimate.moisture, profile)
        if needs_water
        else None,
        ask_if_watered=(
            urgency is Urgency.WATER_NOW and estimate.source is MoistureSource.WEATHER_ESTIMATE
        ),
    )
