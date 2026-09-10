"""
Middleware de logging e rastreamento de requisições.

Responsabilidades:
  - Gerar ID de correlação único por requisição
  - Registrar entrada (método, path, IP)
  - Registrar saída (status code, tempo de processamento)
  - Propagar ID de correlação no header de resposta para rastreamento
"""

import logging
import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# Chave usada para armazenar o id_correlacao no request state
CHAVE_ID_CORRELACAO = "id_correlacao"
HEADER_ID_CORRELACAO = "X-Correlation-ID"


class MiddlewareLogRequisicao(BaseHTTPMiddleware):
    """
    Middleware que intercepta todas as requisições HTTP para:
      1. Gerar ou propagar um ID de Correlação
      2. Registrar os metadados da requisição (IP, método, path)
      3. Medir o tempo de processamento
      4. Registrar os metadados da resposta (status code, duração)
      5. Injetar o ID de Correlação no header da resposta
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Gera ou reutiliza ID de Correlação do header de entrada
        id_correlacao = request.headers.get(HEADER_ID_CORRELACAO) or str(uuid.uuid4())
        request.state.id_correlacao = id_correlacao

        # Captura IP real (suporte a proxy/load balancer via X-Forwarded-For)
        ip_cliente = self._obter_ip_cliente(request)
        request.state.ip_cliente = ip_cliente

        inicio = time.perf_counter()

        logger.info(
            "REQUISIÇÃO  | id_correlacao=%s | metodo=%s | path=%s | ip=%s",
            id_correlacao,
            request.method,
            request.url.path,
            ip_cliente,
        )

        try:
            resposta: Response = await call_next(request)
        except Exception as exc:
            duracao_ms = (time.perf_counter() - inicio) * 1000
            logger.error(
                "ERRO REQUISIÇÃO | id_correlacao=%s | path=%s | ip=%s | duracao_ms=%.2f | erro=%s",
                id_correlacao,
                request.url.path,
                ip_cliente,
                duracao_ms,
                type(exc).__name__,
            )
            raise

        duracao_ms = (time.perf_counter() - inicio) * 1000

        logger.info(
            "RESPOSTA | id_correlacao=%s | metodo=%s | path=%s | ip=%s | status=%d | duracao_ms=%.2f",
            id_correlacao,
            request.method,
            request.url.path,
            ip_cliente,
            resposta.status_code,
            duracao_ms,
        )

        # Injeta ID de Correlação na resposta para rastreamento pelo cliente
        resposta.headers[HEADER_ID_CORRELACAO] = id_correlacao

        return resposta

    @staticmethod
    def _obter_ip_cliente(request: Request) -> str:
        """
        Extrai o IP real do cliente.
        Considera cabeçalhos de proxy na seguinte ordem:
          X-Forwarded-For > X-Real-IP > request.client.host
        """
        encaminhado_por = request.headers.get("X-Forwarded-For")
        if encaminhado_por:
            # X-Forwarded-For pode conter múltiplos IPs; o primeiro é o cliente original
            return encaminhado_por.split(",")[0].strip()

        ip_real = request.headers.get("X-Real-IP")
        if ip_real:
            return ip_real.strip()

        if request.client:
            return request.client.host

        return "desconhecido"
