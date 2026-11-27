import math
from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from app.domain.water_balance import (
    DEFAULT_ET0_MM,
    INDOOR_ET_FACTOR,
    DailyWeather,
    Environment,
    PlantProfile,
    Watering,
    apply_watering,
    apply_weather,
    plant_et_mm,
    pot_depth_mm,
    simulate,
    water_capacity_liters,
    water_capacity_mm,
)

# Vaso de π/4 L: cilindro com 100 mm de altura → retém 30 mm de água disponível.
POT_100MM = math.pi / 4
DAY1 = date(2026, 11, 20)
DAY2 = date(2026, 11, 21)


def profile(
    environment: Environment = Environment.OUTDOOR, kc: float = 1.0, volume: float = POT_100MM
) -> PlantProfile:
    return PlantProfile(
        kc=kc, drying_threshold=0.3, environment=environment, pot_volume_liters=volume
    )


def at(day: date, hour: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=UTC)


def weather(*days: tuple[date, float, float]) -> dict[date, DailyWeather]:
    return {d: DailyWeather(day=d, et0_mm=et0, rain_mm=rain) for d, et0, rain in days}


class TestPotGeometry:
    def test_depth_of_cylinder_with_height_equal_to_diameter(self) -> None:
        assert pot_depth_mm(POT_100MM) == pytest.approx(100)

    def test_capacity_in_mm_is_available_fraction_of_depth(self) -> None:
        assert water_capacity_mm(POT_100MM) == pytest.approx(30)

    def test_capacity_in_liters_scales_with_volume(self) -> None:
        assert water_capacity_liters(10) == pytest.approx(3)

    def test_bigger_pots_hold_more_water_per_area(self) -> None:
        assert water_capacity_mm(20) > water_capacity_mm(2)


class TestPlantEvapotranspiration:
    def test_outdoor_is_kc_times_et0(self) -> None:
        assert plant_et_mm(4.0, 0.5, Environment.OUTDOOR) == pytest.approx(2.0)

    def test_indoor_is_reduced(self) -> None:
        assert plant_et_mm(4.0, 0.5, Environment.INDOOR) == pytest.approx(2.0 * INDOOR_ET_FACTOR)

    def test_zero_et0_means_no_loss(self) -> None:
        assert plant_et_mm(0.0, 1.2, Environment.OUTDOOR) == 0


class TestApplyWatering:
    def test_full_watering_fills_the_pot(self) -> None:
        assert apply_watering(0.1, None, profile()) == 1.0

    def test_partial_watering_adds_proportionally_to_capacity(self) -> None:
        # Vaso de 10 L retém 3 L; 600 ml = 20% da capacidade.
        assert apply_watering(0.3, 600, profile(volume=10)) == pytest.approx(0.5)

    def test_excess_drains(self) -> None:
        assert apply_watering(0.9, 5_000, profile(volume=10)) == 1.0


