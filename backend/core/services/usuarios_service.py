import uuid

from ..config import PASSWORD_MIN, ROLES_VALIDOS
from .. import storage
from ..security import hash_password

"""Regras de negócio de usuários, compartilhadas entre o controller web
(formulários em Configurações) e o controller de API (JSON + JWT) — para
que as duas superfícies fiquem sempre parametrizáveis e consistentes."""


def listar_usuarios(incluir_senha: bool = False) -> list:
    users = storage.load_users()
    if incluir_senha:
        return users
    return [{k: v for k, v in u.items() if k != 'password'} for u in users]


def criar_usuario(username: str, password: str, name: str, role: str,
                   email: str = '', perfil_id: str | None = None):
    username = (username or '').strip()
    password = (password or '').strip()
    name = (name or '').strip()
    perfil_id = (perfil_id or '').strip() or None

    if not (username and password and name):
        return False, 'campos_obrigatorios', None
    if len(password) < PASSWORD_MIN:
        return False, 'senha_curta', None

    users = storage.load_users()
    if any(u['username'] == username for u in users):
        return False, 'usuario_existe', None

    if role not in ROLES_VALIDOS:
        role = 'funcionario'

    if perfil_id:
        cfg = storage.load_config()
        if not any(p['id'] == perfil_id for p in cfg.get('perfis', [])):
            perfil_id = None

    novo = {
        'id': str(uuid.uuid4()), 'username': username,
        'password': hash_password(password), 'name': name,
        'role': role, 'email': (email or '').strip(), 'ativo': True,
    }
    if perfil_id:
        novo['perfil_id'] = perfil_id
    users.append(novo)
    storage.save_users(users)
    return True, None, {k: v for k, v in novo.items() if k != 'password'}


def toggle_usuario(user_id: str, current_user_id: str):
    if user_id == current_user_id:
        return False, 'nao_pode_alterar_proprio_status'
    users = storage.load_users()
    user = next((u for u in users if u['id'] == user_id), None)
    if not user:
        return False, 'usuario_nao_encontrado'
    user['ativo'] = not user.get('ativo', True)
    storage.save_users(users)
    return True, None


def alterar_senha(user_id: str, nova_senha: str):
    nova_senha = (nova_senha or '').strip()
    users = storage.load_users()
    user = next((u for u in users if u['id'] == user_id), None)
    if not user:
        return False, 'usuario_nao_encontrado'
    if len(nova_senha) < PASSWORD_MIN:
        return False, 'senha_curta'
    user['password'] = hash_password(nova_senha)
    storage.save_users(users)
    return True, None


def alterar_perfil_usuario(user_id: str, perfil_id: str | None):
    users = storage.load_users()
    user = next((u for u in users if u['id'] == user_id), None)
    if not user:
        return False, 'usuario_nao_encontrado'

    perfil_id = (perfil_id or '').strip() or None
    if perfil_id:
        cfg = storage.load_config()
        if not any(p['id'] == perfil_id for p in cfg.get('perfis', [])):
            perfil_id = None

    if perfil_id:
        user['perfil_id'] = perfil_id
    elif 'perfil_id' in user:
        del user['perfil_id']
    storage.save_users(users)
    return True, None


def excluir_usuario(user_id: str, current_user_id: str):
    if user_id == current_user_id:
        return False, 'nao_pode_excluir_proprio_usuario'
    users = storage.load_users()
    if not any(u['id'] == user_id for u in users):
        return False, 'usuario_nao_encontrado'
    users = [u for u in users if u['id'] != user_id]
    storage.save_users(users)
    return True, None
