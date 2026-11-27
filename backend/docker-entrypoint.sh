#!/bin/sh
# Aplica as migrações pendentes, carrega a base curada de espécies (idempotente)
# e então inicia o comando recebido (por padrão, o uvicorn).
set -e
alembic upgrade head
python -m app.db.seed
exec "$@"
