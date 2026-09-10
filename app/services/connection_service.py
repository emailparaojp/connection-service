"""
Serviço de conexão Oracle.
Orquestra o fluxo completo de uma solicitação de conexão:

  1. Autentica e autoriza o sistema (ServicoAutenticacao)
  2. Registra auditoria (ServicoAuditoria)
  3. Obtém as credenciais Oracle para o ambiente (config)
  4. Criptografa a string de conexão (ServicoCriptografia)
  5. Retorna apenas o token criptografado

Nunca retorna credenciais em texto puro.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.auth import (
    MOTIVO_AMBIENTE_NAO_PERMITIDO,
    MOTIVO_CHAVE_API_INVALIDA,
    MOTIVO_SISTEMA_NAO_ENCONTRADO,
)
from app.config import obter_configuracoes
from app.crypto import obter_servico_criptografia
from app.exceptions import (
    ErroConstrucaoConexao,
    ErroCriptografia,
    ErroAmbienteNaoPermitido,
    ErroChaveApiInvalida,
    ErroSistemaNaoEncontrado,
)
from app.schemas import RequisicaoConexao, RespostaConexaoSucesso
from app.services.audit_service import ServicoAuditoria
from app.services.auth_service import ServicoAutenticacao

logger = logging.getLogger(__name__)


class ServicoConexao:
    """
    Serviço principal de orquestração do fluxo de conexão Oracle.

    Compõe ServicoAutenticacao, ServicoAuditoria e ServicoCriptografia
    para entregar conexões criptografadas de forma auditada e segura.
    """

    def __init__(self, sessao: Session) -> None:
        self._servico_autenticacao = ServicoAutenticacao()
        self._servico_auditoria = ServicoAuditoria(sessao)
        self._servico_criptografia = obter_servico_criptografia()
        self._configuracoes = obter_configuracoes()

    def processar_solicitacao_conexao(
        self,
        requisicao: RequisicaoConexao,
        ip_requisicao: str,
        id_correlacao: Optional[str] = None,
    ) -> RespostaConexaoSucesso:
        """
        Processa uma solicitação de conexão Oracle de ponta a ponta.

        Fluxo:
            1. Autenticar e autorizar o sistema
            2. Registrar auditoria (sucesso ou falha)
            3. Obter configuração Oracle do ambiente
            4. Criptografar os dados de conexão
            5. Retornar apenas o token criptografado

        Args:
            requisicao:     Dados da requisição (nm_sistema, chave_api, cd_ambiente).
            ip_requisicao:  IP do cliente para auditoria.
            id_correlacao:  ID de correlação para rastreamento.

        Returns:
            RespostaConexaoSucesso com o token criptografado.

        Raises:
            ErroSistemaNaoEncontrado:   Sistema não registrado.
            ErroChaveApiInvalida:       Chave de API inválida.
            ErroAmbienteNaoPermitido:   Ambiente não permitido.
            ErroConstrucaoConexao:      Falha ao obter configuração Oracle.
            ErroCriptografia:           Falha na criptografia.
        """
        nm_sistema = requisicao.nm_sistema
        cd_ambiente = requisicao.cd_ambiente

        # --- Etapa 1: Autenticação e Autorização ---
        try:
            self._servico_autenticacao.autenticar(
                nm_sistema=nm_sistema,
                chave_api=requisicao.chave_api,
                cd_ambiente=cd_ambiente,
            )
        except (ErroSistemaNaoEncontrado, ErroChaveApiInvalida) as exc:
            self._servico_auditoria.registrar_negacao(
                nm_sistema=nm_sistema,
                cd_ambiente=cd_ambiente,
                ip_requisicao=ip_requisicao,
                cd_motivo=MOTIVO_CHAVE_API_INVALIDA
                if isinstance(exc, ErroChaveApiInvalida)
                else MOTIVO_SISTEMA_NAO_ENCONTRADO,
                id_correlacao=id_correlacao,
            )
            raise

        except ErroAmbienteNaoPermitido:
            self._servico_auditoria.registrar_negacao(
                nm_sistema=nm_sistema,
                cd_ambiente=cd_ambiente,
                ip_requisicao=ip_requisicao,
                cd_motivo=MOTIVO_AMBIENTE_NAO_PERMITIDO,
                id_correlacao=id_correlacao,
            )
            raise

        # --- Etapa 2: Obter configuração Oracle ---
        try:
            config_oracle = self._configuracoes.obter_config_oracle(nm_sistema, cd_ambiente)
        except Exception as exc:
            logger.error(
                "Falha ao obter configuração Oracle | cd_ambiente=%s | erro=%s",
                cd_ambiente,
                exc,
            )
            self._servico_auditoria.registrar_erro(
                nm_sistema=nm_sistema,
                cd_ambiente=cd_ambiente,
                ip_requisicao=ip_requisicao,
                id_correlacao=id_correlacao,
            )
            raise ErroConstrucaoConexao(
                f"Não foi possível obter a configuração Oracle para '{cd_ambiente}'"
            ) from exc

        # --- Etapa 3: Criptografar os dados de conexão ---
        try:
            conexao_criptografada = self._servico_criptografia.criptografar_conexao(config_oracle)
        except Exception as exc:
            logger.error(
                "Falha ao criptografar conexão | nm_sistema=%s | cd_ambiente=%s | erro=%s",
                nm_sistema,
                cd_ambiente,
                exc,
            )
            self._servico_auditoria.registrar_erro(
                nm_sistema=nm_sistema,
                cd_ambiente=cd_ambiente,
                ip_requisicao=ip_requisicao,
                id_correlacao=id_correlacao,
            )
            raise ErroCriptografia("Falha ao criptografar os dados de conexão.") from exc

        # --- Etapa 4: Registrar auditoria de sucesso ---
        self._servico_auditoria.registrar_sucesso(
            nm_sistema=nm_sistema,
            cd_ambiente=cd_ambiente,
            ip_requisicao=ip_requisicao,
            id_correlacao=id_correlacao,
        )

        logger.info(
            "Conexão entregue com sucesso | nm_sistema=%s | cd_ambiente=%s | id_correlacao=%s",
            nm_sistema,
            cd_ambiente,
            id_correlacao,
        )

        return RespostaConexaoSucesso(
            sucesso=True,
            cd_ambiente=cd_ambiente,
            conexao_criptografada=conexao_criptografada,
        )
