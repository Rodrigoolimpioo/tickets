from datetime import datetime

from ..connection import get_cursor


def criar_token(token: str, user_id: str, criado_em: datetime, expira_em: datetime) -> None:
    with get_cursor(commit=True) as cursor:
        cursor.execute(
            """
            INSERT INTO PASSWORD_RESET_TOKENS (TOKEN, USER_ID, CRIADO_EM, EXPIRA_EM, USADO)
            VALUES (:token, :user_id, :criado_em, :expira_em, 0)
            """,
            token=token, user_id=user_id, criado_em=criado_em, expira_em=expira_em,
        )


def obter_token_valido(token: str, agora: datetime):
    """Retorna o USER_ID se o token existir, não tiver sido usado e não
    estiver expirado; caso contrário, None."""
    with get_cursor() as cursor:
        cursor.execute(
            """
            SELECT USER_ID FROM PASSWORD_RESET_TOKENS
            WHERE TOKEN = :token AND USADO = 0 AND EXPIRA_EM > :agora
            """,
            token=token, agora=agora,
        )
        row = cursor.fetchone()
        return row[0] if row else None


def marcar_usado(token: str) -> None:
    with get_cursor(commit=True) as cursor:
        cursor.execute("UPDATE PASSWORD_RESET_TOKENS SET USADO = 1 WHERE TOKEN = :token", token=token)


def invalidar_tokens_do_usuario(user_id: str) -> None:
    """Invalida quaisquer tokens anteriores ainda válidos ao gerar um novo
    (evita que um link antigo continue utilizável em paralelo)."""
    with get_cursor(commit=True) as cursor:
        cursor.execute(
            "UPDATE PASSWORD_RESET_TOKENS SET USADO = 1 WHERE USER_ID = :user_id AND USADO = 0",
            user_id=user_id,
        )
