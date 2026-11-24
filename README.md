# Monitor de Plantas

Sistema que recomenda **quando e como regar** cada planta, combinando clima real, registros
opcionais de rega, uma base de conhecimento de plantas e sensores de umidade do solo.

> **Status:** fase 1 (esqueleto) — infraestrutura, API com healthcheck, migrações e CI.
> Ainda não há funcionalidades de domínio.

## O que é real e o que é simulado

| Componente | Situação |
| --- | --- |
| Clima (Open-Meteo) | Real — a partir da fase 3 |
| Sensores de umidade | **Simulados** (fase 4); o contrato MQTT é o mesmo que um ESP32 real usará |
| Base de plantas | Curada no próprio projeto + Perenual (fase 6) |

## Estrutura

```
backend/      FastAPI, domínio, balanço hídrico, testes
frontend/     React + TypeScript (fase 5)
simulator/    sensor simulado publicando via MQTT (fase 4)
firmware/     ESP32 — futuro, fora do MVP
infra/        configuração do Mosquitto, backup, seeds
docs/         arquitetura, contrato MQTT, ADRs
```

## Como rodar

Pré-requisito: Docker com Compose v2.

```bash
cp .env.example .env    # ajuste POSTGRES_PASSWORD
docker compose up --build
```

Serviços (expostos apenas em `127.0.0.1`):

| Serviço | Endereço |
| --- | --- |
| API | http://localhost:8000 — docs em `/docs` |
| Healthcheck | `GET /health` (processo) e `GET /health/ready` (banco) |
| PostgreSQL + TimescaleDB | `localhost:5432` |
| Mosquitto | `localhost:1883` — recusa conexões até a fase 4 (sem acesso anônimo) |

O container do backend aplica as migrações (`alembic upgrade head`) antes de iniciar a API.

Para desenvolver o backend sem Docker, veja [`backend/README.md`](backend/README.md).

## CI

O GitHub Actions ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) roda:

- **ruff** (lint e formatação) e **pytest** no backend;
- as migrações contra um TimescaleDB real (upgrade → downgrade → upgrade e `alembic check`);
- validação do `docker-compose.yml` e build da imagem do backend.
