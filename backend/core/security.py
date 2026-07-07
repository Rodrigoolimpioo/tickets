import hmac
import ipaddress
import secrets
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import g, jsonify, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from .config import (
    HEX_COLOR_RE, JWT_ALGORITHM, JWT_EXP_HOURS, JWT_SECRET_KEY, PERMISSOES_IDS,
    TIME_RE, _LOGIN_LOCKOUT_MIN, _LOGIN_MAX,
)
from .time_utils import get_brasilia_time
from . import storage

_login_attempts: dict = defaultdict(list)


# ─────────────────────────────────────────
#  VALIDAÇÃO
# ─────────────────────────────────────────

def valid_hex(value: str, default: str) -> str:
    return value if HEX_COLOR_RE.match(value or '') else default


def valid_ip(ip: str) -> bool:
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def valid_time(val: str) -> bool:
    return bool(TIME_RE.match(val or ''))


# ─────────────────────────────────────────
#  SENHAS
# ─────────────────────────────────────────

def _is_hashed(stored: str) -> bool:
    return stored.startswith(('pbkdf2:', 'scrypt:', 'argon2'))


def verify_password(stored: str, provided: str) -> bool:
    if _is_hashed(stored):
        return check_password_hash(stored, provided)
    return stored == provided


def hash_password(password: str) -> str:
    return generate_password_hash(password)


# ─────────────────────────────────────────
#  RATE LIMIT DE LOGIN
# ─────────────────────────────────────────

def rate_limit_exceeded(ip: str) -> bool:
    now = datetime.utcnow()
    cutoff = now - timedelta(minutes=_LOGIN_LOCKOUT_MIN)
    _login_attempts[ip] = [t for t in _login_attempts[ip] if t > cutoff]
    return len(_login_attempts[ip]) >= _LOGIN_MAX


def register_failed_login(ip: str) -> None:
    _login_attempts[ip].append(datetime.utcnow())


# ─────────────────────────────────────────
#  CSRF (cookies de sessão)
# ─────────────────────────────────────────

def get_csrf_token() -> str:
    if '_csrf' not in session:
        session['_csrf'] = secrets.token_hex(32)
    return session['_csrf']


def csrf_valid(token: str) -> bool:
    return bool(token) and hmac.compare_digest(token, get_csrf_token())


# ─────────────────────────────────────────
#  PERMISSÕES POR PERFIL (roles/claims)
# ─────────────────────────────────────────

def get_user_permissoes(user: dict) -> list:
    """Retorna a lista de permissões (módulos liberados) do usuário com
    base no perfil atribuído. Usada tanto para montar a sessão web quanto
    as claims do token JWT — é a mesma fonte de verdade nos dois casos."""
    if user.get('role') == 'admin':
        return PERMISSOES_IDS[:]

    perfil_id = user.get('perfil_id')
    if perfil_id:
        cfg = storage.load_config()
        perfil = next((p for p in cfg.get('perfis', []) if p['id'] == perfil_id), None)
        if perfil:
            return perfil.get('permissoes', [])

    # Fallback por role, caso o usuário não tenha um perfil customizado
    role = user.get('role', 'funcionario')
    if role == 'supervisor':
        return ['dashboard', 'acompanhamento', 'ver_ticket', 'atualizar_ticket', 'comentar_ticket', 'meu_perfil']
    return ['dashboard', 'abrir_ticket', 'acompanhamento', 'ver_ticket', 'comentar_ticket', 'meu_perfil']


# ─────────────────────────────────────────
#  TOKEN JWT — geração e validação
# ─────────────────────────────────────────

def generate_token(user: dict) -> dict:
    """Gera um JWT contendo as claims de identidade e autorização do usuário
    (role + lista de permissões do perfil atual). Qualquer cliente (frontend
    SPA, app mobile, integração externa) usa esse token via
    `Authorization: Bearer <token>` para acessar os endpoints em /api/*."""
    permissoes = get_user_permissoes(user)
    now = datetime.now(timezone.utc)
    expires_delta = timedelta(hours=JWT_EXP_HOURS)
    payload = {
        'sub': user['id'],
        'username': user['username'],
        'name': user['name'],
        'role': user['role'],
        'perfil_id': user.get('perfil_id'),
        'permissoes': permissoes,
        'iat': now,
        'exp': now + expires_delta,
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return {
        'access_token': token,
        'token_type': 'Bearer',
        'expires_in': int(expires_delta.total_seconds()),
        'claims': payload,
    }


def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])


# ─────────────────────────────────────────
#  RESPOSTA DE ACESSO NEGADO (web x api)
# ─────────────────────────────────────────

def deny_response(motivo: str, status: int = 403, **ctx):
    if request.path.startswith('/api/'):
        payload = {'error': motivo}
        if 'ip' in ctx:
            payload['ip'] = ctx['ip']
        return jsonify(payload), status
    return render_template(
        'acesso_negado.html', motivo=motivo,
        hora=get_brasilia_time().strftime('%d/%m/%Y %H:%M:%S'), **ctx
    ), status


# ─────────────────────────────────────────
#  DECORATORS — autenticação por SESSÃO (telas web)
# ─────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        from flask import redirect, url_for
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if session.get('role') not in roles:
                return deny_response('permissao')
            return f(*args, **kwargs)
        return decorated
    return decorator


def permission_required(perm):
    """Verifica se o usuário da sessão tem a permissão. Admin sempre passa."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if session.get('role') == 'admin':
                return f(*args, **kwargs)
            if perm not in session.get('permissoes', []):
                return deny_response('permissao')
            return f(*args, **kwargs)
        return decorated
    return decorator


# ─────────────────────────────────────────
#  DECORATORS — autenticação por TOKEN (API)
# ─────────────────────────────────────────

def jwt_required(f):
    """Exige um Bearer token válido. Popula flask.g.jwt_claims com as
    claims (role, permissoes, etc.) decodificadas do token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'token_ausente'}), 401
        token = auth_header[len('Bearer '):].strip()
        try:
            claims = decode_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'token_expirado'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'token_invalido'}), 401
        g.jwt_claims = claims
        return f(*args, **kwargs)
    return decorated


def api_role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            claims = getattr(g, 'jwt_claims', None) or {}
            if claims.get('role') not in roles:
                return jsonify({'error': 'permissao_negada'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


def api_permission_required(perm):
    """Equivalente ao permission_required, mas lendo as claims do JWT
    em vez da sessão — usado nas rotas de /api/*. Admin sempre passa."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            claims = getattr(g, 'jwt_claims', None) or {}
            if claims.get('role') == 'admin':
                return f(*args, **kwargs)
            if perm not in claims.get('permissoes', []):
                return jsonify({'error': 'permissao_negada'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator
