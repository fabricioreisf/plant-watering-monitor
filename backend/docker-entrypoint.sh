#!/bin/sh
# Aplica as migrações pendentes e então inicia o comando recebido (por padrão, o uvicorn).
set -e
alembic upgrade head
exec "$@"
