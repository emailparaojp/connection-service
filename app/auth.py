"""
Módulo de autenticação e autorização.
Valida nm_sistema, chave_api e permissões de ambiente.

Regras:
  1. O sistema deve estar na lista ROBOTS do .env
  2. A chave de API deve corresponder à variável {SISTEMA}_API_KEY
  3. O ambiente solicitado deve estar em {SISTEMA}_ALLOWED_ENVS
"""

import hmac
import logging

from app.config import obter_configuracoes

logger = logging.getLogger(__name__)


class ResultadoAutenticacao:
    """Resultado de uma verificação de autenticação/autorização."""

    __slots__ = ("autorizado", "cd_status", "cd_motivo")

    def __init__(self, autorizado: bool, cd_status: str, cd_motivo: str) -> None:
        self.autorizado = autorizado
        self.cd_status = cd_status    # "SUCESSO" | "NEGADO"
        self.cd_motivo = cd_motivo    # Código descritivo para auditoria


# Constantes de motivo (usadas na auditoria)
MOTIVO_AUTORIZADO = "AUTORIZADO"
MOTIVO_SISTEMA_NAO_ENCONTRADO = "SISTEMA_NAO_ENCONTRADO"
MOTIVO_CHAVE_API_INVALIDA = "CHAVE_API_INVALIDA"
MOTIVO_AMBIENTE_NAO_PERMITIDO = "AMBIENTE_NAO_PERMITIDO"


def validar_sistema(nm_sistema: str, chave_api: str, cd_ambiente: str) -> ResultadoAutenticacao:
    """
    Valida a identidade do sistema e sua autorização para o ambiente.

    Args:
        nm_sistema:  Nome do sistema (já normalizado para lowercase).
        chave_api:   Chave de API informada pelo sistema.
        cd_ambiente: Ambiente Oracle solicitado (DEV/HOM/PROD).

    Returns:
        ResultadoAutenticacao com o resultado detalhado da validação.
    """
    configuracoes = obter_configuracoes()
    sistemas_registrados = configuracoes.obter_lista_sistemas()

    # 1. Verifica se o sistema está registrado
    if nm_sistema not in sistemas_registrados:
        logger.warning("Sistema não encontrado: '%s'", nm_sistema)
        return ResultadoAutenticacao(
            autorizado=False,
            cd_status="NEGADO",
            cd_motivo=MOTIVO_SISTEMA_NAO_ENCONTRADO,
        )

    # 2. Busca a chave de API esperada para o sistema
    chave_esperada = configuracoes.obter_chave_api_sistema(nm_sistema)
    if not chave_esperada:
        logger.warning("Chave de API não configurada para o sistema: '%s'", nm_sistema)
        return ResultadoAutenticacao(
            autorizado=False,
            cd_status="NEGADO",
            cd_motivo=MOTIVO_CHAVE_API_INVALIDA,
        )

    # 3. Compara as chaves usando comparação em tempo constante (evita timing attacks)
    if not hmac.compare_digest(chave_api, chave_esperada):
        logger.warning("Chave de API inválida para o sistema: '%s'", nm_sistema)
        return ResultadoAutenticacao(
            autorizado=False,
            cd_status="NEGADO",
            cd_motivo=MOTIVO_CHAVE_API_INVALIDA,
        )

    # 4. Verifica permissão para o ambiente solicitado
    ambientes_permitidos = configuracoes.obter_ambientes_permitidos(nm_sistema)
    if cd_ambiente.upper() not in ambientes_permitidos:
        logger.warning(
            "Sistema '%s' não autorizado para o ambiente '%s'. Permitidos: %s",
            nm_sistema,
            cd_ambiente,
            ambientes_permitidos,
        )
        return ResultadoAutenticacao(
            autorizado=False,
            cd_status="NEGADO",
            cd_motivo=MOTIVO_AMBIENTE_NAO_PERMITIDO,
        )

    logger.info("Sistema '%s' autorizado para o ambiente '%s'.", nm_sistema, cd_ambiente)
    return ResultadoAutenticacao(
        autorizado=True,
        cd_status="SUCESSO",
        cd_motivo=MOTIVO_AUTORIZADO,
    )
