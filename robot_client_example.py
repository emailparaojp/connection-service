"""
Exemplo completo de sistema/robô cliente do connection-service.

Este arquivo demonstra como um sistema deve:
  1. Ler a FERNET_KEY do ambiente local
  2. Solicitar a conexão criptografada ao connection-service
  3. Descriptografar a resposta
  4. Converter o JSON para objeto Python
  5. Conectar ao Oracle usando oracledb

Dependências necessárias no sistema/robô:
  pip install cryptography requests oracledb python-dotenv

Variáveis de ambiente necessárias no sistema/robô:
  FERNET_KEY               — a mesma chave configurada no connection-service
  NM_SISTEMA               — nome do sistema (ex: robo-financeiro)
  CHAVE_API                — chave de API do sistema
  URL_CONNECTION_SERVICE   — URL base do connection-service
  CD_AMBIENTE              — DEV, HOM ou PROD
"""

import json
import logging
import os
import sys
from dataclasses import dataclass
from typing import Optional

import oracledb
import requests
from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv

# Carrega variáveis de ambiente do .env local do sistema (se existir)
load_dotenv()

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("sistema-cliente")


# ------------------------------------------------------------------
# Configuração do sistema
# ------------------------------------------------------------------

@dataclass
class ConfiguracaoSistema:
    """Configurações do sistema lidas das variáveis de ambiente."""

    chave_fernet: str
    nm_sistema: str
    chave_api: str
    url_connection_service: str
    cd_ambiente: str
    timeout_requisicao: int = 10  # segundos


def carregar_configuracao_sistema() -> ConfiguracaoSistema:
    """
    Carrega e valida as configurações do sistema a partir das variáveis de ambiente.

    Raises:
        SystemExit: Se alguma variável obrigatória estiver ausente.
    """
    variaveis = {
        "FERNET_KEY": os.getenv("FERNET_KEY"),
        "NM_SISTEMA": os.getenv("NM_SISTEMA"),
        "CHAVE_API": os.getenv("CHAVE_API"),
        "URL_CONNECTION_SERVICE": os.getenv("URL_CONNECTION_SERVICE", "http://localhost:8080"),
        "CD_AMBIENTE": os.getenv("CD_AMBIENTE", "DEV"),
    }

    ausentes = [chave for chave, valor in variaveis.items() if not valor]
    if ausentes:
        logger.critical("Variáveis de ambiente obrigatórias ausentes: %s", ausentes)
        sys.exit(1)

    return ConfiguracaoSistema(
        chave_fernet=variaveis["FERNET_KEY"],
        nm_sistema=variaveis["NM_SISTEMA"],
        chave_api=variaveis["CHAVE_API"],
        url_connection_service=variaveis["URL_CONNECTION_SERVICE"].rstrip("/"),
        cd_ambiente=variaveis["CD_AMBIENTE"],
    )


# ------------------------------------------------------------------
# Cliente do connection-service
# ------------------------------------------------------------------

class ClienteConnectionService:
    """
    Cliente HTTP para o connection-service.
    Solicita, descriptografa e retorna a configuração de conexão Oracle.
    """

    def __init__(self, configuracao: ConfiguracaoSistema) -> None:
        self._configuracao = configuracao
        self._fernet = self._inicializar_fernet(configuracao.chave_fernet)

    @staticmethod
    def _inicializar_fernet(chave_fernet: str) -> Fernet:
        """
        Inicializa o Fernet com a chave local do sistema.

        Raises:
            SystemExit: Se a chave for inválida.
        """
        try:
            return Fernet(chave_fernet.encode())
        except Exception as exc:
            logger.critical("FERNET_KEY inválida: %s", exc)
            sys.exit(1)

    def solicitar_conexao(self) -> dict:
        """
        Solicita a conexão criptografada ao connection-service,
        descriptografa e retorna o dicionário de configuração Oracle.

        Fluxo:
            1. POST /api/v1/conexao com nm_sistema, chave_api, cd_ambiente
            2. Recebe conexao_criptografada
            3. Descriptografa com FERNET_KEY local
            4. Retorna dict com servidor, porta, nome_servico, usuario, senha

        Returns:
            Dicionário com as configurações de conexão Oracle.

        Raises:
            SystemExit: Em caso de falha irrecuperável.
        """
        endpoint = f"{self._configuracao.url_connection_service}/api/v1/conexao"

        corpo = {
            "nm_sistema": self._configuracao.nm_sistema,
            "chave_api": self._configuracao.chave_api,
            "cd_ambiente": self._configuracao.cd_ambiente,
        }

        logger.info(
            "Solicitando conexão | nm_sistema=%s | cd_ambiente=%s | url=%s",
            self._configuracao.nm_sistema,
            self._configuracao.cd_ambiente,
            endpoint,
        )

        # --- Requisição HTTP ---
        try:
            resposta = requests.post(
                endpoint,
                json=corpo,
                timeout=self._configuracao.timeout_requisicao,
                headers={"Content-Type": "application/json"},
            )
        except requests.exceptions.ConnectionError:
            logger.critical(
                "Não foi possível conectar ao connection-service: %s", endpoint
            )
            sys.exit(1)
        except requests.exceptions.Timeout:
            logger.critical(
                "Timeout ao conectar ao connection-service (limite: %ds)",
                self._configuracao.timeout_requisicao,
            )
            sys.exit(1)
        except requests.exceptions.RequestException as exc:
            logger.critical("Erro na requisição ao connection-service: %s", exc)
            sys.exit(1)

        # --- Validação do código HTTP ---
        if resposta.status_code == 401:
            logger.critical(
                "Autenticação negada pelo connection-service. "
                "Verifique NM_SISTEMA e CHAVE_API."
            )
            sys.exit(1)

        if resposta.status_code == 403:
            logger.critical(
                "Ambiente '%s' não autorizado para o sistema '%s'.",
                self._configuracao.cd_ambiente,
                self._configuracao.nm_sistema,
            )
            sys.exit(1)

        if resposta.status_code == 429:
            logger.critical(
                "Limite de requisições excedido. Aguarde antes de tentar novamente."
            )
            sys.exit(1)

        if resposta.status_code != 200:
            logger.critical(
                "Resposta inesperada do connection-service: HTTP %d | corpo=%s",
                resposta.status_code,
                resposta.text[:200],
            )
            sys.exit(1)

        # --- Parse do JSON de resposta ---
        try:
            dados = resposta.json()
        except ValueError:
            logger.critical("Resposta do connection-service não é JSON válido.")
            sys.exit(1)

        if not dados.get("sucesso"):
            logger.critical(
                "connection-service retornou erro: %s",
                dados.get("mensagem", "Sem mensagem"),
            )
            sys.exit(1)

        conexao_criptografada: Optional[str] = dados.get("conexao_criptografada")
        if not conexao_criptografada:
            logger.critical("Campo 'conexao_criptografada' ausente na resposta.")
            sys.exit(1)

        logger.info("Token criptografado recebido com sucesso.")

        # --- Descriptografia local ---
        return self._descriptografar_conexao(conexao_criptografada)

    def _descriptografar_conexao(self, token_criptografado: str) -> dict:
        """
        Descriptografa o token Fernet recebido do connection-service.

        Args:
            token_criptografado: Token Fernet base64url.

        Returns:
            Dicionário com os dados de conexão Oracle.

        Raises:
            SystemExit: Se o token for inválido.
        """
        try:
            bytes_descriptografados = self._fernet.decrypt(
                token_criptografado.encode("utf-8")
            )
            dados_conexao = json.loads(bytes_descriptografados.decode("utf-8"))
            logger.info(
                "Conexão descriptografada | servidor=%s | porta=%s | nome_servico=%s",
                dados_conexao.get("servidor"),
                dados_conexao.get("porta"),
                dados_conexao.get("nome_servico"),
            )
            return dados_conexao
        except InvalidToken:
            logger.critical(
                "Falha ao descriptografar token. "
                "Verifique se FERNET_KEY do sistema corresponde à chave do connection-service."
            )
            sys.exit(1)
        except (json.JSONDecodeError, KeyError) as exc:
            logger.critical("Dados de conexão descriptografados são inválidos: %s", exc)
            sys.exit(1)


