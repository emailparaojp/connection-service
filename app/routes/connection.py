"""
Rota principal de solicitação de conexão Oracle.

POST /api/v1/conexao

Recebe as credenciais do sistema, valida, audita e retorna
a string de conexão Oracle criptografada com Fernet.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.config import obter_configuracoes
from app.database import obter_banco
from app.middleware import CHAVE_ID_CORRELACAO
from app.schemas import RequisicaoConexao, RespostaConexaoSucesso, RespostaErro
from app.services.connection_service import ServicoConexao

logger = logging.getLogger(__name__)
configuracoes = obter_configuracoes()

# Inicializa o limiter usando o IP remoto como chave
limiter = Limiter(key_func=get_remote_address)

roteador = APIRouter(prefix="/api/v1", tags=["Conexão"])


@roteador.post(
    "/conexao",
    response_model=RespostaConexaoSucesso,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Conexão criptografada entregue com sucesso",
            "model": RespostaConexaoSucesso,
        },
        401: {
            "description": "Sistema não encontrado ou chave de API inválida",
            "model": RespostaErro,
        },
        403: {
            "description": "Ambiente não autorizado para este sistema",
            "model": RespostaErro,
        },
        422: {
            "description": "Dados de entrada inválidos",
            "model": RespostaErro,
        },
        429: {
            "description": "Limite de requisições excedido",
            "model": RespostaErro,
        },
        500: {
            "description": "Erro interno do servidor",
            "model": RespostaErro,
        },
    },
    summary="Solicitar conexão Oracle criptografada",
    description=(
        "Autentica o sistema pela chave de API, verifica permissão de ambiente, "
        "e retorna a string de conexão Oracle criptografada com Fernet. "
        "Toda solicitação é auditada independentemente do resultado."
    ),
)
@limiter.limit(f"{configuracoes.rate_limit_per_minute}/minute")
async def solicitar_conexao(
    request: Request,
    corpo: RequisicaoConexao,
    sessao: Annotated[Session, Depends(obter_banco)],
) -> RespostaConexaoSucesso:
    """
    Endpoint principal para solicitação de conexão Oracle.

    O sistema deve informar:
      - nm_sistema:  nome registrado no connection-service
      - chave_api:   chave de autenticação
      - cd_ambiente: DEV, HOM ou PROD

    Retorna apenas a string de conexão criptografada.
    Nunca retorna servidor, usuário, senha ou nome do serviço em texto puro.
    """
    # Extrai IP e ID de correlação do estado da requisição (injetados pelo middleware)
    ip_requisicao: str = getattr(
        request.state,
        "ip_cliente",
        request.client.host if request.client else "desconhecido",
    )
    id_correlacao: str = getattr(request.state, CHAVE_ID_CORRELACAO, None)

    logger.info(
        "Solicitação de conexão | nm_sistema=%s | cd_ambiente=%s | ip=%s | id_correlacao=%s",
        corpo.nm_sistema,
        corpo.cd_ambiente,
        ip_requisicao,
        id_correlacao,
    )

    servico = ServicoConexao(sessao=sessao)
    return servico.processar_solicitacao_conexao(
        requisicao=corpo,
        ip_requisicao=ip_requisicao,
        id_correlacao=id_correlacao,
    )
