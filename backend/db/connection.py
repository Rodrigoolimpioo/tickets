"""Conexão com o Oracle Autonomous Database via python-oracledb em modo thin.

Usa connection pool para reutilizar conexões entre requisições — elimina o
overhead de TLS handshake (~300ms) a cada query.
"""
import contextlib
import logging

import oracledb

from core.config import DB_DSN, DB_PASSWORD, DB_USER, DB_WALLET_DIR, DB_WALLET_PASSWORD

logger = logging.getLogger(__name__)

_AUTONOMOUS_PAUSED_HINT = (
    'Falha ao conectar no Oracle Autonomous Database. Se o banco ficou 7 dias '
    'consecutivos sem uso (tier Always Free), ele é pausado automaticamente '
    '(os dados não são perdidos) — reative-o no OCI Console e tente de novo.'
)

_pool: oracledb.ConnectionPool | None = None


def get_pool() -> oracledb.ConnectionPool:
    global _pool
    if _pool is None:
        _pool = oracledb.create_pool(
            user=DB_USER,
            password=DB_PASSWORD,
            dsn=DB_DSN,
            config_dir=DB_WALLET_DIR,
            wallet_location=DB_WALLET_DIR,
            wallet_password=DB_WALLET_PASSWORD,
            min=2,
            max=8,
            increment=1,
        )
        logger.info('Oracle connection pool criado (min=2, max=8).')
    return _pool


@contextlib.contextmanager
def get_connection():
    """Retira uma conexão do pool e devolve ao final."""
    pool = get_pool()
    try:
        connection = pool.acquire()
    except oracledb.DatabaseError:
        logger.warning(_AUTONOMOUS_PAUSED_HINT)
        raise
    try:
        yield connection
    finally:
        pool.release(connection)


@contextlib.contextmanager
def get_cursor(commit: bool = False):
    """Conexão + cursor prontos para uso; comita ao final quando commit=True."""
    with get_connection() as connection:
        cursor = connection.cursor()
        try:
            yield cursor
            if commit:
                connection.commit()
        finally:
            cursor.close()


def rows_to_dicts(cursor) -> list:
    """Converte o resultado de um SELECT em lista de dicts com colunas em minúsculo."""
    columns = [col[0].lower() for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]
