"""
Serviço de autenticação e autorização.
Orquestra a validação do sistema delegando para o módulo auth.py
e traduz os resultados em exceções de domínio.
"""

import logging
from typing import Optional

from app.auth import (
    MOTIVO_AMBIENTE_NAO_PERMITIDO,
    MOTIVO_CHAVE_API_INVALIDA,
    MOTIVO_SISTEMA_NAO_ENCONTRADO,
    ResultadoAutenticacao,
    validar_sistema,
)
from app.exceptions import (
    ErroAmbienteNaoPermitido,
    ErroChaveApiInvalida,
    ErroSistemaNaoEncontrado,
)

logger = logging.getLogger(__name__)


class ServicoAutenticacao:
    """
    Serviço responsável por autenticar e autorizar sistemas/robôs.

    Centraliza a lógica de validação e lança exceções de domínio
    que serão capturadas pelos handlers globais de exceção.
    """

    def autenticar(
        self,
        nm_sistema: str,
        chave_api: str,
        cd_ambiente: str,
    ) -> ResultadoAutenticacao:
        """
        Autentica o sistema e verifica sua autorização para o ambiente.

        Fluxo:
            1. Verifica se o sistema existe nos registros.
            2. Valida a chave de API via comparação em tempo constante.
            3. Verifica se o ambiente solicitado está nos permitidos.

        Args:
            nm_sistema:  Nome do sistema (normalizado para lowercase).
            chave_api:   Chave de API fornecida pelo sistema.
            cd_ambiente: Ambiente Oracle solicitado (DEV/HOM/PROD).

        Returns:
            ResultadoAutenticacao com cd_status SUCESSO.

        Raises:
            ErroSistemaNaoEncontrado:   Se o sistema não estiver registrado.
            ErroChaveApiInvalida:       Se a chave de API for inválida.
            ErroAmbienteNaoPermitido:   Se o ambiente não for permitido para o sistema.
        """
        resultado = validar_sistema(nm_sistema, chave_api, cd_ambiente)

        if not resultado.autorizado:
            self._lancar_por_motivo(resultado.cd_motivo, nm_sistema, cd_ambiente)

        return resultado

    @staticmethod
    def _lancar_por_motivo(
        cd_motivo: str,
        nm_sistema: str,
        cd_ambiente: Optional[str] = None,
    ) -> None:
        """
        Converte o código de motivo em exceção de domínio apropriada.

        Args:
            cd_motivo:   Código de motivo retornado por validar_sistema.
            nm_sistema:  Nome do sistema (para mensagem de log).
            cd_ambiente: Ambiente solicitado (para mensagem de log).
        """
        if cd_motivo == MOTIVO_SISTEMA_NAO_ENCONTRADO:
            raise ErroSistemaNaoEncontrado(
                f"Sistema não encontrado: '{nm_sistema}'"
            )
        if cd_motivo == MOTIVO_CHAVE_API_INVALIDA:
            raise ErroChaveApiInvalida(
                f"Chave de API inválida para o sistema: '{nm_sistema}'"
            )
        if cd_motivo == MOTIVO_AMBIENTE_NAO_PERMITIDO:
            raise ErroAmbienteNaoPermitido(
                f"Sistema '{nm_sistema}' não autorizado para o ambiente '{cd_ambiente}'"
            )
        # Motivo desconhecido — lança como chave inválida para não vazar informações
        raise ErroChaveApiInvalida(
            f"Autorização negada para o sistema: '{nm_sistema}'"
        )
