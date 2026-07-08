import secrets
from datetime import timedelta

from db.repositories import password_reset_repository

from .. import storage
from ..config import APP_BASE_URL, PASSWORD_MIN, RESET_TOKEN_EXP_MINUTES
from ..mailer import enviar_email
from ..security import hash_password
from ..time_utils import get_brasilia_time

"""Fluxo de 'esqueci minha senha' por e-mail. Sempre responde de forma
genérica pro solicitante (nunca revela se o e-mail existe na base) —
quem decide se o e-mail existe ou não é só o log de auditoria, do lado
do admin."""


def solicitar_reset(email: str) -> None:
    email = (email or '').strip().lower()
    if not email:
        return
    users = storage.load_users()
    user = next(
        (u for u in users if (u.get('email') or '').strip().lower() == email and u.get('ativo', True)),
        None,
    )
    if not user:
        return

    token = secrets.token_urlsafe(32)
    agora = get_brasilia_time().replace(tzinfo=None)
    expira_em = agora + timedelta(minutes=RESET_TOKEN_EXP_MINUTES)

    password_reset_repository.invalidar_tokens_do_usuario(user['id'])
    password_reset_repository.criar_token(token, user['id'], agora, expira_em)

    link = f'{APP_BASE_URL}/resetar-senha/{token}'
    corpo_html = f"""
    <p>Olá, {user['name']}.</p>
    <p>Recebemos uma solicitação para redefinir a senha da sua conta no Sistema Tickets.</p>
    <p><a href="{link}">Clique aqui para criar uma nova senha</a></p>
    <p>Esse link expira em {RESET_TOKEN_EXP_MINUTES} minutos e só pode ser usado uma vez.</p>
    <p>Se você não pediu essa redefinição, pode ignorar este e-mail com segurança.</p>
    """
    enviar_email(user['email'], 'Redefinição de senha — Sistema Tickets', corpo_html)


def validar_token(token: str):
    agora = get_brasilia_time().replace(tzinfo=None)
    user_id = password_reset_repository.obter_token_valido(token, agora)
    if not user_id:
        return None
    return next((u for u in storage.load_users() if u['id'] == user_id), None)


def redefinir_senha(token: str, nova_senha: str, confirmar_senha: str):
    user = validar_token(token)
    if not user:
        return False, 'token_invalido'
    if nova_senha != confirmar_senha:
        return False, 'senhas_diferentes'
    if len(nova_senha or '') < PASSWORD_MIN:
        return False, 'senha_curta'

    users = storage.load_users()
    for u in users:
        if u['id'] == user['id']:
            u['password'] = hash_password(nova_senha)
    storage.save_users(users)
    password_reset_repository.marcar_usado(token)
    return True, None
