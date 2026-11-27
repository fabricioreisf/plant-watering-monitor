import math
from datetime import UTC, date, datetime, timedelta

import pytest

from app.domain.recommendation import (
    AMOUNT_ROUNDING_ML,
    ASSUMED_INITIAL_MOISTURE,
    SENSOR_FRESHNESS,
    Confidence,
    MoistureEstimate,
    MoistureSource,
    SensorReading,
    Urgency,
    days_until_threshold,
    estimate_current_moisture,
    recommend,
    suggested_amount_ml,
)
from app.domain.water_balance import DailyWeather, Environment, PlantProfile, Watering

NOW = datetime(2026, 11, 24, 12, tzinfo=UTC)
# Vaso de π/4 L (30 mm de capacidade), Kc 1 e ET0 de 3 mm/dia → perde 10% por dia.
PROFILE = PlantProfile(
    kc=1.0, drying_threshold=0.3, environment=Environment.OUTDOOR, pot_volume_liters=math.pi / 4
)


def steady_weather(days: int = 30, et0: float = 3.0) -> dict[date, DailyWeather]:
    first = (NOW - timedelta(days=days)).date()
    return {
        first + timedelta(days=i): DailyWeather(day=first + timedelta(days=i), et0_mm=et0)
        for i in range(days + 1)
    }


def estimate(
    moisture: float, source: MoistureSource = MoistureSource.WATERING_LOG
) -> MoistureEstimate:
    return MoistureEstimate(
        moisture=moisture, source=source, confidence=Confidence.MEDIUM, as_of=NOW
    )


class TestEstimateCurrentMoisture:
    def test_without_any_data_uses_weather_only_with_low_confidence(self) -> None:
        result = estimate_current_moisture(
            profile=PROFILE,
            now=NOW,
            tracking_since=NOW - timedelta(days=1),
            weather=steady_weather(),
        )
        assert result.source is MoistureSource.WEATHER_ESTIMATE
        assert result.confidence is Confidence.LOW
        assert result.moisture == pytest.approx(ASSUMED_INITIAL_MOISTURE - 0.1)
        assert result.as_of == NOW

    def test_watering_log_anchors_the_estimate(self) -> None:
        result = estimate_current_moisture(
            profile=PROFILE,
            now=NOW,
            tracking_since=NOW - timedelta(days=10),
            weather=steady_weather(),
            waterings=[Watering(at=NOW - timedelta(days=2))],
        )
        assert result.source is MoistureSource.WATERING_LOG
        assert result.confidence is Confidence.MEDIUM
        assert result.moisture == pytest.approx(0.8)

    def test_watering_before_tracking_started_is_still_used(self) -> None:
        result = estimate_current_moisture(
            profile=PROFILE,
            now=NOW,
            tracking_since=NOW - timedelta(hours=1),
            weather=steady_weather(),
            waterings=[Watering(at=NOW - timedelta(days=3))],
        )
        assert result.moisture == pytest.approx(0.7)

    def test_sensor_reading_takes_priority_over_logs(self) -> None:
        result = estimate_current_moisture(
            profile=PROFILE,
            now=NOW,
            tracking_since=NOW - timedelta(days=10),
            weather=steady_weather(),
            waterings=[Watering(at=NOW - timedelta(days=2))],
            sensor_readings=[SensorReading(at=NOW - timedelta(hours=1), soil_moisture=0.25)],
        )
        assert result.source is MoistureSource.SENSOR
        assert result.confidence is Confidence.HIGH
        # Uma hora de evapotranspiração depois da leitura: 0,1/24.
        assert result.moisture == pytest.approx(0.25 - 0.1 / 24)

    def test_latest_sensor_reading_wins(self) -> None:
        readings = [
            SensorReading(at=NOW - timedelta(hours=2), soil_moisture=0.9),
            SensorReading(at=NOW, soil_moisture=0.4),
            SensorReading(at=NOW - timedelta(hours=1), soil_moisture=0.8),
        ]
        result = estimate_current_moisture(
            profile=PROFILE,
            now=NOW,
            tracking_since=NOW - timedelta(days=1),
            weather=steady_weather(),
            sensor_readings=readings,
        )
        assert result.moisture == pytest.approx(0.4)

    def test_watering_after_sensor_reading_is_applied(self) -> None:
        result = estimate_current_moisture(
            profile=PROFILE,
            now=NOW,
            tracking_since=NOW - timedelta(days=1),
            weather=steady_weather(),
            waterings=[Watering(at=NOW)],
            sensor_readings=[SensorReading(at=NOW - timedelta(hours=1), soil_moisture=0.2)],
        )
        assert result.source is MoistureSource.SENSOR
        assert result.moisture == 1.0

    def test_stale_sensor_reading_lowers_confidence(self) -> None:
        reading = SensorReading(at=NOW - SENSOR_FRESHNESS - timedelta(minutes=1), soil_moisture=0.6)
        result = estimate_current_moisture(
            profile=PROFILE,
            now=NOW,
            tracking_since=NOW - timedelta(days=1),
            weather=steady_weather(),
            sensor_readings=[reading],
        )
        assert result.source is MoistureSource.SENSOR
        assert result.confidence is Confidence.MEDIUM

    def test_future_data_is_ignored(self) -> None:
        result = estimate_current_moisture(
            profile=PROFILE,
            now=NOW,
            tracking_since=NOW - timedelta(days=1),
            weather=steady_weather(),
            waterings=[Watering(at=NOW + timedelta(hours=1))],
            sensor_readings=[SensorReading(at=NOW + timedelta(hours=1), soil_moisture=1.0)],
        )
        assert result.source is MoistureSource.WEATHER_ESTIMATE

    def test_missing_weather_lowers_confidence_of_log_based_estimate(self) -> None:
        result = estimate_current_moisture(
            profile=PROFILE,
            now=NOW,
            tracking_since=NOW - timedelta(days=3),
            weather={},
            waterings=[Watering(at=NOW - timedelta(days=2))],
        )
        assert result.source is MoistureSource.WATERING_LOG
        assert result.confidence is Confidence.LOW
        # De 21/11 12h a 24/11 12h: quatro dias de calendário sem clima.
        assert len(result.missing_weather_days) == 4

    def test_missing_weather_keeps_fresh_sensor_confidence(self) -> None:
        result = estimate_current_moisture(
            profile=PROFILE,
            now=NOW,
            tracking_since=NOW - timedelta(days=3),
            weather={},
            sensor_readings=[SensorReading(at=NOW - timedelta(hours=1), soil_moisture=0.5)],
        )
        assert result.confidence is Confidence.HIGH


