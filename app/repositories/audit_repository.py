"""
Repositório de auditoria.
Responsável por todas as operações de persistência na tabela TB_AUDITORIA.

Segue o padrão Repository para desacoplar a lógica de acesso a dados
dos serviços de negócio.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models import RegistroAuditoria

logger = logging.getLogger(__name__)


class RepositorioAuditoria:
    """
    Repositório para persistência dos registros de auditoria.
    Recebe a sessão de banco via injeção de dependência.
    """

    def __init__(self, sessao: Session) -> None:
        self._sessao = sessao

    def criar(
        self,
        nm_sistema: str,
        cd_ambiente: str,
        ip_requisicao: str,
        cd_status: str,
        cd_motivo: str,
        id_correlacao: Optional[str] = None,
    ) -> RegistroAuditoria:
        """
        Persiste um novo registro de auditoria na tabela TB_AUDITORIA.

        Args:
            nm_sistema:     Nome do sistema/robô que realizou a requisição.
            cd_ambiente:    Ambiente solicitado (DEV/HOM/PROD).
            ip_requisicao:  IP do cliente.
            cd_status:      "SUCESSO" ou "NEGADO".
            cd_motivo:      Código descritivo (ex: AUTORIZADO, CHAVE_API_INVALIDA).
            id_correlacao:  ID de correlação da requisição (opcional).

        Returns:
            Instância do RegistroAuditoria persistida.

        Raises:
            Exception: Propaga exceções de banco para tratamento na camada superior.
        """
        registro = RegistroAuditoria(
            nm_sistema=nm_sistema,
            cd_ambiente=cd_ambiente,
            ip_requisicao=ip_requisicao,
            dt_requisicao=datetime.now(tz=timezone.utc),
            cd_status=cd_status,
            cd_motivo=cd_motivo,
            id_correlacao=id_correlacao,
        )

        try:
            self._sessao.add(registro)
            self._sessao.flush()  # Garante o cd_auditoria sem commit (responsabilidade do caller)
            logger.debug(
                "Auditoria registrada | cd_auditoria=%s | nm_sistema=%s | cd_ambiente=%s"
                " | cd_status=%s | cd_motivo=%s",
                registro.cd_auditoria,
                nm_sistema,
                cd_ambiente,
                cd_status,
                cd_motivo,
            )
            return registro
        except Exception as exc:
            logger.error(
                "Falha ao persistir auditoria | nm_sistema=%s | cd_ambiente=%s | erro=%s",
                nm_sistema,
                cd_ambiente,
                exc,
            )
            raise

    def buscar_por_sistema(
        self, nm_sistema: str, limite: int = 100
    ) -> list[RegistroAuditoria]:
        """
        Retorna os últimos registros de auditoria de um sistema específico.

        Args:
            nm_sistema: Nome do sistema/robô.
            limite:     Número máximo de registros retornados.

        Returns:
            Lista de RegistroAuditoria ordenada por data decrescente.
        """
        return (
            self._sessao.query(RegistroAuditoria)
            .filter(RegistroAuditoria.nm_sistema == nm_sistema)
            .order_by(RegistroAuditoria.dt_requisicao.desc())
            .limit(limite)
            .all()
        )
