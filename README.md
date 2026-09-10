# connection-service

Serviço centralizado para entrega de conexões Oracle criptografadas.

Robôs/aplicações autenticados recebem a string de conexão cifrada com **Fernet (AES-128-CBC + HMAC-SHA256)**, garantindo que nenhuma credencial do banco de dados (Oracle pro exemplo) trafegue em texto puro entre sistemas.

---

## Sumário

- [Objetivo](#objetivo)
- [Arquitetura](#arquitetura)
- [Tecnologias](#tecnologias)
- [Variáveis de Ambiente](#variáveis-de-ambiente)
- [Instalação Local](#instalação-local)
- [Execução Local](#execução-local)
- [Execução com Docker](#execução-com-docker)
- [Fluxo de Autenticação](#fluxo-de-autenticação)
- [Fluxo de Autorização](#fluxo-de-autorização)
- [Fluxo de Criptografia](#fluxo-de-criptografia)
- [Auditoria](#auditoria)
- [Rate Limiting](#rate-limiting)
- [Endpoints](#endpoints)
- [Exemplos de Requisição](#exemplos-de-requisição)
- [Segurança](#segurança)

---

## Objetivo

Centralizar e proteger as credenciais de conexão dos bancos utilizados pelos robôs/aplicações da organização.

**Problemas resolvidos:**

- Robôs/aplicações não armazenam localmente nenhuma credencial de banco de dados
- Toda conexão é entregue criptografada — nunca em texto puro
- Toda solicitação é auditada com IP, status e motivo
- Controle de acesso por ambiente (DEV / HOM / PROD) por robô/aplicação
- Rate limiting para proteção contra abuso. O ideal é a aplicação fazer a busca e utilizar o resultado obtido evitando abrir muitas conexões

---

## Arquitetura

```
connection-service/
├── app/
│   ├── main.py               # Ponto de entrada, configuração FastAPI
│   ├── config.py             # Settings (pydantic-settings, .env)
│   ├── database.py           # Engine SQLite, sessões SQLAlchemy
│   ├── auth.py               # Validação de robot_name + api_key + ambiente
│   ├── crypto.py             # Criptografia/descriptografia Fernet
│   ├── middleware.py         # Logging de request/response + Correlation ID
│   ├── exceptions.py         # Exceções de domínio + handlers globais
│   ├── models.py             # ORM — tabela audit_log
│   ├── schemas.py            # Schemas Pydantic (request/response)
│   ├── routes/
│   │   ├── connection.py     # POST /api/v1/connection
│   │   └── health.py         # GET /health
│   ├── services/
│   │   ├── auth_service.py       # Orquestra autenticação/autorização
│   │   ├── audit_service.py      # Registra auditoria
│   │   └── connection_service.py # Fluxo completo de entrega de conexão
│   └── repositories/
│       └── audit_repository.py   # Persistência do audit_log
├── logs/                     # Logs rotativos da aplicação
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── .gitignore
```

### Camadas

| Camada | Responsabilidade |
|---|---|
| **Routes** | Recebe HTTP, valida entrada (Pydantic), chama serviços |
| **Services** | Orquestra regras de negócio |
| **Repositories** | Acesso exclusivo ao banco de dados |
| **Models** | Mapeamento ORM das tabelas |
| **Schemas** | Contratos de entrada/saída da API |

---

## Tecnologias

| Tecnologia | Versão | Uso |
|---|---|---|
| Python | 3.12 | Runtime |
| FastAPI | 0.115 | Framework HTTP |
| Uvicorn | 0.30 | Servidor ASGI |
| SQLAlchemy | 2.0 | ORM / banco de auditoria |
| SQLite | — | Banco de auditoria |
| Pydantic | 2.9 | Validação de dados |
| pydantic-settings | 2.5 | Configuração via .env |
| cryptography (Fernet) | 43.0 | Criptografia das conexões |
| SlowAPI | 0.1.9 | Rate limiting |
| python-dotenv | 1.0 | Carregamento do .env |
| oracledb | 2.4 | Cliente Oracle (nos robôs) |

---

## Variáveis de Ambiente

Copie `.env.example` para `.env` e preencha os valores:

```bash
cp .env.example .env
```

### Gerar FERNET_KEY

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Gerar API Keys para os robôs

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Referência completa

| Variável | Obrigatória | Descrição |
|---|---|---|
| `FERNET_KEY` | ✅ | Chave Fernet para criptografar conexões |
| `SQLITE_DATABASE_URL` | — | URL do SQLite (padrão: `sqlite:///./audit.db`) |
| `ROBOTS` | ✅ | Lista de robôs separados por vírgula |
| `ROBO_FINANCEIRO_API_KEY` | ✅ | API Key do robo-financeiro |
| `ROBO_FISCAL_API_KEY` | ✅ | API Key do robo-fiscal |
| `ROBO_RH_API_KEY` | ✅ | API Key do robo-rh |
| `ROBO_FINANCEIRO_ALLOWED_ENVS` | ✅ | Ambientes permitidos: ex. `DEV,HOM` |
| `ROBO_FISCAL_ALLOWED_ENVS` | ✅ | Ambientes permitidos: ex. `DEV,HOM,PROD` |
| `ROBO_RH_ALLOWED_ENVS` | ✅ | Ambientes permitidos: ex. `DEV` |
| `DB_DEV_HOST` | ✅ | Host Oracle DEV |
| `DB_DEV_PORT` | — | Porta Oracle DEV (padrão: 1521) |
| `DB_DEV_SERVICE_NAME` | ✅ | Service Name Oracle DEV |
| `DB_DEV_USER` | ✅ | Usuário Oracle DEV |
| `DB_DEV_PASSWORD` | ✅ | Senha Oracle DEV |
| `DB_HOM_*` | ✅ | Mesma estrutura para HOM |
| `DB_PROD_*` | ✅ | Mesma estrutura para PROD |
| `RATE_LIMIT_PER_MINUTE` | — | Req/min por IP (padrão: 20) |
| `LOG_LEVEL` | — | Nível de log (padrão: INFO) |

> **Nunca versione o arquivo `.env`**. Ele está no `.gitignore`.

---

## Instalação Local

### Pré-requisitos

- Python 3.12+
- pip

### Passos

```bash
# 1. Clone ou acesse o diretório do projeto
cd connection-service

# 2. Crie o ambiente virtual
python -m venv .venv

# 3. Ative o ambiente virtual
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# Linux / macOS
source .venv/bin/activate

# 4. Instale as dependências
pip install -r requirements.txt

# 5. Configure as variáveis de ambiente
cp .env.example .env
# Edite o .env com seus valores reais
```

---

## Execução Local

```bash
# Com uvicorn diretamente (recomendado para desenvolvimento)
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

# Ou via Python
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

A API estará disponível em:
- **API:** http://localhost:8080
- **Documentação Swagger:** http://localhost:8080/docs
- **Documentação Redoc:** http://localhost:8080/redoc
- **Health Check:** http://localhost:8080/health

---

## Execução com Docker

### Build e start

```bash
# Certifique-se de ter o .env configurado
cp .env.example .env

# Build e inicialização
docker compose up --build

# Em background
docker compose up --build -d
```

### Comandos úteis

```bash
# Acompanhar logs em tempo real
docker compose logs -f

# Parar o serviço
docker compose down

# Parar e remover volumes (apaga banco de auditoria!)
docker compose down -v

# Restartar apenas o serviço
docker compose restart connection-service

# Verificar status
docker compose ps
```

### Volumes persistidos

| Volume | Destino no container | Conteúdo |
|---|---|---|
| `sqlite_data` | `/app/audit.db` | Banco SQLite de auditoria |
| `./logs` | `/app/logs` | Arquivos de log rotativos |

---

## Fluxo de Autenticação

```
Robô
 │
 ├─ Envia: robot_name + api_key + environment
 │
 ▼
connection-service
 │
 ├─ 1. Verifica se robot_name está em ROBOTS
 │      └─ Não encontrado → HTTP 401 (ROBOT_NOT_FOUND)
 │
 ├─ 2. Busca {ROBOT_NAME}_API_KEY nas variáveis de ambiente
 │      └─ Não configurada → HTTP 401 (INVALID_API_KEY)
 │
 ├─ 3. Compara api_key recebida com a esperada
 │      (comparação em tempo constante — sem timing attack)
 │      └─ Divergente → HTTP 401 (INVALID_API_KEY)
 │
 └─ 4. Autenticação aprovada → segue para autorização
```

**A comparação usa `hmac.compare_digest` para evitar timing attacks.**

---

## Fluxo de Autorização

```
Autenticação aprovada
 │
 ├─ Busca {ROBOT_NAME}_ALLOWED_ENVS nas variáveis de ambiente
 │
 ├─ Verifica se o ambiente solicitado está na lista permitida
 │      └─ Não está → HTTP 403 (ENVIRONMENT_NOT_ALLOWED)
 │
 └─ Autorizado → segue para montagem da conexão

Exemplo de configuração:
  robo-financeiro: ROBO_FINANCEIRO_ALLOWED_ENVS=DEV,HOM
    DEV  → ✅ permitido
    HOM  → ✅ permitido
    PROD → ❌ HTTP 403

  robo-fiscal: ROBO_FISCAL_ALLOWED_ENVS=DEV,HOM,PROD
    DEV  → ✅ permitido
    HOM  → ✅ permitido
    PROD → ✅ permitido
```

---

## Fluxo de Criptografia

```
1. Autenticação e autorização aprovadas
        │
2. Busca credenciais Oracle do ambiente nas variáveis de ambiente
        │
3. Monta dicionário de conexão:
        {
          "host": "oracle-dev",
          "port": 1521,
          "service_name": "DEVDB",
          "user": "usuario",
          "password": "senha"
        }
        │
4. Serializa para JSON (json.dumps)
        │
5. Criptografa com Fernet.encrypt()
        │
6. Retorna APENAS o token criptografado:
        {
          "success": true,
          "environment": "DEV",
          "encrypted_connection": "gAAAAABXXX..."
        }

O robô descriptografa localmente com sua FERNET_KEY:
        │
7. Fernet.decrypt(token) → JSON → dict
        │
8. oracledb.connect(user=..., password=..., host=..., ...)
```

**Nunca são retornados em texto puro: host, user, password, service_name.**

---

## Auditoria

Toda requisição — com sucesso ou falha — é registrada na tabela `audit_log` do SQLite.

### Estrutura da tabela

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | INTEGER PK | Identificador único |
| `robot_name` | VARCHAR(100) | Nome do robô |
| `environment` | VARCHAR(10) | Ambiente: DEV/HOM/PROD |
| `request_ip` | VARCHAR(45) | IP do cliente (IPv4/IPv6) |
| `request_date` | DATETIME | Data/hora UTC da requisição |
| `status` | VARCHAR(20) | SUCCESS ou DENIED |
| `reason` | VARCHAR(100) | Código descritivo do resultado |
| `correlation_id` | VARCHAR(36) | ID de correlação para rastreamento |

### Códigos de reason

| Reason | Descrição |
|---|---|
| `AUTHORIZED` | Conexão entregue com sucesso |
| `ROBOT_NOT_FOUND` | Robô não está registrado |
| `INVALID_API_KEY` | API Key inválida ou ausente |
| `ENVIRONMENT_NOT_ALLOWED` | Ambiente não autorizado para o robô |
| `INTERNAL_ERROR` | Erro interno durante o processamento |

### Exemplos de registros

**Sucesso:**
```
robot_name: robo-financeiro | environment: DEV | ip: 10.42.10.15
status: SUCCESS | reason: AUTHORIZED
```

**Negado — ambiente não permitido:**
```
robot_name: robo-financeiro | environment: PROD | ip: 10.42.10.15
status: DENIED | reason: ENVIRONMENT_NOT_ALLOWED
```

**Negado — API Key inválida:**
```
robot_name: robo-fiscal | environment: HOM | ip: 10.42.10.20
status: DENIED | reason: INVALID_API_KEY
```

---

## Rate Limiting

Implementado via **SlowAPI**. Por padrão: **20 requisições por minuto por IP**.

Configure via variável de ambiente:
```env
RATE_LIMIT_PER_MINUTE=20
```

Ao exceder o limite:
```json
HTTP 429 Too Many Requests
{
  "success": false,
  "message": "Too many requests. Please try again later."
}
```

---

## Endpoints

### POST /api/v1/connection

Solicita uma conexão Oracle criptografada.

**Request:**
```json
{
  "robot_name": "robo-financeiro",
  "api_key": "sua-api-key",
  "environment": "DEV"
}
```

**Response 200 — Sucesso:**
```json
{
  "success": true,
  "environment": "DEV",
  "encrypted_connection": "gAAAAABXXXXXXXXXXXXXXXXXX..."
}
```

**Response 401 — Não autorizado:**
```json
{
  "success": false,
  "message": "Robot not authorized"
}
```

**Response 403 — Ambiente não permitido:**
```json
{
  "success": false,
  "message": "Environment not allowed for this robot"
}
```

**Response 429 — Rate limit:**
```json
{
  "success": false,
  "message": "Too many requests. Please try again later."
}
```

**Response 500 — Erro interno:**
```json
{
  "success": false,
  "message": "Internal error"
}
```

---

### GET /health

Verifica se o serviço está ativo.

**Response 200:**
```json
{
  "status": "UP"
}
```

---

## Exemplos de Requisição

### curl

```bash
curl -X POST http://localhost:8080/api/v1/connection \
  -H "Content-Type: application/json" \
  -d '{
    "robot_name": "robo-financeiro",
    "api_key": "sua-api-key",
    "environment": "DEV"
  }'
```

### Python (requests)

```python
import requests

response = requests.post(
    "http://localhost:8080/api/v1/connection",
    json={
        "robot_name": "robo-financeiro",
        "api_key": "sua-api-key",
        "environment": "DEV",
    },
)

data = response.json()
encrypted_connection = data["encrypted_connection"]
```

---

## Segurança

| Controle | Implementação |
|---|---|
| Autenticação | API Key por robô via variável de ambiente |
| Comparação segura | `hmac.compare_digest` (sem timing attack) |
| Autorização | Lista de ambientes permitidos por robô |
| Criptografia | Fernet (AES-128-CBC + HMAC-SHA256) |
| Validação de entrada | Pydantic com type hints e field validators |
| Rate limiting | SlowAPI — 20 req/min por IP |
| Auditoria | 100% das requisições registradas no SQLite |
| Logging | Logs estruturados com Correlation ID |
| Erros | Handler global — nunca expõe stacktrace ou paths internos |
| Container | Usuário não-root no Docker |
| Credenciais | Nunca retornadas em texto puro |

---

## Estrutura do .env (resumo)

```env
FERNET_KEY=<gere com Fernet.generate_key()>
SQLITE_DATABASE_URL=sqlite:///./audit.db
ROBOTS=robo-financeiro,robo-fiscal,robo-rh

ROBO_FINANCEIRO_API_KEY=<token seguro>
ROBO_FISCAL_API_KEY=<token seguro>
ROBO_RH_API_KEY=<token seguro>

ROBO_FINANCEIRO_ALLOWED_ENVS=DEV,HOM
ROBO_FISCAL_ALLOWED_ENVS=DEV,HOM,PROD
ROBO_RH_ALLOWED_ENVS=DEV

DB_DEV_HOST=oracle-dev.internal
DB_DEV_PORT=1521
DB_DEV_SERVICE_NAME=DEVDB
DB_DEV_USER=dev_user
DB_DEV_PASSWORD=<senha>
# ... HOM e PROD seguem o mesmo padrão
```