class TestDaysUntilThreshold:
    def test_already_dry(self) -> None:
        assert days_until_threshold(0.3, PROFILE) == 0.0
        assert days_until_threshold(0.1, PROFILE) == 0.0

    def test_whole_days_with_default_weather(self) -> None:
        # 3 mm/dia é o DEFAULT_ET0_MM: 0,5 → 0,3 em 2 dias.
        assert days_until_threshold(0.5, PROFILE) == pytest.approx(2.0)

    def test_interpolates_within_the_crossing_day(self) -> None:
        assert days_until_threshold(0.45, PROFILE) == pytest.approx(1.5)

    def test_uses_forecast_before_default(self) -> None:
        forecast = [DailyWeather(day=date(2026, 11, 25), et0_mm=6.0)]
        # Primeiro dia perde 0,2 (previsão) e depois 0,1/dia.
        assert days_until_threshold(0.6, PROFILE, forecast) == pytest.approx(2.0)

    def test_forecast_rain_postpones_watering(self) -> None:
        dry = days_until_threshold(0.6, PROFILE)
        rainy = days_until_threshold(
            0.6, PROFILE, [DailyWeather(day=date(2026, 11, 25), et0_mm=3.0, rain_mm=30.0)]
        )
        assert dry is not None and rainy is not None
        assert rainy > dry

    def test_returns_none_beyond_the_projection_horizon(self) -> None:
        slow = PlantProfile(
            kc=0.1, drying_threshold=0.1, environment=Environment.INDOOR, pot_volume_liters=50
        )
        assert days_until_threshold(1.0, slow) is None


class TestSuggestedAmount:
    def test_refills_the_deficit(self) -> None:
        big = PlantProfile(
            kc=1, drying_threshold=0.3, environment=Environment.INDOOR, pot_volume_liters=10
        )
        # Capacidade de 3000 ml; metade vazia = 1500 ml.
        assert suggested_amount_ml(0.5, big) == 1500

    def test_rounds_up(self) -> None:
        big = PlantProfile(
            kc=1, drying_threshold=0.3, environment=Environment.INDOOR, pot_volume_liters=10
        )
        assert suggested_amount_ml(0.49, big) == 1550

    def test_never_suggests_less_than_the_rounding_step(self) -> None:
        assert suggested_amount_ml(0.999, PROFILE) == AMOUNT_ROUNDING_ML


class TestRecommend:
    def test_water_now_at_or_below_threshold(self) -> None:
        result = recommend(PROFILE, estimate(0.2))
        assert result.urgency is Urgency.WATER_NOW
        assert result.days_until_threshold == 0.0
        assert result.suggested_amount_ml is not None
        assert result.ask_if_watered is False

    def test_asks_if_watered_when_probably_dry_without_logs(self) -> None:
        result = recommend(PROFILE, estimate(0.2, MoistureSource.WEATHER_ESTIMATE))
        assert result.ask_if_watered is True

    def test_does_not_ask_when_sensor_says_dry(self) -> None:
        result = recommend(PROFILE, estimate(0.2, MoistureSource.SENSOR))
        assert result.ask_if_watered is False

    def test_water_soon_when_threshold_is_hit_within_a_day(self) -> None:
        result = recommend(PROFILE, estimate(0.35))
        assert result.urgency is Urgency.WATER_SOON
        assert result.days_until_threshold == pytest.approx(0.5)
        assert result.suggested_amount_ml is not None

    def test_ok_when_there_is_time(self) -> None:
        result = recommend(PROFILE, estimate(0.9))
        assert result.urgency is Urgency.OK
        assert result.days_until_threshold == pytest.approx(6.0)
        assert result.suggested_amount_ml is None
        assert result.ask_if_watered is False

    def test_does_not_ask_when_not_dry(self) -> None:
        result = recommend(PROFILE, estimate(0.9, MoistureSource.WEATHER_ESTIMATE))
        assert result.ask_if_watered is False


class TestSensorReading:
    @pytest.mark.parametrize("value", [-0.01, 1.01])
    def test_rejects_out_of_range(self, value: float) -> None:
        with pytest.raises(ValueError):
            SensorReading(at=NOW, soil_moisture=value)
