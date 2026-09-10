"""
Serviço de auditoria.
Orquestra o registro de todas as solicitações de conexão,
independentemente do resultado (sucesso ou falha).

Princípio: toda chamada à API deve gerar um registro de auditoria,
incluindo erros internos — para rastreabilidade total.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models import RegistroAuditoria
from app.repositories.audit_repository import RepositorioAuditoria

logger = logging.getLogger(__name__)


class ServicoAuditoria:
    """
    Serviço responsável por registrar eventos de auditoria.
    Recebe a sessão de banco via injeção de dependência para
    participar da mesma transação da requisição quando necessário.
    """

    def __init__(self, sessao: Session) -> None:
        self._repositorio = RepositorioAuditoria(sessao)

    def registrar(
        self,
        nm_sistema: str,
        cd_ambiente: str,
        ip_requisicao: str,
        cd_status: str,
        cd_motivo: str,
        id_correlacao: Optional[str] = None,
    ) -> Optional[RegistroAuditoria]:
        """
        Registra um evento de auditoria no banco de dados (TB_AUDITORIA).

        Nunca lança exceção para o chamador — falhas de auditoria
        são apenas logadas para não interromper o fluxo principal.

        Args:
            nm_sistema:     Nome do sistema solicitante.
            cd_ambiente:    Ambiente solicitado (DEV/HOM/PROD).
            ip_requisicao:  IP do cliente.
            cd_status:      "SUCESSO" ou "NEGADO".
            cd_motivo:      Código descritivo do resultado.
            id_correlacao:  ID de correlação da requisição.

        Returns:
            RegistroAuditoria persistido, ou None em caso de falha de auditoria.
        """
        try:
            registro = self._repositorio.criar(
                nm_sistema=nm_sistema,
                cd_ambiente=cd_ambiente,
                ip_requisicao=ip_requisicao,
                cd_status=cd_status,
                cd_motivo=cd_motivo,
                id_correlacao=id_correlacao,
            )
            logger.info(
                "AUDITORIA | nm_sistema=%s | cd_ambiente=%s | ip=%s"
                " | cd_status=%s | cd_motivo=%s | id_correlacao=%s",
                nm_sistema,
                cd_ambiente,
                ip_requisicao,
                cd_status,
                cd_motivo,
                id_correlacao,
            )
            return registro
        except Exception as exc:
            # Auditoria não deve quebrar o fluxo principal
            logger.error(
                "Falha ao registrar auditoria | nm_sistema=%s | cd_ambiente=%s | erro=%s",
                nm_sistema,
                cd_ambiente,
                exc,
            )
            return None

    def registrar_sucesso(
        self,
        nm_sistema: str,
        cd_ambiente: str,
        ip_requisicao: str,
        id_correlacao: Optional[str] = None,
    ) -> Optional[RegistroAuditoria]:
        """Atalho para registrar auditoria de sucesso."""
        return self.registrar(
            nm_sistema=nm_sistema,
            cd_ambiente=cd_ambiente,
            ip_requisicao=ip_requisicao,
            cd_status="SUCESSO",
            cd_motivo="AUTORIZADO",
            id_correlacao=id_correlacao,
        )

    def registrar_negacao(
        self,
        nm_sistema: str,
        cd_ambiente: str,
        ip_requisicao: str,
        cd_motivo: str,
        id_correlacao: Optional[str] = None,
    ) -> Optional[RegistroAuditoria]:
        """Atalho para registrar auditoria de negação."""
        return self.registrar(
            nm_sistema=nm_sistema,
            cd_ambiente=cd_ambiente,
            ip_requisicao=ip_requisicao,
            cd_status="NEGADO",
            cd_motivo=cd_motivo,
            id_correlacao=id_correlacao,
        )

    def registrar_erro(
        self,
        nm_sistema: str,
        cd_ambiente: str,
        ip_requisicao: str,
        id_correlacao: Optional[str] = None,
    ) -> Optional[RegistroAuditoria]:
        """Atalho para registrar erros internos."""
        return self.registrar(
            nm_sistema=nm_sistema,
            cd_ambiente=cd_ambiente,
            ip_requisicao=ip_requisicao,
            cd_status="NEGADO",
            cd_motivo="ERRO_INTERNO",
            id_correlacao=id_correlacao,
        )
