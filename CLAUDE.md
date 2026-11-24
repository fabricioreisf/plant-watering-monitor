# Monitor de Plantas

Sistema que recomenda **quando e como regar** cada planta do usuário, combinando clima real, registros opcionais de rega, uma base de conhecimento de plantas e sensores de umidade do solo (simulados no MVP, com estrutura pronta para um ESP32 real).

Projeto de portfólio: priorize código limpo, testado e bem documentado em vez de muitas funcionalidades.

## Stack

| Camada | Tecnologia |
| --- | --- |
| Backend | Python 3.12, FastAPI, Pydantic, SQLAlchemy 2 + Alembic, aiomqtt |
| Frontend | React + TypeScript (Vite) |
| Banco | PostgreSQL + extensão TimescaleDB |
| Mensageria | Mosquitto (MQTT) + WebSocket (FastAPI) |
| Clima | Open-Meteo (sem chave) |
| Plantas | Base curada própria + Perenual (com cache) |
| Testes / CI | pytest, GitHub Actions |
| Infra | Docker Compose |

## Estrutura (monorepo)

```
backend/      FastAPI, domínio, balanço hídrico, testes
frontend/     React + TypeScript
simulator/    sensor simulado publicando via MQTT
firmware/     (futuro) ESP32 — não implementar agora
infra/        config do Mosquitto, scripts de backup, seeds
docs/         arquitetura, contrato MQTT, decisões (ADRs)
.github/workflows/
docker-compose.yml
.env.example
```

## Requisitos funcionais

1. Cadastro e login de usuário.
2. Cadastro de plantas: espécie, apelido, ambiente (`indoor` | `outdoor`), localização (lat/lon) e tamanho do vaso.
3. Registro **opcional** de rega: data/hora e quantidade aproximada. O sistema deve funcionar sem nenhum registro.
4. Coleta periódica de clima (Open-Meteo) por localização: ET₀ (`et0_fao_evapotranspiration`), chuva, temperatura e umidade.
5. Estimativa diária da umidade do vaso (balanço hídrico) e recomendação de quando e como regar.
6. Dispositivos (sensores) vinculados a plantas; leitura de sensor, quando existe, substitui a estimativa.
7. Dashboard com estado de cada planta e leituras ao vivo via WebSocket.

## Requisitos não funcionais

- Autorização por recurso: um usuário só lê/altera as próprias plantas, registros e dispositivos.
- Autenticação JWT (access + refresh), senhas com hash (argon2 ou bcrypt).
- Mosquitto com TLS e usuário/senha por dispositivo; sem acesso anônimo.
- Log de auditoria (quem, o quê, quando) para ações de escrita.
- Script de backup do banco em `infra/`.
- Nenhum segredo no repositório: usar `.env` (fora do git) e manter `.env.example` atualizado.
- Exibir "Weather data by Open-Meteo.com" na interface (licença CC BY 4.0).
- README deve deixar claro o que é dado real e o que é simulado.

## Contrato MQTT (estável — o ESP32 real usará o mesmo)

- Tópico: `devices/{device_id}/telemetry`
- Payload JSON:
  ```json
  { "soil_moisture": 0.42, "temperature": 24.1, "timestamp": "2026-11-24T10:00:00Z" }
  ```
  `soil_moisture` entre 0 e 1. Validar com Pydantic; mensagens inválidas são descartadas e registradas em log.
- O simulador deve publicar **exatamente** nesse formato. Documentar em `docs/mqtt-contract.md`.

## Modelo de domínio (balanço hídrico)

- Cada planta tem uma umidade estimada do vaso (0 a 1).
- Sobe com rega registrada e com chuva (somente `outdoor`).
- Cai com evapotranspiração: `ET_planta = Kc * ET0`, com fator de redução adicional para `indoor`.
- A espécie define `Kc` e o limite de secagem que dispara a recomendação.
- Prioridade das fontes: leitura de sensor > registro do usuário > estimativa por clima. A recomendação informa o nível de confiança conforme a fonte usada.
- Sem registro e com estimativa "provavelmente seco", o sistema pode perguntar ao usuário se ele regou; a resposta vira um novo registro.
- Implementar o balanço hídrico como **funções puras**, sem I/O, com testes unitários extensos.

## Base de conhecimento

- Interface `KnowledgeProvider` no domínio; implementações em adaptadores.
- Fonte principal: tabela curada própria (seed) com 20 a 30 plantas comuns: nome popular em português, nome científico, `Kc`, limite de secagem, instruções de rega.
- Perenual como enriquecimento: plano gratuito tem 100 requisições/dia, apenas espécies de ID 1 a 3000, uso não comercial. Cache persistente obrigatório.
- Chave de espécie = nome científico. Dados da Perenual chegam em inglês: o adaptador converte valores categóricos (`frequent`, `average`, `minimum`, `full_sun`, `part_shade`...) em códigos internos do domínio. O resto do sistema nunca vê o formato da API externa (anti-corruption layer). Textos ao usuário são em português, gerados por templates a partir dos dados estruturados.

## Banco de dados

- Tabelas relacionais: users, plants, species, watering_logs, devices, audit_log.
- Hypertables Timescale: sensor_readings, weather_readings.
- Migrações com Alembic.

## Fases de implementação

Implemente **uma fase por vez** e pare ao fim de cada uma para revisão.

1. **Esqueleto:** estrutura de pastas, docker-compose (Postgres/Timescale, Mosquitto, backend), backend FastAPI com healthcheck, Alembic, CI rodando pytest e lint (ruff).
2. **Núcleo:** modelos, auth JWT, CRUD de plantas e registros de rega com autorização por recurso, seed de espécies, balanço hídrico com testes.
3. **Clima:** cliente Open-Meteo com job periódico e persistência; recomendação usando dados reais.
4. **IoT:** simulador MQTT, serviço de ingestão, TLS/credenciais no Mosquitto, WebSocket de leituras ao vivo.
5. **Frontend:** login, lista de plantas, detalhe com gráfico e recomendação, leituras ao vivo.
6. **Governança e acabamento:** auditoria, backup, integração Perenual com cache, README com diagrama de arquitetura.

## Convenções

- Código e nomes em inglês; textos de interface e documentação em português.
- Type hints em todo o backend; ruff para lint e formatação.
- Commits pequenos com mensagens descritivas.
- Não implementar nada fora da fase atual sem perguntar.