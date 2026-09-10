"""
Exceções customizadas e handlers globais de erro.

Princípios:
  - Nunca expor stacktrace, paths internos ou mensagens técnicas ao cliente.
  - Toda exceção deve ser mapeada para uma resposta JSON padronizada.
  - Erros inesperados retornam HTTP 500 com mensagem genérica.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Exceções de domínio
# ------------------------------------------------------------------


class ErroSistemaNaoEncontrado(Exception):
    """Lançada quando o sistema não está registrado no connection-service."""


class ErroChaveApiInvalida(Exception):
    """Lançada quando a chave de API fornecida é inválida."""


class ErroAmbienteNaoPermitido(Exception):
    """Lançada quando o sistema não tem permissão para o ambiente solicitado."""


class ErroConstrucaoConexao(Exception):
    """Lançada quando não é possível montar a string de conexão Oracle."""


class ErroCriptografia(Exception):
    """Lançada quando a criptografia da conexão falha."""


# ------------------------------------------------------------------
# Resposta de erro padronizada
# ------------------------------------------------------------------


def _resposta_erro(mensagem: str, codigo_status: int) -> JSONResponse:
    """Monta resposta JSON de erro no formato padrão da API."""
    return JSONResponse(
        status_code=codigo_status,
        content={"sucesso": False, "mensagem": mensagem},
    )


# ------------------------------------------------------------------
# Registro dos handlers no app FastAPI
# ------------------------------------------------------------------


def registrar_handlers_excecao(app: FastAPI) -> None:
    """
    Registra todos os handlers de exceção na instância FastAPI.
    Deve ser chamado durante a inicialização da aplicação.
    """

    @app.exception_handler(ErroSistemaNaoEncontrado)
    async def handler_sistema_nao_encontrado(
        request: Request, exc: ErroSistemaNaoEncontrado
    ) -> JSONResponse:
        logger.warning("ErroSistemaNaoEncontrado: %s | path=%s", exc, request.url.path)
        return _resposta_erro("Sistema não autorizado", status.HTTP_401_UNAUTHORIZED)

    @app.exception_handler(ErroChaveApiInvalida)
    async def handler_chave_api_invalida(
        request: Request, exc: ErroChaveApiInvalida
    ) -> JSONResponse:
        logger.warning("ErroChaveApiInvalida: %s | path=%s", exc, request.url.path)
        return _resposta_erro("Sistema não autorizado", status.HTTP_401_UNAUTHORIZED)

    @app.exception_handler(ErroAmbienteNaoPermitido)
    async def handler_ambiente_nao_permitido(
        request: Request, exc: ErroAmbienteNaoPermitido
    ) -> JSONResponse:
        logger.warning("ErroAmbienteNaoPermitido: %s | path=%s", exc, request.url.path)
        return _resposta_erro(
            "Ambiente não autorizado para este sistema", status.HTTP_403_FORBIDDEN
        )

    @app.exception_handler(ErroConstrucaoConexao)
    async def handler_erro_construcao_conexao(
        request: Request, exc: ErroConstrucaoConexao
    ) -> JSONResponse:
        logger.error("ErroConstrucaoConexao: %s | path=%s", exc, request.url.path)
        return _resposta_erro("Erro interno", status.HTTP_500_INTERNAL_SERVER_ERROR)

    @app.exception_handler(ErroCriptografia)
    async def handler_erro_criptografia(
        request: Request, exc: ErroCriptografia
    ) -> JSONResponse:
        logger.error("ErroCriptografia: %s | path=%s", exc, request.url.path)
        return _resposta_erro("Erro interno", status.HTTP_500_INTERNAL_SERVER_ERROR)

    @app.exception_handler(RequestValidationError)
    async def handler_erro_validacao(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """
        Captura erros de validação do Pydantic.
        Retorna mensagem amigável sem expor detalhes internos do schema.
        """
        logger.warning(
            "Erro de validação de entrada | path=%s | erros=%s",
            request.url.path,
            exc.errors(),
        )
        mensagens = []
        for erro in exc.errors():
            campo = " -> ".join(str(loc) for loc in erro.get("loc", []))
            msg = erro.get("msg", "Valor inválido")
            mensagens.append(f"{campo}: {msg}" if campo else msg)

        return _resposta_erro(
            "; ".join(mensagens) if mensagens else "Dados de requisição inválidos",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    @app.exception_handler(RateLimitExceeded)
    async def handler_limite_requisicoes(
        request: Request, exc: RateLimitExceeded
    ) -> JSONResponse:
        logger.warning(
            "Limite de requisições excedido | ip=%s | path=%s",
            request.client.host,
            request.url.path,
        )
        return _resposta_erro(
            "Muitas requisições. Tente novamente em instantes.",
            status.HTTP_429_TOO_MANY_REQUESTS,
        )

    @app.exception_handler(Exception)
    async def handler_excecao_generica(request: Request, exc: Exception) -> JSONResponse:
        """
        Handler de último recurso.
        Captura qualquer exceção não tratada e retorna resposta genérica.
        Nunca expõe detalhes técnicos ao cliente.
        """
        logger.exception(
            "Exceção não tratada | path=%s | tipo=%s",
            request.url.path,
            type(exc).__name__,
        )
        return _resposta_erro("Erro interno", status.HTTP_500_INTERNAL_SERVER_ERROR)
