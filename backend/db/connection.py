"""Conexão com o Oracle Autonomous Database via python-oracledb, sempre
em modo thin (não chama oracledb.init_oracle_client — isso ligaria o modo
thick, que exige o Oracle Instant Client instalado no SO e não é necessário
aqui: o modo thin conversa direto com o wallet)."""
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


@contextlib.contextmanager
def get_connection():
    """Abre uma conexão e garante o fechamento mesmo em caso de erro."""
    connection = oracledb.connect(
        user=DB_USER,
        password=DB_PASSWORD,
        dsn=DB_DSN,
        config_dir=DB_WALLET_DIR,
        wallet_location=DB_WALLET_DIR,
        wallet_password=DB_WALLET_PASSWORD,
    )
    try:
        yield connection
    except oracledb.DatabaseError:
        logger.warning(_AUTONOMOUS_PAUSED_HINT)
        raise
    finally:
        connection.close()


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
    """Converte o resultado de um SELECT em uma lista de dicts com as
    colunas em minúsculo, independente de como o nome foi declarado no SQL."""
    columns = [col[0].lower() for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]