# ------------------------------------------------------------------
# Conexão Oracle
# ------------------------------------------------------------------

def conectar_oracle(dados_conexao: dict) -> oracledb.Connection:
    """
    Estabelece conexão com o Oracle usando as configurações descriptografadas.

    Args:
        dados_conexao: Dicionário com servidor, porta, nome_servico, usuario, senha.

    Returns:
        Objeto de conexão oracledb ativo.

    Raises:
        SystemExit: Se a conexão falhar.
    """
    campos_obrigatorios = ["servidor", "porta", "nome_servico", "usuario", "senha"]
    ausentes = [c for c in campos_obrigatorios if not dados_conexao.get(c)]
    if ausentes:
        logger.critical(
            "Campos obrigatórios ausentes na configuração Oracle: %s", ausentes
        )
        sys.exit(1)

    logger.info(
        "Conectando ao Oracle | servidor=%s | porta=%s | nome_servico=%s | usuario=%s",
        dados_conexao["servidor"],
        dados_conexao["porta"],
        dados_conexao["nome_servico"],
        dados_conexao["usuario"],
    )

    try:
        conexao = oracledb.connect(
            user=dados_conexao["usuario"],
            password=dados_conexao["senha"],
            host=dados_conexao["servidor"],
            port=int(dados_conexao["porta"]),
            service_name=dados_conexao["nome_servico"],
        )
        logger.info("Conexão Oracle estabelecida com sucesso.")
        return conexao

    except oracledb.DatabaseError as exc:
        (erro,) = exc.args
        logger.critical(
            "Falha ao conectar ao Oracle | codigo=%s | mensagem=%s",
            getattr(erro, "code", "N/A"),
            getattr(erro, "message", str(exc)),
        )
        sys.exit(1)


# ------------------------------------------------------------------
# Exemplo de uso completo
# ------------------------------------------------------------------

def executar_consulta_exemplo(conexao: oracledb.Connection) -> None:
    """
    Demonstra o uso da conexão Oracle após a descriptografia.
    Substitua pelo código real do seu sistema/robô.
    """
    try:
        with conexao.cursor() as cursor:
            cursor.execute("SELECT SYSDATE FROM DUAL")
            linha = cursor.fetchone()
            logger.info("Consulta de teste bem-sucedida | SYSDATE=%s", linha[0])
    except oracledb.DatabaseError as exc:
        logger.error("Erro na consulta Oracle: %s", exc)
    finally:
        conexao.close()
        logger.info("Conexão Oracle encerrada.")


def principal() -> None:
    """
    Ponto de entrada do sistema/robô.

    Fluxo completo:
      1. Carrega configuração das variáveis de ambiente
      2. Solicita conexão criptografada ao connection-service
      3. Descriptografa com FERNET_KEY local
      4. Conecta ao Oracle
      5. Executa lógica de negócio do sistema
    """
    logger.info("=" * 55)
    logger.info("Iniciando sistema cliente")
    logger.info("=" * 55)

    # 1. Carrega configurações locais
    configuracao = carregar_configuracao_sistema()
    logger.info(
        "Sistema: %s | Ambiente: %s",
        configuracao.nm_sistema,
        configuracao.cd_ambiente,
    )

    # 2. Solicita e descriptografa conexão
    cliente = ClienteConnectionService(configuracao)
    dados_conexao = cliente.solicitar_conexao()

    # 3. Conecta ao Oracle
    conexao_oracle = conectar_oracle(dados_conexao)

    # 4. Executa lógica do sistema (substitua pelo código real)
    executar_consulta_exemplo(conexao_oracle)

    logger.info("Sistema finalizado com sucesso.")


if __name__ == "__main__":
    principal()
