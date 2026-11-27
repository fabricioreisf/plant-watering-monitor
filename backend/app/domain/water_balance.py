"""Balanço hídrico do vaso: funções puras, sem I/O.

A umidade do vaso é uma fração entre 0 e 1 da água disponível que o substrato retém:
1 logo após uma rega completa (capacidade de campo), 0 quando a planta não consegue
mais extrair água. Ela

- sobe com regas e com chuva (somente plantas `outdoor`);
- cai com a evapotranspiração da planta: ``ET_planta = Kc * ET0``, reduzida em ambientes
  internos.

O vaso é modelado como um cilindro com altura igual ao diâmetro. A lâmina de água que ele
retém (em mm, mesma unidade de ET0 e chuva) é a profundidade do substrato vezes a fração
de água disponível. As constantes abaixo são aproximações documentadas; leituras de sensor
e registros de rega corrigem o modelo na prática.
"""

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum

# Fração do volume do substrato que fica disponível para a planta após drenar.
AVAILABLE_WATER_FRACTION = 0.3
# Ambientes internos têm menos radiação e vento que a referência FAO-56 de ET0.
INDOOR_ET_FACTOR = 0.5
# ET0 usada quando não há dado de clima para um dia (valor típico de clima ameno).
DEFAULT_ET0_MM = 3.0

_DAY = timedelta(days=1)


class Environment(StrEnum):
    INDOOR = "indoor"
    OUTDOOR = "outdoor"


@dataclass(frozen=True)
class PlantProfile:
    """Parâmetros de uma planta que o balanço hídrico precisa."""

    kc: float
    drying_threshold: float
    environment: Environment
    pot_volume_liters: float

    def __post_init__(self) -> None:
        if not 0 < self.kc <= 1.5:
            raise ValueError(f"kc must be in (0, 1.5], got {self.kc}")
        if not 0 < self.drying_threshold < 1:
            raise ValueError(f"drying_threshold must be in (0, 1), got {self.drying_threshold}")
        if self.pot_volume_liters <= 0:
            raise ValueError(f"pot_volume_liters must be positive, got {self.pot_volume_liters}")


@dataclass(frozen=True)
class DailyWeather:
    day: date
    et0_mm: float
    rain_mm: float = 0.0

    def __post_init__(self) -> None:
        if self.et0_mm < 0 or self.rain_mm < 0:
            raise ValueError("et0_mm and rain_mm must be non-negative")


@dataclass(frozen=True)
class Watering:
    """Uma rega. `amount_ml=None` significa rega completa (encharcar e deixar drenar)."""

    at: datetime
    amount_ml: int | None = None

    def __post_init__(self) -> None:
        _require_aware(self.at, "at")
        if self.amount_ml is not None and self.amount_ml <= 0:
            raise ValueError(f"amount_ml must be positive, got {self.amount_ml}")


@dataclass(frozen=True)
class SimulationResult:
    moisture: float
    # Dias sem dado de clima, em que DEFAULT_ET0_MM foi usado.
    missing_weather_days: tuple[date, ...] = ()


def clamp_moisture(value: float) -> float:
    return min(1.0, max(0.0, value))


def pot_depth_mm(pot_volume_liters: float) -> float:
    """Altura do substrato num vaso cilíndrico com altura igual ao diâmetro."""
    volume_m3 = pot_volume_liters / 1000
    return (4 * volume_m3 / math.pi) ** (1 / 3) * 1000


def water_capacity_mm(pot_volume_liters: float) -> float:
    """Lâmina de água disponível que o vaso retém, em mm."""
    return AVAILABLE_WATER_FRACTION * pot_depth_mm(pot_volume_liters)


def water_capacity_liters(pot_volume_liters: float) -> float:
    """Volume de água que leva o vaso de completamente seco (0) a cheio (1)."""
    return AVAILABLE_WATER_FRACTION * pot_volume_liters


def plant_et_mm(et0_mm: float, kc: float, environment: Environment) -> float:
    """Evapotranspiração da planta: ``Kc * ET0``, com redução para ambiente interno."""
    factor = INDOOR_ET_FACTOR if environment is Environment.INDOOR else 1.0
    return kc * et0_mm * factor


def apply_watering(moisture: float, amount_ml: int | None, profile: PlantProfile) -> float:
    if amount_ml is None:
        return 1.0
    gained = amount_ml / 1000 / water_capacity_liters(profile.pot_volume_liters)
    return clamp_moisture(moisture + gained)


def apply_weather(
    moisture: float, weather: DailyWeather, profile: PlantProfile, fraction_of_day: float = 1.0
) -> float:
    """Aplica (uma fração de) um dia de clima: primeiro a chuva, depois a evapotranspiração.

    O excesso de chuva acima da capacidade drena e é perdido.
    """
    if not 0 <= fraction_of_day <= 1:
        raise ValueError(f"fraction_of_day must be in [0, 1], got {fraction_of_day}")
    capacity = water_capacity_mm(profile.pot_volume_liters)

    if profile.environment is Environment.OUTDOOR:
        moisture = clamp_moisture(moisture + weather.rain_mm * fraction_of_day / capacity)

    et = plant_et_mm(weather.et0_mm, profile.kc, profile.environment) * fraction_of_day
    return clamp_moisture(moisture - et / capacity)


def simulate(
    *,
    start_moisture: float,
    start: datetime,
    end: datetime,
    profile: PlantProfile,
    weather: Mapping[date, DailyWeather],
    waterings: Iterable[Watering] = (),
) -> SimulationResult:
    """Evolui a umidade de `start` até `end`.

    Os dias são em UTC. Dias parciais recebem a fração proporcional de ET0 e chuva. Regas
    em ``[start, end]`` são aplicadas no instante em que ocorreram (`start_moisture` é o
    estado antes de qualquer rega em `start`).
    """
    _require_aware(start, "start")
    _require_aware(end, "end")
    if end < start:
        raise ValueError("end must not be before start")

    moisture = clamp_moisture(start_moisture)
    missing: set[date] = set()
    cursor = start.astimezone(UTC)
    events = sorted((w for w in waterings if start <= w.at <= end), key=lambda w: w.at)

    for event in events:
        moisture = _advance(moisture, cursor, event.at, profile, weather, missing)
        moisture = apply_watering(moisture, event.amount_ml, profile)
        cursor = event.at.astimezone(UTC)

    moisture = _advance(moisture, cursor, end.astimezone(UTC), profile, weather, missing)
    return SimulationResult(moisture=moisture, missing_weather_days=tuple(sorted(missing)))


def _advance(
    moisture: float,
    start: datetime,
    end: datetime,
    profile: PlantProfile,
    weather: Mapping[date, DailyWeather],
    missing: set[date],
) -> float:
    cursor = start.astimezone(UTC)
    end = end.astimezone(UTC)
    while cursor < end:
        day = cursor.date()
        next_midnight = datetime.combine(day + _DAY, time(), tzinfo=UTC)
        segment_end = min(end, next_midnight)
        day_weather = weather.get(day)
        if day_weather is None:
            missing.add(day)
            day_weather = DailyWeather(day=day, et0_mm=DEFAULT_ET0_MM)
        moisture = apply_weather(moisture, day_weather, profile, (segment_end - cursor) / _DAY)
        cursor = segment_end
    return moisture


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
