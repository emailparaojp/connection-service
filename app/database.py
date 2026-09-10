"""
Configuração do banco de dados SQLite para auditoria.
Utiliza SQLAlchemy com suporte a conexões via thread pool.
"""

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import obter_configuracoes

logger = logging.getLogger(__name__)


def _criar_engine():
    """
    Cria o engine SQLAlchemy de forma lazy.
    Garante que obter_configuracoes() seja chamado apenas quando
    o módulo for efetivamente utilizado, e não na importação.
    """
    configuracoes = obter_configuracoes()
    return create_engine(
        configuracoes.sqlite_database_url,
        connect_args={"check_same_thread": False},
        echo=False,
        pool_pre_ping=True,
    )


# Cria engine SQLite com suporte a múltiplas threads (necessário para FastAPI)
engine = _criar_engine()


# Habilita WAL mode no SQLite para melhor concorrência
@event.listens_for(engine, "connect")
def configurar_pragma_sqlite(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


# Factory de sessões
FabricaSessao = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    """Classe base para todos os modelos ORM."""
    pass


def inicializar_banco() -> None:
    """
    Inicializa o banco de dados criando todas as tabelas.
    Deve ser chamado na inicialização da aplicação.
    """
    from app.models import RegistroAuditoria  # noqa: F401 — importa para registrar o modelo

    Base.metadata.create_all(bind=engine)
    logger.info("Banco de dados SQLite inicializado com sucesso.")


@contextmanager
def obter_sessao_banco() -> Generator[Session, None, None]:
    """
    Context manager que fornece uma sessão de banco de dados.
    Garante commit/rollback e fechamento correto da sessão.

    Uso:
        with obter_sessao_banco() as sessao:
            sessao.add(objeto)
    """
    sessao = FabricaSessao()
    try:
        yield sessao
        sessao.commit()
    except Exception as exc:
        sessao.rollback()
        logger.error("Erro na sessão do banco de dados: %s", exc)
        raise
    finally:
        sessao.close()


def obter_banco() -> Generator[Session, None, None]:
    """
    Dependency injection para FastAPI.
    Fornece sessão de banco gerenciada por request.

    Uso nas rotas:
        def minha_rota(db: Session = Depends(obter_banco)):
            ...
    """
    sessao = FabricaSessao()
    try:
        yield sessao
        sessao.commit()
    except Exception:
        sessao.rollback()
        raise
    finally:
        sessao.close()
