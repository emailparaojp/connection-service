"""
Modelos ORM do banco de dados de auditoria.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RegistroAuditoria(Base):
    """
    Registro de auditoria de cada solicitação de conexão.
    Toda requisição — com sucesso ou falha — deve ser registrada.
    """

    __tablename__ = "TB_AUDITORIA"

    cd_auditoria: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        name="CD_AUDITORIA",
        comment="Identificador único do registro de auditoria",
    )

    nm_sistema: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        name="NM_SISTEMA",
        comment="Nome do robô/sistema que realizou a solicitação",
    )

    cd_ambiente: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        name="CD_AMBIENTE",
        comment="Ambiente solicitado: DEV, HOM ou PROD",
    )

    ip_requisicao: Mapped[str] = mapped_column(
        String(45),  # Suporta IPv6
        nullable=False,
        name="IP_REQUISICAO",
        comment="Endereço IP do solicitante",
    )

    dt_requisicao: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        name="DT_REQUISICAO",
        comment="Data e hora da solicitação",
    )

    cd_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        name="CD_STATUS",
        comment="Resultado da solicitação: SUCESSO ou NEGADO",
    )

    cd_motivo: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        name="CD_MOTIVO",
        comment="Motivo detalhado: AUTORIZADO, API_KEY_INVALIDA, ROBO_NAO_ENCONTRADO, etc.",
    )

    id_correlacao: Mapped[str] = mapped_column(
        String(36),
        nullable=True,
        name="ID_CORRELACAO",
        comment="ID de correlação da requisição para rastreamento",
    )

    def __repr__(self) -> str:
        return (
            f"<RegistroAuditoria cd_auditoria={self.cd_auditoria} "
            f"nm_sistema={self.nm_sistema} "
            f"cd_ambiente={self.cd_ambiente} cd_status={self.cd_status}>"
        )
