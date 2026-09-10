"""
Schemas Pydantic para validação de entrada e saída da API.
Define contratos claros entre cliente e servidor.
"""

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ------------------------------------------------------------------
# Constantes de validação
# ------------------------------------------------------------------

AMBIENTES_VALIDOS = {"DEV", "HOM", "PROD"}
STATUS_VALIDOS = {"SUCESSO", "NEGADO"}

# Padrão permitido para nomes de sistemas/robôs: letras minúsculas, números e hífens
PADRAO_NOME_SISTEMA = re.compile(r"^[a-z0-9\-]{3,50}$")


# ------------------------------------------------------------------
# Schemas de Requisição
# ------------------------------------------------------------------


class RequisicaoConexao(BaseModel):
    """Schema de entrada para solicitação de conexão Oracle."""

    nm_sistema: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Nome do sistema/robô solicitante",
        examples=["robo-financeiro"],
    )

    chave_api: str = Field(
        ...,
        min_length=8,
        max_length=256,
        description="Chave de API do sistema para autenticação",
        examples=["abc123"],
    )

    cd_ambiente: str = Field(
        ...,
        description="Ambiente Oracle desejado: DEV, HOM ou PROD",
        examples=["DEV"],
    )

    @field_validator("nm_sistema")
    @classmethod
    def validar_nome_sistema(cls, v: str) -> str:
        """Sanitiza e valida o nome do sistema."""
        sanitizado = v.strip().lower()
        if not PADRAO_NOME_SISTEMA.match(sanitizado):
            raise ValueError(
                "nm_sistema deve conter apenas letras minúsculas, números e hífens (3-50 caracteres)"
            )
        return sanitizado

    @field_validator("cd_ambiente")
    @classmethod
    def validar_ambiente(cls, v: str) -> str:
        """Valida e normaliza o ambiente solicitado."""
        upper = v.strip().upper()
        if upper not in AMBIENTES_VALIDOS:
            raise ValueError(f"cd_ambiente deve ser um de: {sorted(AMBIENTES_VALIDOS)}")
        return upper

    @field_validator("chave_api")
    @classmethod
    def validar_chave_api(cls, v: str) -> str:
        """Remove espaços e garante que a chave de API não está vazia."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("chave_api não pode estar vazia")
        return stripped

    model_config = {
        "json_schema_extra": {
            "example": {
                "nm_sistema": "robo-financeiro",
                "chave_api": "abc123",
                "cd_ambiente": "DEV",
            }
        }
    }


# ------------------------------------------------------------------
# Schemas de Resposta
# ------------------------------------------------------------------


class RespostaConexaoSucesso(BaseModel):
    """Resposta de sucesso com a string de conexão criptografada."""

    sucesso: bool = Field(default=True)
    cd_ambiente: str = Field(..., description="Ambiente da conexão retornada")
    conexao_criptografada: str = Field(
        ...,
        description="String de conexão Oracle criptografada com Fernet",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "sucesso": True,
                "cd_ambiente": "DEV",
                "conexao_criptografada": "gAAAAABXXXXXXXXXXXXXXXXXX",
            }
        }
    }


class RespostaErro(BaseModel):
    """Resposta de erro padronizada. Nunca expõe detalhes técnicos."""

    sucesso: bool = Field(default=False)
    mensagem: str = Field(..., description="Mensagem de erro legível")

    model_config = {
        "json_schema_extra": {
            "example": {
                "sucesso": False,
                "mensagem": "Sistema não autorizado",
            }
        }
    }


class RespostaSaude(BaseModel):
    """Resposta do endpoint de health check."""

    status: str = Field(default="UP")


# ------------------------------------------------------------------
# Schemas de Auditoria (uso interno / logs)
# ------------------------------------------------------------------


class EsquemaRegistroAuditoria(BaseModel):
    """Representação de um registro de auditoria (uso interno)."""

    cd_auditoria: int
    nm_sistema: str
    cd_ambiente: str
    ip_requisicao: str
    dt_requisicao: datetime
    cd_status: str
    cd_motivo: str
    id_correlacao: Optional[str] = None

    model_config = {"from_attributes": True}
