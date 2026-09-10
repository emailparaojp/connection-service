"""
Módulo de criptografia.
Responsável por criptografar e descriptografar strings de conexão Oracle usando Fernet.

Fernet garante:
  - Criptografia simétrica autenticada (AES-128-CBC + HMAC-SHA256)
  - Tokens com timestamp (permitem expiração futura)
  - Impossibilidade de leitura sem a chave correta
"""

import json
import logging
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.config import obter_configuracoes

logger = logging.getLogger(__name__)


class ServicoCriptografia:
    """
    Serviço de criptografia baseado em Fernet.
    Encapsula todas as operações de cifra/decifra da aplicação.
    """

    def __init__(self) -> None:
        configuracoes = obter_configuracoes()
        try:
            self._fernet = Fernet(configuracoes.fernet_key.encode())
        except Exception as exc:
            logger.critical("Falha ao inicializar Fernet — verifique FERNET_KEY: %s", exc)
            raise RuntimeError("Falha ao inicializar o serviço de criptografia.") from exc

    def criptografar_conexao(self, dados_conexao: dict[str, Any]) -> str:
        """
        Recebe um dicionário com os dados de conexão Oracle,
        serializa para JSON e criptografa com Fernet.

        Fluxo:
            dados_conexao (dict)
                → JSON (str)
                → bytes
                → Fernet.encrypt()
                → token criptografado (str)

        Args:
            dados_conexao: Dicionário com servidor, porta, nome_servico, usuario, senha.

        Returns:
            String criptografada em formato Fernet (base64url).

        Raises:
            RuntimeError: Se a criptografia falhar por qualquer motivo.
        """
        try:
            json_str = json.dumps(dados_conexao, ensure_ascii=False)
            token = self._fernet.encrypt(json_str.encode("utf-8"))
            return token.decode("utf-8")
        except Exception as exc:
            logger.error("Erro ao criptografar dados de conexão: %s", exc)
            raise RuntimeError("Falha na criptografia dos dados de conexão.") from exc

    def descriptografar_conexao(self, token_criptografado: str) -> dict[str, Any]:
        """
        Descriptografa um token Fernet e retorna o dicionário de conexão.

        Fluxo:
            token criptografado (str)
                → bytes
                → Fernet.decrypt()
                → JSON (str)
                → dict

        Args:
            token_criptografado: Token Fernet em string base64url.

        Returns:
            Dicionário com os dados de conexão Oracle.

        Raises:
            ValueError: Se o token for inválido ou tiver sido adulterado.
            RuntimeError: Para outros erros inesperados.
        """
        try:
            bytes_descriptografados = self._fernet.decrypt(token_criptografado.encode("utf-8"))
            return json.loads(bytes_descriptografados.decode("utf-8"))
        except InvalidToken as exc:
            logger.warning("Token Fernet inválido ou adulterado.")
            raise ValueError("Token de conexão inválido ou expirado.") from exc
        except Exception as exc:
            logger.error("Erro ao descriptografar token: %s", exc)
            raise RuntimeError("Falha na descriptografia do token de conexão.") from exc


# Instância singleton — inicializada uma única vez
_servico_criptografia: ServicoCriptografia | None = None


def obter_servico_criptografia() -> ServicoCriptografia:
    """
    Retorna a instância singleton do ServicoCriptografia.
    Inicializa na primeira chamada (lazy initialization).
    """
    global _servico_criptografia
    if _servico_criptografia is None:
        _servico_criptografia = ServicoCriptografia()
    return _servico_criptografia
