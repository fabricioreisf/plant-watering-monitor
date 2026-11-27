# Backend

API FastAPI do Monitor de Plantas. Veja o [README principal](../README.md) para subir tudo com Docker.

## Organização

```
app/
  api/        rotas HTTP e dependências (autenticação, autorização por recurso)
  core/       configuração e segurança (argon2, JWT)
  db/         engine/sessões, base declarativa, seed de espécies
  domain/     balanço hídrico e recomendação — funções puras, sem I/O
  models/     modelos ORM (SQLAlchemy 2)
  schemas/    contratos de entrada e saída (Pydantic)
alembic/      migrações
tests/
  domain/     testes unitários do domínio (não precisam de banco)
  api/        testes de API contra um PostgreSQL real
```

## Desenvolvimento local

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
ruff check . && ruff format --check .
```

### Testes

Os testes de domínio e segurança rodam sem nada além do Python. Os testes de API precisam de um
PostgreSQL indicado por `TEST_DATABASE_URL`; o nome do banco precisa terminar em `_test`, porque as
tabelas são recriadas a cada execução. Sem a variável, esses testes são **pulados** (o `pytest -rs`
mostra quantos).

```bash
docker compose up -d db
docker compose exec db sh -c 'createdb -U "$POSTGRES_USER" "${POSTGRES_DB}_test"'
export TEST_DATABASE_URL=postgresql+psycopg://plants:<senha>@127.0.0.1:5432/plants_test
pytest -rs
```

Use `127.0.0.1` em vez de `localhost`: no Windows, `localhost` tenta primeiro IPv6 (`::1`), e o
Docker publica as portas só em IPv4, o que faz a primeira conexão esperar um timeout.

### Rodar a API fora do Docker

```bash
alembic upgrade head
python -m app.db.seed            # base curada de espécies; idempotente
uvicorn app.main:app --reload
```

No Windows, o psycopg assíncrono não funciona com o event loop padrão (Proactor). Inicie o
uvicorn com o loop compatível:

```bash
uvicorn app.main:app --reload --loop app.db.session:event_loop_factory
```

## Endpoints

| Rota | Descrição |
| --- | --- |
| `GET /health` | Liveness: o processo está no ar. |
| `GET /health/ready` | Readiness: o banco responde (`503` se não). |
| `POST /auth/register` | Cadastro (`email`, `password` com 8 a 128 caracteres). |
| `POST /auth/login` | Formulário OAuth2 (`username` = e-mail). Retorna access e refresh tokens. |
| `POST /auth/refresh` | Troca um refresh token por um novo par de tokens. |
| `GET /users/me` | Usuário autenticado. |
| `GET /species`, `GET /species/{id}` | Catálogo público de espécies (`?q=` busca por nome). |
| `GET/POST /plants`, `GET/PATCH/DELETE /plants/{id}` | Plantas do usuário autenticado. |
| `GET/POST /plants/{id}/waterings`, `DELETE /plants/{id}/waterings/{log_id}` | Registros de rega. |
| `GET /docs` | Documentação OpenAPI interativa (o botão *Authorize* usa o login acima). |

Recursos de outro usuário respondem `404`, como se não existissem, para não revelar ids válidos.

## Autenticação

- Senhas com hash **argon2** (`argon2-cffi`). O login gasta o mesmo tempo de verificação quando o
  e-mail não existe, para não revelar quais e-mails têm conta.
- **JWT HS256** com claim `type`: o access token (15 min) não é aceito como refresh e vice-versa.
  O segredo vem de `JWT_SECRET_KEY` (mínimo de 32 caracteres, sem valor padrão).
- Limitação conhecida: os refresh tokens são *stateless*. Não há revogação nem logout no servidor;
  um token vazado vale até expirar (7 dias). Uma tabela de tokens com rotação resolveria isso.

## Balanço hídrico (`app/domain`)

A umidade do vaso é uma fração de 0 a 1 da água disponível que o substrato retém: 1 logo após uma
rega completa, 0 quando a planta não consegue mais extrair água.

- **Perda diária:** `ET_planta = Kc × ET0`, multiplicada por 0,5 em ambiente `indoor`.
- **Ganho:** rega registrada (quantidade em ml, ou "rega completa" quando a quantidade fica vazia)
  e chuva, esta só para plantas `outdoor`. O excesso drena.
- **Capacidade do vaso:** o vaso é tratado como um cilindro com altura igual ao diâmetro, e 30% do
  volume do substrato fica disponível para a planta. Um vaso de 2 L retém cerca de 41 mm de água,
  ou 600 ml.
- **Fontes, em ordem de prioridade:** leitura de sensor (confiança alta, ou média se tiver mais de
  6 h), registro de rega (média) e estimativa só pelo clima (baixa). Quando não há registro e a
  estimativa diz "provavelmente seco", a recomendação pede ao usuário que confirme se regou.
- **Recomendação:** "regar agora" no limite de secagem da espécie ou abaixo dele; "regar em breve"
  se o limite deve ser atingido em até 24 h; senão, informa em quantos dias será a próxima rega. A
  quantidade sugerida leva o vaso de volta à capacidade, arredondada para múltiplos de 50 ml.

As constantes (fração de água disponível, fator `indoor`, ET0 padrão quando falta clima) são
aproximações documentadas em [`water_balance.py`](app/domain/water_balance.py). Os valores de `Kc`
e o limite de secagem de cada espécie em [`species.json`](app/db/seeds/species.json) são
estimativas baseadas em coeficientes de paisagismo e recomendações gerais de cultivo, não medições.
