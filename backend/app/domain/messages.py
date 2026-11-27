"""Textos em português gerados por templates a partir dos dados estruturados do domínio."""

from app.domain.recommendation import Confidence, MoistureSource, Recommendation, Urgency

_SOURCE_TEXT = {
    MoistureSource.SENSOR: "leitura do sensor",
    MoistureSource.WATERING_LOG: "seus registros de rega e o clima",
    MoistureSource.WEATHER_ESTIMATE: "apenas o clima, sem registros de rega",
}

_CONFIDENCE_TEXT = {
    Confidence.HIGH: "alta",
    Confidence.MEDIUM: "média",
    Confidence.LOW: "baixa",
}

ASK_IF_WATERED_TEXT = "Você regou esta planta recentemente? Registrar a rega melhora a estimativa."


def percent(fraction: float) -> str:
    return f"{round(fraction * 100)}%"


def render_recommendation(recommendation: Recommendation) -> str:
    estimate = recommendation.estimate
    moisture = percent(estimate.moisture)
    threshold = percent(recommendation.drying_threshold)
    amount = recommendation.suggested_amount_ml

    match recommendation.urgency:
        case Urgency.WATER_NOW:
            state = (
                "O solo está seco"
                if estimate.source is MoistureSource.SENSOR
                else "O vaso provavelmente está seco"
            )
            main = (
                f"{state} (umidade {moisture}, limite {threshold}). "
                f"Regue agora com cerca de {amount} ml."
            )
        case Urgency.WATER_SOON:
            main = (
                f"Regue nas próximas 24 horas: a umidade ({moisture}) está chegando ao limite "
                f"de {threshold}. Use cerca de {amount} ml."
            )
        case Urgency.OK:
            main = f"Não precisa regar agora (umidade {moisture}). {_next_watering(recommendation)}"

    confidence = _CONFIDENCE_TEXT[estimate.confidence]
    parts = [main, f"Confiança {confidence}: baseada em {_SOURCE_TEXT[estimate.source]}."]
    if recommendation.ask_if_watered:
        parts.append(ASK_IF_WATERED_TEXT)
    return " ".join(parts)


def _next_watering(recommendation: Recommendation) -> str:
    days = recommendation.days_until_threshold
    if days is None:
        return "A próxima rega deve demorar mais de um mês."
    whole_days = round(days)
    if whole_days <= 1:
        return "A próxima rega deve ser em cerca de 1 dia."
    return f"A próxima rega deve ser em cerca de {whole_days} dias."
