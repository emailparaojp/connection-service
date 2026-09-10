# connection-service

Serviço centralizado para entrega de conexões Oracle criptografadas.

Sistemas e robôs autenticados recebem a string de conexão cifrada com **Fernet (AES-128-CBC + HMAC-SHA256)**, garantindo que nenhuma credencial Oracle trafegue em texto puro entre aplicações.

---

## Sumário

- [Objetivo](#objetivo)
- [Arquitetura](#arquitetura)
- [Tecnologias](#tecnologias)
- [Variáveis de Ambiente](#variáveis-de-ambiente)
- [Conexões por Sistema](#conexões-por-sistema)
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
- [Como Descriptografar](#como-descriptografar)
- [Segurança](#segurança)

---

## Objetivo

Centralizar e proteger as credenciais de conexão dos bancos Oracle utilizados pelos sistemas e robôs da organização.

**Problemas resolvidos:**

- Sistemas não armazenam localmente nenhuma credencial Oracle
- Toda conexão é entregue criptografada — nunca em texto puro
- Toda solicitação é auditada com IP, status e motivo
- Controle de acesso por ambiente (DEV / HOM / PROD) por sistema
- Cada sistema pode ter sua própria conexão Oracle ou compartilhar a global
- Rate limiting para proteção contra abuso

> **Recomendação:** a aplicação cliente deve solicitar a conexão uma única vez, armazenar em memória e reutilizá-la durante sua execução, evitando abrir múltiplas requisições ao serviço.

---

## Arquitetura

```
connection-service/
├── app/
│   ├── main.py               # Ponto de entrada, fábrica FastAPI, ciclo de vida
│   ├── config.py             # Configurações (pydantic-settings, .env)
│   ├── database.py           # Engine SQLite, sessões SQLAlchemy
│   ├── auth.py               # Validação de nm_sistema + chave_api + ambiente
│   ├── crypto.py             # Criptografia/descriptografia Fernet
│   ├── middleware.py         # Logging de requisição/resposta + ID de Correlação
│   ├── exceptions.py         # Exceções de domínio + handlers globais
│   ├── models.py             # ORM — tabela TB_AUDITORIA
│   ├── schemas.py            # Schemas Pydantic (requisição/resposta)
│   ├── routes/
│   │   ├── connection.py     # POST /api/v1/conexao
│   │   └── health.py         # GET /health
│   ├── services/
│   │   ├── auth_service.py       # Orquestra autenticação/autorização
│   │   ├── audit_service.py      # Registra auditoria
│   │   └── connection_service.py # Fluxo completo de entrega de conexão
│   └── repositories/
│       └── audit_repository.py   # Persistência da TB_AUDITORIA
├── logs/                     # Logs rotativos da aplicação
├── robot_client_example.py   # Exemplo completo de sistema cliente
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
| oracledb | 2.4 | Cliente Oracle (nos sistemas clientes) |

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

### Gerar chaves de API para os sistemas

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Referência completa

| Variável | Obrigatória | Descrição |
|---|---|---|
| `FERNET_KEY` | ✅ | Chave Fernet para criptografar conexões |
| `SQLITE_DATABASE_URL` | — | URL do SQLite (padrão: `sqlite:///./audit.db`) |
| `ROBOTS` | ✅ | Lista de sistemas separados por vírgula |
| `{SISTEMA}_API_KEY` | ✅ | Chave de API de cada sistema registrado |
| `{SISTEMA}_ALLOWED_ENVS` | ✅ | Ambientes permitidos por sistema: ex. `DEV,HOM` |
| `DB_DEV_HOST` | ✅ | Host Oracle DEV (variável global) |
| `DB_DEV_PORT` | — | Porta Oracle DEV (padrão: 1521) |
| `DB_DEV_SERVICE_NAME` | ✅ | Service Name Oracle DEV |
| `DB_DEV_USER` | ✅ | Usuário Oracle DEV |
| `DB_DEV_PASSWORD` | ✅ | Senha Oracle DEV |
| `DB_HOM_*` / `DB_PROD_*` | — | Mesma estrutura para HOM e PROD |
| `{SISTEMA}_{AMBIENTE}_HOST` | — | Host Oracle específico do sistema (sobrepõe o global) |
| `{SISTEMA}_{AMBIENTE}_SCHEMA` | — | Schema Oracle exclusivo por sistema (opcional) |
| `RATE_LIMIT_PER_MINUTE` | — | Req/min por IP (padrão: 20) |
| `LOG_LEVEL` | — | Nível de log (padrão: INFO) |

> **Nunca versione o arquivo `.env`**. Ele está no `.gitignore`.

---

## Conexões por Sistema

O connection-service suporta dois modelos de configuração Oracle:

### 1. Conexão global (compartilhada)

Todos os sistemas que não possuem variáveis próprias usam as variáveis `DB_{AMBIENTE}_*`:

```env
DB_DEV_HOST=oracle-dev.internal
DB_DEV_PORT=1521
DB_DEV_SERVICE_NAME=ORCL
DB_DEV_USER=usuario_global
DB_DEV_PASSWORD=senha_global
```

### 2. Conexão específica por sistema (prioridade)

Cada sistema pode ter sua própria conexão Oracle definida com o padrão `{SISTEMA}_{AMBIENTE}_{CAMPO}`. Essas variáveis têm **prioridade** sobre as globais.

```env
# Sistema "aguia" com conexão própria
AGUIA_DEV_HOST=oracle-aguia-dev.internal
AGUIA_DEV_PORT=1521
AGUIA_DEV_SERVICE_NAME=AGUIADB
AGUIA_DEV_USER=aguia_user
AGUIA_DEV_PASSWORD=aguia_pass
AGUIA_DEV_SCHEMA=SCH_AGUIA        # campo exclusivo da notação por sistema
```

### Campos disponíveis

| Campo | Variável global | Variável por sistema | Tipo |
|---|---|---|---|
| Servidor | `DB_{AMB}_HOST` | `{SISTEMA}_{AMB}_HOST` | string |
| Porta | `DB_{AMB}_PORT` | `{SISTEMA}_{AMB}_PORT` | inteiro |
| Service Name | `DB_{AMB}_SERVICE_NAME` | `{SISTEMA}_{AMB}_SERVICE_NAME` | string |
| Usuário | `DB_{AMB}_USER` | `{SISTEMA}_{AMB}_USER` | string |
| Senha | `DB_{AMB}_PASSWORD` | `{SISTEMA}_{AMB}_PASSWORD` | string |
| Schema | — | `{SISTEMA}_{AMB}_SCHEMA` | string (opcional) |

### Resolução de variáveis (ordem de prioridade)

```
{SISTEMA}_{AMBIENTE}_{CAMPO}   ← 1º (específico do sistema)
        ↓ não encontrado
DB_{AMBIENTE}_{CAMPO}          ← 2º (global)
        ↓ não encontrado
"" (string vazia)              ← 3º (padrão)
```

### Exemplo completo com múltiplos sistemas

```env
ROBOTS=robo-financeiro,aguia,falcon

# robo-financeiro usa a conexão global
ROBO_FINANCEIRO_API_KEY=chave_financeiro
ROBO_FINANCEIRO_ALLOWED_ENVS=DEV,HOM

# aguia tem conexão Oracle própria
AGUIA_API_KEY=chave_aguia
AGUIA_ALLOWED_ENVS=DEV,HOM,PROD
AGUIA_DEV_HOST=oracle-aguia.internal
AGUIA_DEV_SERVICE_NAME=AGUIADB
AGUIA_DEV_USER=aguia_user
AGUIA_DEV_PASSWORD=aguia_pass
AGUIA_DEV_SCHEMA=SCH_AGUIA

# falcon tem conexão própria em PROD, usa global em DEV
FALCON_API_KEY=chave_falcon
FALCON_ALLOWED_ENVS=DEV,PROD
FALCON_PROD_HOST=oracle-falcon-prod.internal
FALCON_PROD_SERVICE_NAME=FALCONDB
FALCON_PROD_USER=falcon_prod_user
FALCON_PROD_PASSWORD=falcon_prod_pass

# Variáveis globais (usadas por robo-financeiro e pelo falcon em DEV)
DB_DEV_HOST=oracle-dev.internal
DB_DEV_SERVICE_NAME=DEVDB
DB_DEV_USER=dev_user
DB_DEV_PASSWORD=dev_pass
```

### Conteúdo descriptografado pelo sistema cliente

```python
{
    'servidor':    'oracle-aguia.internal',
    'porta':       1521,
    'nome_servico':'AGUIADB',
    'usuario':     'aguia_user',
    'senha':       'aguia_pass',
    'schema':      'SCH_AGUIA'   # vazio "" se não configurado
}
```

---

## Instalação Local

### Pré-requisitos

- Python 3.12+
- pip

### Passos

```bash
# 1. Acesse o diretório do projeto
cd connection-service

# 2. Crie o ambiente virtual
python -m venv .venv

# 3. Ative o ambiente virtual
# Linux / macOS
source .venv/bin/activate
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# 4. Instale as dependências
pip install -r requirements.txt

# 5. Configure as variáveis de ambiente
cp .env.example .env
# Edite o .env com seus valores reais
```

---

## Execução Local

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

> **Atenção:** após alterar o `.env`, reinicie o uvicorn completamente (`Ctrl+C` + subir novamente). O `--reload` não recarrega variáveis de ambiente em cache.

A API estará disponível em:
- **API:** http://localhost:8080
- **Swagger UI:** http://localhost:8080/docs
- **Redoc:** http://localhost:8080/redoc
- **Health Check:** http://localhost:8080/health

---

## Execução com Docker

```bash
# Certifique-se de ter o .env configurado
cp .env.example .env

# Build e inicialização
docker compose up --build

# Em background
docker compose up --build -d

# Acompanhar logs
docker compose logs -f

# Parar
docker compose down

# Parar e remover volumes (apaga banco de auditoria!)
docker compose down -v
```

### Volumes persistidos

| Volume | Destino no container | Conteúdo |
|---|---|---|
| `sqlite_data` | `/app/audit.db` | Banco SQLite de auditoria |
| `./logs` | `/app/logs` | Arquivos de log rotativos |

---

## Fluxo de Autenticação

```
Sistema cliente
 │
 ├─ Envia: nm_sistema + chave_api + cd_ambiente
 │
 ▼
connection-service
 │
 ├─ 1. Verifica se nm_sistema está em ROBOTS
 │      └─ Não encontrado → HTTP 401 (SISTEMA_NAO_ENCONTRADO)
 │
 ├─ 2. Busca {SISTEMA}_API_KEY nas variáveis de ambiente
 │      └─ Não configurada → HTTP 401 (CHAVE_API_INVALIDA)
 │
 ├─ 3. Compara chave_api recebida com a esperada
 │      (comparação em tempo constante — sem timing attack)
 │      └─ Divergente → HTTP 401 (CHAVE_API_INVALIDA)
 │
 └─ 4. Autenticação aprovada → segue para autorização
```

A comparação usa `hmac.compare_digest` para evitar timing attacks.

---

## Fluxo de Autorização

```
Autenticação aprovada
 │
 ├─ Busca {SISTEMA}_ALLOWED_ENVS nas variáveis de ambiente
 │
 ├─ Verifica se cd_ambiente está na lista permitida
 │      └─ Não está → HTTP 403 (AMBIENTE_NAO_PERMITIDO)
 │
 └─ Autorizado → segue para montagem da conexão

Exemplo:
  aguia: AGUIA_ALLOWED_ENVS=DEV,HOM
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
2. Resolve credenciais Oracle:
   Tenta {SISTEMA}_{AMBIENTE}_{CAMPO} → senão usa DB_{AMBIENTE}_{CAMPO}
        │
3. Monta dicionário de conexão:
        {
          "servidor":    "oracle-dev.internal",
          "porta":       1521,
          "nome_servico":"DEVDB",
          "usuario":     "dev_user",
          "senha":       "dev_pass",
          "schema":      "SCH_DEV"
        }
        │
4. Serializa para JSON
        │
5. Criptografa com Fernet.encrypt()
        │
6. Retorna APENAS o token criptografado:
        {
          "sucesso": true,
          "cd_ambiente": "DEV",
          "conexao_criptografada": "gAAAAABXXX..."
        }

O sistema cliente descriptografa localmente com sua FERNET_KEY:
        │
7. Fernet.decrypt(token) → JSON → dict
        │
8. oracledb.connect(user=..., password=..., host=..., ...)
```

Nunca são retornados em texto puro: servidor, usuário, senha, nome_servico, schema.

---

## Auditoria

Toda requisição — com sucesso ou falha — é registrada na tabela `TB_AUDITORIA` do SQLite.

### Estrutura da tabela

| Coluna | Tipo | Descrição |
|---|---|---|
| `CD_AUDITORIA` | INTEGER PK | Identificador único |
| `NM_SISTEMA` | VARCHAR(100) | Nome do sistema solicitante |
| `CD_AMBIENTE` | VARCHAR(10) | Ambiente: DEV/HOM/PROD |
| `IP_REQUISICAO` | VARCHAR(45) | IP do cliente (IPv4/IPv6) |
| `DT_REQUISICAO` | DATETIME | Data/hora UTC da requisição |
| `CD_STATUS` | VARCHAR(20) | SUCESSO ou NEGADO |
| `CD_MOTIVO` | VARCHAR(100) | Código descritivo do resultado |
| `ID_CORRELACAO` | VARCHAR(36) | ID de correlação para rastreamento |

### Códigos de CD_MOTIVO

| Código | Descrição |
|---|---|
| `AUTORIZADO` | Conexão entregue com sucesso |
| `SISTEMA_NAO_ENCONTRADO` | Sistema não está registrado em ROBOTS |
| `CHAVE_API_INVALIDA` | Chave de API inválida ou ausente |
| `AMBIENTE_NAO_PERMITIDO` | Ambiente não autorizado para este sistema |
| `ERRO_INTERNO` | Erro interno durante o processamento |

### Exemplos de registros

**Sucesso:**
```
NM_SISTEMA: aguia | CD_AMBIENTE: DEV | IP: 10.42.10.15
CD_STATUS: SUCESSO | CD_MOTIVO: AUTORIZADO
```

**Negado — ambiente não permitido:**
```
NM_SISTEMA: aguia | CD_AMBIENTE: PROD | IP: 10.42.10.15
CD_STATUS: NEGADO | CD_MOTIVO: AMBIENTE_NAO_PERMITIDO
```

**Negado — chave de API inválida:**
```
NM_SISTEMA: robo-fiscal | CD_AMBIENTE: HOM | IP: 10.42.10.20
CD_STATUS: NEGADO | CD_MOTIVO: CHAVE_API_INVALIDA
```

---

## Rate Limiting

Implementado via **SlowAPI**. Por padrão: **20 requisições por minuto por IP**.

```env
RATE_LIMIT_PER_MINUTE=20
```

Ao exceder o limite:
```json
HTTP 429 Too Many Requests
{
  "sucesso": false,
  "mensagem": "Muitas requisições. Tente novamente em instantes."
}
```

---

## Endpoints

### POST /api/v1/conexao

Solicita uma conexão Oracle criptografada.

**Body:**
```json
{
  "nm_sistema": "aguia",
  "chave_api": "sua-chave-api",
  "cd_ambiente": "DEV"
}
```

**200 — Sucesso:**
```json
{
  "sucesso": true,
  "cd_ambiente": "DEV",
  "conexao_criptografada": "gAAAAABXXXXXXXXXXXXXXXXXX..."
}
```

**401 — Não autorizado:**
```json
{
  "sucesso": false,
  "mensagem": "Sistema não autorizado"
}
```

**403 — Ambiente não permitido:**
```json
{
  "sucesso": false,
  "mensagem": "Ambiente não autorizado para este sistema"
}
```

**422 — Dados inválidos:**
```json
{
  "sucesso": false,
  "mensagem": "cd_ambiente: deve ser um de: ['DEV', 'HOM', 'PROD']"
}
```

**429 — Rate limit:**
```json
{
  "sucesso": false,
  "mensagem": "Muitas requisições. Tente novamente em instantes."
}
```

**500 — Erro interno:**
```json
{
  "sucesso": false,
  "mensagem": "Erro interno"
}
```

---

### GET /health

```json
{ "status": "UP" }
```

---

## Exemplos de Requisição

### curl

```bash
curl -X POST http://localhost:8080/api/v1/conexao \
  -H "Content-Type: application/json" \
  -d '{
    "nm_sistema": "aguia",
    "chave_api": "sua-chave-api",
    "cd_ambiente": "DEV"
  }'
```

### Python (requests)

```python
import requests

resposta = requests.post(
    "http://localhost:8080/api/v1/conexao",
    json={
        "nm_sistema": "aguia",
        "chave_api": "sua-chave-api",
        "cd_ambiente": "DEV",
    },
)
dados = resposta.json()
conexao_criptografada = dados["conexao_criptografada"]
```

---

## Como Descriptografar

O sistema cliente precisa ter a **mesma `FERNET_KEY`** configurada como variável de ambiente.

### Instalação no sistema cliente

```bash
pip install cryptography
```

### Código mínimo

```python
import json
import os
from cryptography.fernet import Fernet

fernet = Fernet(os.environ["FERNET_KEY"].encode())

# token recebido do connection-service
conexao_criptografada = "gAAAAAB..."

dados = json.loads(fernet.decrypt(conexao_criptografada.encode()).decode())

# {
#   'servidor':    'oracle-aguia.internal',
#   'porta':       1521,
#   'nome_servico':'AGUIADB',
#   'usuario':     'aguia_user',
#   'senha':       'aguia_pass',
#   'schema':      'SCH_AGUIA'
# }
```

### Conectar ao Oracle

```python
import oracledb

connection = oracledb.connect(
    user=dados["usuario"],
    password=dados["senha"],
    host=dados["servidor"],
    port=int(dados["porta"]),
    service_name=dados["nome_servico"],
)
```

> Consulte `robot_client_example.py` para o fluxo completo com tratamento de erros.

---

## Segurança

| Controle | Implementação |
|---|---|
| Autenticação | Chave de API por sistema via variável de ambiente |
| Comparação segura | `hmac.compare_digest` — sem timing attack |
| Autorização | Lista de ambientes permitidos por sistema |
| Criptografia | Fernet (AES-128-CBC + HMAC-SHA256) |
| Validação de entrada | Pydantic com type hints e field validators |
| Rate limiting | SlowAPI — 20 req/min por IP (configurável) |
| Auditoria | 100% das requisições registradas no SQLite |
| Logging | Logs estruturados com ID de Correlação por requisição |
| Erros | Handler global — nunca expõe stacktrace ou paths internos |
| Container | Usuário não-root no Docker |
| Credenciais | Nunca retornadas em texto puro |
