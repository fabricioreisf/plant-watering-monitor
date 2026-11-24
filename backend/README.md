# Backend

API FastAPI do Monitor de Plantas. Veja o [README principal](../README.md) para subir tudo com Docker.

## Desenvolvimento local

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

ruff check . && ruff format --check .
pytest
```

Rodar a API fora do Docker (requer um Postgres acessível em `DATABASE_URL`):

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

## Endpoints

| Rota | Descrição |
| --- | --- |
| `GET /health` | Liveness: o processo está no ar. |
| `GET /health/ready` | Readiness: o banco responde (`503` se não). |
| `GET /docs` | Documentação OpenAPI interativa. |
