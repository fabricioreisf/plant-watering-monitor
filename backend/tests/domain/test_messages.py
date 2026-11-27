from datetime import UTC, datetime

from app.domain.messages import ASK_IF_WATERED_TEXT, render_recommendation
from app.domain.recommendation import (
    Confidence,
    MoistureEstimate,
    MoistureSource,
    Recommendation,
    Urgency,
)

NOW = datetime(2026, 11, 24, 12, tzinfo=UTC)


def make(
    urgency: Urgency,
    *,
    moisture: float = 0.5,
    source: MoistureSource = MoistureSource.WATERING_LOG,
    confidence: Confidence = Confidence.MEDIUM,
    days: float | None = 3.0,
    amount: int | None = None,
    ask: bool = False,
) -> Recommendation:
    return Recommendation(
        urgency=urgency,
        estimate=MoistureEstimate(
            moisture=moisture, source=source, confidence=confidence, as_of=NOW
        ),
        drying_threshold=0.3,
        days_until_threshold=days,
        suggested_amount_ml=amount,
        ask_if_watered=ask,
    )


def test_water_now_mentions_amount_and_probable_dryness() -> None:
    text = render_recommendation(make(Urgency.WATER_NOW, moisture=0.18, amount=450, days=0))
    assert "provavelmente está seco" in text
    assert "18%" in text
    assert "30%" in text
    assert "450 ml" in text


def test_water_now_with_sensor_is_assertive() -> None:
    text = render_recommendation(
        make(
            Urgency.WATER_NOW,
            moisture=0.1,
            amount=300,
            source=MoistureSource.SENSOR,
            confidence=Confidence.HIGH,
        )
    )
    assert text.startswith("O solo está seco")
    assert "Confiança alta" in text
    assert "sensor" in text


def test_water_soon() -> None:
    text = render_recommendation(make(Urgency.WATER_SOON, moisture=0.33, amount=200, days=0.4))
    assert "próximas 24 horas" in text
    assert "200 ml" in text


def test_ok_with_days_until_next_watering() -> None:
    text = render_recommendation(make(Urgency.OK, moisture=0.8, days=4.4))
    assert "Não precisa regar agora" in text
    assert "cerca de 4 dias" in text


def test_ok_singular_day() -> None:
    assert "cerca de 1 dia." in render_recommendation(make(Urgency.OK, days=1.2))


def test_ok_beyond_projection_horizon() -> None:
    assert "mais de um mês" in render_recommendation(make(Urgency.OK, days=None))


def test_low_confidence_weather_estimate_asks_user() -> None:
    text = render_recommendation(
        make(
            Urgency.WATER_NOW,
            moisture=0.2,
            amount=400,
            source=MoistureSource.WEATHER_ESTIMATE,
            confidence=Confidence.LOW,
            ask=True,
        )
    )
    assert "Confiança baixa" in text
    assert "apenas o clima" in text
    assert text.endswith(ASK_IF_WATERED_TEXT)