class TestApplyWeather:
    def test_evapotranspiration_lowers_moisture(self) -> None:
        day = DailyWeather(day=DAY1, et0_mm=3.0)
        # 3 mm de 30 mm = 10% da capacidade.
        assert apply_weather(0.8, day, profile()) == pytest.approx(0.7)

    def test_indoor_loses_less(self) -> None:
        day = DailyWeather(day=DAY1, et0_mm=3.0)
        indoor = apply_weather(0.8, day, profile(Environment.INDOOR))
        outdoor = apply_weather(0.8, day, profile(Environment.OUTDOOR))
        assert indoor > outdoor
        assert indoor == pytest.approx(0.8 - 0.1 * INDOOR_ET_FACTOR)

    def test_kc_scales_the_loss(self) -> None:
        day = DailyWeather(day=DAY1, et0_mm=3.0)
        assert apply_weather(0.8, day, profile(kc=0.5)) == pytest.approx(0.75)

    def test_rain_waters_outdoor_plants(self) -> None:
        day = DailyWeather(day=DAY1, et0_mm=0.0, rain_mm=6.0)
        assert apply_weather(0.4, day, profile(Environment.OUTDOOR)) == pytest.approx(0.6)

    def test_rain_is_ignored_indoors(self) -> None:
        day = DailyWeather(day=DAY1, et0_mm=0.0, rain_mm=50.0)
        assert apply_weather(0.4, day, profile(Environment.INDOOR)) == pytest.approx(0.4)

    def test_excess_rain_drains_before_evapotranspiration(self) -> None:
        day = DailyWeather(day=DAY1, et0_mm=3.0, rain_mm=100.0)
        assert apply_weather(0.5, day, profile()) == pytest.approx(0.9)

    def test_moisture_never_goes_below_zero(self) -> None:
        day = DailyWeather(day=DAY1, et0_mm=20.0)
        assert apply_weather(0.1, day, profile()) == 0.0

    def test_fraction_of_day_scales_et_and_rain(self) -> None:
        day = DailyWeather(day=DAY1, et0_mm=3.0, rain_mm=6.0)
        # Meio dia: +3 mm de chuva (+0,1) e -1,5 mm de ET (-0,05).
        assert apply_weather(0.5, day, profile(), fraction_of_day=0.5) == pytest.approx(0.55)

    @pytest.mark.parametrize("fraction", [-0.1, 1.1])
    def test_rejects_invalid_fraction(self, fraction: float) -> None:
        with pytest.raises(ValueError):
            apply_weather(0.5, DailyWeather(day=DAY1, et0_mm=1), profile(), fraction)


