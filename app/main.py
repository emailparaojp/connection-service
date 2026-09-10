"""
Ponto de entrada da aplicação connection-service.

Responsabilidades deste módulo:
  - Configurar o logging estruturado
  - Criar e configurar a instância FastAPI
  - Registrar middlewares
  - Registrar handlers de exceção
  - Registrar roteadores
  - Inicializar o banco de dados SQLite na partida
  - Configurar o SlowAPI (rate limiting)
"""

import logging
import logging.config
import os
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.config import obter_configuracoes
from app.database import inicializar_banco
from app.exceptions import registrar_handlers_excecao
from app.middleware import MiddlewareLogRequisicao
from app.routes.connection import roteador as roteador_conexao
from app.routes.health import roteador as roteador_saude


# ------------------------------------------------------------------
# Configuração de Logging
# ------------------------------------------------------------------

def configurar_logging(nivel_log: str = "INFO") -> None:
    """
    Configura o sistema de logging da aplicação.

    Formata as mensagens com timestamp, nível, nome do módulo e mensagem.
    Garante que logs sejam gravados tanto no console quanto em arquivo rotativo.
    """
    os.makedirs("logs", exist_ok=True)

    configuracao_log = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "padrao": {
                "format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                "datefmt": "%Y-%m-%dT%H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": sys.stdout,
                "formatter": "padrao",
                "level": nivel_log,
            },
            "arquivo": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": "logs/connection-service.log",
                "maxBytes": 10 * 1024 * 1024,  # 10 MB
                "backupCount": 5,
                "formatter": "padrao",
                "level": nivel_log,
                "encoding": "utf-8",
            },
        },
        "root": {
            "level": nivel_log,
            "handlers": ["console", "arquivo"],
        },
        # Reduz verbosidade de bibliotecas de terceiros
        "loggers": {
            "uvicorn": {"level": "INFO", "propagate": True},
            "uvicorn.access": {"level": "WARNING", "propagate": True},
            "sqlalchemy.engine": {"level": "WARNING", "propagate": True},
        },
    }

    logging.config.dictConfig(configuracao_log)


# ------------------------------------------------------------------
# Ciclo de Vida (substitui os eventos on_startup / on_shutdown)
# ------------------------------------------------------------------

@asynccontextmanager
async def ciclo_de_vida(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Gerencia o ciclo de vida da aplicação.
    Código antes do yield: executado na inicialização.
    Código após o yield:   executado no encerramento.
    """
    configuracoes = obter_configuracoes()
    configurar_logging(configuracoes.log_level)
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("Iniciando connection-service...")
    logger.info("Nível de log: %s", configuracoes.log_level)
    logger.info("Rate limit: %d req/min", configuracoes.rate_limit_per_minute)
    logger.info("Sistemas registrados: %s", configuracoes.obter_lista_sistemas())
    logger.info("=" * 60)

    # Inicializa o banco de dados SQLite (cria tabelas se não existirem)
    try:
        inicializar_banco()
        logger.info("Banco de dados inicializado com sucesso.")
    except Exception as exc:
        logger.critical("Falha ao inicializar banco de dados: %s", exc)
        raise

    # Inicializa o ServicoCriptografia para validar a FERNET_KEY na partida
    try:
        from app.crypto import obter_servico_criptografia
        obter_servico_criptografia()
        logger.info("Serviço de criptografia inicializado com sucesso.")
    except Exception as exc:
        logger.critical("Falha ao inicializar ServicoCriptografia: %s", exc)
        raise

    logger.info("connection-service pronto para receber requisições.")

    yield  # Aplicação em execução

    logger.info("Encerrando connection-service...")


# ------------------------------------------------------------------
# Fábrica da aplicação
# ------------------------------------------------------------------

def criar_app() -> FastAPI:
    """
    Fábrica que cria e configura a instância FastAPI.
    Facilita testes unitários e de integração.
    """
    configuracoes = obter_configuracoes()

    app = FastAPI(
        title="Connection Service",
        description=(
            "Serviço centralizado para entrega de conexões Oracle criptografadas. "
            "Sistemas autenticados recebem strings de conexão cifradas com Fernet, "
            "garantindo que nenhuma credencial Oracle trafegue em texto puro."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=ciclo_de_vida,
    )

    # ------------------------------------------------------------------
    # Rate Limiting (SlowAPI)
    # ------------------------------------------------------------------
    limitador = Limiter(
        key_func=get_remote_address,
        default_limits=[f"{configuracoes.rate_limit_per_minute}/minute"],
    )
    app.state.limiter = limitador
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # ------------------------------------------------------------------
    # Middleware de logging e ID de Correlação
    # Deve ser adicionado APÓS o SlowAPIMiddleware
    # ------------------------------------------------------------------
    app.add_middleware(MiddlewareLogRequisicao)

    # ------------------------------------------------------------------
    # Handlers globais de exceção
    # ------------------------------------------------------------------
    registrar_handlers_excecao(app)

    # ------------------------------------------------------------------
    # Roteadores
    # ------------------------------------------------------------------
    app.include_router(roteador_saude)
    app.include_router(roteador_conexao)

    return app


# Instância global usada pelo Uvicorn
app = criar_app()
