"""
Configurações centralizadas da aplicação.
Carrega e valida todas as variáveis de ambiente usando Pydantic Settings.
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracoes(BaseSettings):
    """
    Configurações da aplicação carregadas a partir do arquivo .env.
    Todos os campos são tipados e validados na inicialização.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow",  # Permite variáveis dinâmicas (por robô, por ambiente)
    )

    # ------------------------------------------------------------------
    # Criptografia
    # ------------------------------------------------------------------
    fernet_key: str = Field(..., description="Chave Fernet para criptografia das conexões")

    # ------------------------------------------------------------------
    # Banco de Auditoria
    # ------------------------------------------------------------------
    sqlite_database_url: str = Field(
        default="sqlite:///./audit.db",
        description="URL de conexão SQLite para auditoria",
    )

    # ------------------------------------------------------------------
    # Sistemas/Robôs registrados
    # ------------------------------------------------------------------
    robots: str = Field(
        default="",
        description="Lista de sistemas separados por vírgula",
    )

    # ------------------------------------------------------------------
    # Rate Limiting
    # ------------------------------------------------------------------
    rate_limit_per_minute: int = Field(
        default=20,
        description="Número máximo de requisições por minuto por IP",
    )

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    log_level: str = Field(default="INFO", description="Nível de log")

    # ------------------------------------------------------------------
    # Oracle — DEV
    # ------------------------------------------------------------------
    db_dev_host: str = Field(default="", description="Host Oracle DEV")
    db_dev_port: int = Field(default=1521, description="Porta Oracle DEV")
    db_dev_service_name: str = Field(default="", description="Service Name Oracle DEV")
    db_dev_user: str = Field(default="", description="Usuário Oracle DEV")
    db_dev_password: str = Field(default="", description="Senha Oracle DEV")

    # ------------------------------------------------------------------
    # Oracle — HOM
    # ------------------------------------------------------------------
    db_hom_host: str = Field(default="", description="Host Oracle HOM")
    db_hom_port: int = Field(default=1521, description="Porta Oracle HOM")
    db_hom_service_name: str = Field(default="", description="Service Name Oracle HOM")
    db_hom_user: str = Field(default="", description="Usuário Oracle HOM")
    db_hom_password: str = Field(default="", description="Senha Oracle HOM")

    # ------------------------------------------------------------------
    # Oracle — PROD
    # ------------------------------------------------------------------
    db_prod_host: str = Field(default="", description="Host Oracle PROD")
    db_prod_port: int = Field(default=1521, description="Porta Oracle PROD")
    db_prod_service_name: str = Field(default="", description="Service Name Oracle PROD")
    db_prod_user: str = Field(default="", description="Usuário Oracle PROD")
    db_prod_password: str = Field(default="", description="Senha Oracle PROD")

    @field_validator("log_level")
    @classmethod
    def validar_nivel_log(cls, v: str) -> str:
        permitidos = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in permitidos:
            raise ValueError(f"log_level deve ser um de: {permitidos}")
        return upper

    @field_validator("fernet_key")
    @classmethod
    def validar_chave_fernet(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError("FERNET_KEY não pode estar vazio")
        return v.strip()

    def obter_lista_sistemas(self) -> list[str]:
        """Retorna lista de sistemas/robôs registrados."""
        if not self.robots:
            return []
        return [r.strip() for r in self.robots.split(",") if r.strip()]

    def obter_chave_api_sistema(self, nm_sistema: str) -> Optional[str]:
        """
        Busca a chave de API de um sistema nas variáveis de ambiente.
        Converte o nome do sistema para o formato da variável:
            robo-financeiro → ROBO_FINANCEIRO_API_KEY
        """
        chave_env = nm_sistema.upper().replace("-", "_") + "_API_KEY"
        valor = getattr(self, chave_env.lower(), None)
        if valor is None:
            valor = (
                self.model_extra.get(chave_env.lower())
                or self.model_extra.get(chave_env)
            )
        return valor or None

    def obter_ambientes_permitidos(self, nm_sistema: str) -> list[str]:
        """
        Retorna os ambientes permitidos para um sistema.
        Converte: robo-financeiro → ROBO_FINANCEIRO_ALLOWED_ENVS
        """
        chave_env = nm_sistema.upper().replace("-", "_") + "_ALLOWED_ENVS"
        valor = getattr(self, chave_env.lower(), None)
        if valor is None:
            valor = (
                self.model_extra.get(chave_env.lower())
                or self.model_extra.get(chave_env)
            )
        if not valor:
            return []
        return [e.strip().upper() for e in str(valor).split(",") if e.strip()]

    def obter_config_oracle(self, cd_ambiente: str) -> dict:
        """
        Retorna as configurações Oracle para o ambiente solicitado.
        Nunca deve ser exposto diretamente via API.
        """
        ambiente = cd_ambiente.upper()
        mapeamento = {
            "DEV": {
                "servidor": self.db_dev_host,
                "porta": self.db_dev_port,
                "nome_servico": self.db_dev_service_name,
                "usuario": self.db_dev_user,
                "senha": self.db_dev_password,
            },
            "HOM": {
                "servidor": self.db_hom_host,
                "porta": self.db_hom_port,
                "nome_servico": self.db_hom_service_name,
                "usuario": self.db_hom_user,
                "senha": self.db_hom_password,
            },
            "PROD": {
                "servidor": self.db_prod_host,
                "porta": self.db_prod_port,
                "nome_servico": self.db_prod_service_name,
                "usuario": self.db_prod_user,
                "senha": self.db_prod_password,
            },
        }
        if ambiente not in mapeamento:
            raise ValueError(f"Ambiente desconhecido: {cd_ambiente}")
        return mapeamento[ambiente]


@lru_cache(maxsize=1)
def obter_configuracoes() -> Configuracoes:
    """
    Retorna instância singleton das configurações.
    O cache garante que o arquivo .env seja lido apenas uma vez por processo.

    Em caso de mudança no .env durante desenvolvimento, reinicie o servidor
    completamente (Ctrl+C + uvicorn novamente) para limpar o cache.
    """
    return Configuracoes()