class TestSimulate:
    def test_whole_days(self) -> None:
        result = simulate(
            start_moisture=1.0,
            start=at(DAY1),
            end=at(DAY2 + timedelta(days=1)),
            profile=profile(),
            weather=weather((DAY1, 3.0, 0.0), (DAY2, 6.0, 0.0)),
        )
        assert result.moisture == pytest.approx(0.7)
        assert result.missing_weather_days == ()

    def test_partial_days_get_proportional_weather(self) -> None:
        result = simulate(
            start_moisture=1.0,
            start=at(DAY1, 12),
            end=at(DAY2, 12),
            profile=profile(),
            weather=weather((DAY1, 3.0, 0.0), (DAY2, 6.0, 0.0)),
        )
        # Meio dia com 3 mm + meio dia com 6 mm = 4,5 mm = 15%.
        assert result.moisture == pytest.approx(0.85)

    def test_zero_length_interval_keeps_moisture(self) -> None:
        result = simulate(
            start_moisture=0.42, start=at(DAY1), end=at(DAY1), profile=profile(), weather={}
        )
        assert result.moisture == pytest.approx(0.42)

    def test_watering_in_the_middle_resets_then_dries_again(self) -> None:
        result = simulate(
            start_moisture=0.2,
            start=at(DAY1),
            end=at(DAY2 + timedelta(days=1)),
            profile=profile(),
            weather=weather((DAY1, 3.0, 0.0), (DAY2, 3.0, 0.0)),
            waterings=[Watering(at=at(DAY2))],
        )
        assert result.moisture == pytest.approx(0.9)

    def test_waterings_are_applied_in_chronological_order(self) -> None:
        waterings = [Watering(at=at(DAY1, 18), amount_ml=300), Watering(at=at(DAY1, 6))]
        result = simulate(
            start_moisture=0.1,
            start=at(DAY1),
            end=at(DAY1, 18),
            profile=profile(volume=10),
            weather=weather((DAY1, 0.0, 0.0)),
            waterings=waterings,
        )
        # Rega completa às 6h (→ 1,0) e depois +300 ml, que transbordam.
        assert result.moisture == 1.0

    def test_watering_exactly_at_start_is_applied(self) -> None:
        result = simulate(
            start_moisture=0.1,
            start=at(DAY1),
            end=at(DAY1),
            profile=profile(),
            weather={},
            waterings=[Watering(at=at(DAY1))],
        )
        assert result.moisture == 1.0

    def test_waterings_outside_the_window_are_ignored(self) -> None:
        result = simulate(
            start_moisture=0.5,
            start=at(DAY1),
            end=at(DAY2),
            profile=profile(),
            weather=weather((DAY1, 0.0, 0.0)),
            waterings=[
                Watering(at=at(DAY1) - timedelta(hours=1)),
                Watering(at=at(DAY2) + timedelta(hours=1)),
            ],
        )
        assert result.moisture == pytest.approx(0.5)

    def test_missing_weather_uses_default_et0_and_is_reported(self) -> None:
        result = simulate(
            start_moisture=1.0,
            start=at(DAY1),
            end=at(DAY2 + timedelta(days=1)),
            profile=profile(),
            weather=weather((DAY1, 0.0, 0.0)),
        )
        assert result.moisture == pytest.approx(1.0 - DEFAULT_ET0_MM / 30)
        assert result.missing_weather_days == (DAY2,)

    def test_days_are_counted_in_utc(self) -> None:
        brasilia = timezone(timedelta(hours=-3))
        # 21h em Brasília do dia 20 = 00h UTC do dia 21: o dia inteiro usa o clima do dia 21.
        start = datetime(2026, 11, 20, 21, tzinfo=brasilia)
        result = simulate(
            start_moisture=1.0,
            start=start,
            end=start + timedelta(days=1),
            profile=profile(),
            weather=weather((DAY1, 30.0, 0.0), (DAY2, 3.0, 0.0)),
        )
        assert result.moisture == pytest.approx(0.9)

    def test_rejects_end_before_start(self) -> None:
        with pytest.raises(ValueError, match="end"):
            simulate(
                start_moisture=1.0, start=at(DAY2), end=at(DAY1), profile=profile(), weather={}
            )

    def test_rejects_naive_datetimes(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            simulate(
                start_moisture=1.0,
                start=datetime(2026, 11, 20),
                end=at(DAY2),
                profile=profile(),
                weather={},
            )

    def test_initial_moisture_is_clamped(self) -> None:
        result = simulate(
            start_moisture=1.7, start=at(DAY1), end=at(DAY1), profile=profile(), weather={}
        )
        assert result.moisture == 1.0

    @pytest.mark.parametrize("kc", [0.2, 0.5, 0.8, 1.2])
    def test_higher_kc_dries_faster(self, kc: float) -> None:
        def final(k: float) -> float:
            return simulate(
                start_moisture=1.0,
                start=at(DAY1),
                end=at(DAY2),
                profile=profile(kc=k),
                weather=weather((DAY1, 3.0, 0.0)),
            ).moisture

        assert final(kc) > final(kc + 0.1)


class TestValidation:
    @pytest.mark.parametrize(
        ("kc", "threshold", "volume"),
        [(0, 0.3, 1), (1.6, 0.3, 1), (1, 0, 1), (1, 1, 1), (1, 0.3, 0), (1, 0.3, -2)],
    )
    def test_profile_rejects_out_of_range_values(
        self, kc: float, threshold: float, volume: float
    ) -> None:
        with pytest.raises(ValueError):
            PlantProfile(
                kc=kc,
                drying_threshold=threshold,
                environment=Environment.INDOOR,
                pot_volume_liters=volume,
            )

    def test_weather_rejects_negative_values(self) -> None:
        with pytest.raises(ValueError):
            DailyWeather(day=DAY1, et0_mm=-1)
        with pytest.raises(ValueError):
            DailyWeather(day=DAY1, et0_mm=1, rain_mm=-1)

    def test_watering_rejects_non_positive_amount(self) -> None:
        with pytest.raises(ValueError):
            Watering(at=at(DAY1), amount_ml=0)

    def test_watering_requires_aware_datetime(self) -> None:
        with pytest.raises(ValueError):
            Watering(at=datetime(2026, 11, 20))
