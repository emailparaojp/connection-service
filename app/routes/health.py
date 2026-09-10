"""
Rota de health check da aplicação.

GET /health

Usado por load balancers, orquestradores (Kubernetes, Docker Compose)
e ferramentas de monitoramento para verificar se o serviço está ativo.
"""

import logging

from fastapi import APIRouter, status

from app.schemas import RespostaSaude

logger = logging.getLogger(__name__)

roteador = APIRouter(tags=["Saúde"])


@roteador.get(
    "/health",
    response_model=RespostaSaude,
    status_code=status.HTTP_200_OK,
    summary="Verificação de Saúde",
    description="Verifica se o serviço está ativo e respondendo.",
)
async def verificar_saude() -> RespostaSaude:
    """
    Retorna o status de saúde da aplicação.

    Resposta esperada:
        {"status": "UP"}

    Não verifica dependências externas (Oracle, etc.) — apenas
    confirma que o processo está ativo e aceitando requisições.
    """
    logger.debug("Verificação de saúde solicitada.")
    return RespostaSaude(status="UP")
