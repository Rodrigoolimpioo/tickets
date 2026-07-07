from flask import Blueprint, redirect, render_template, request, session, url_for

from core import storage
from core.security import (
    csrf_valid, deny_response, get_user_permissoes,
    rate_limit_exceeded, register_failed_login, verify_password, hash_password,
    _is_hashed,
)
from core.config import _LOGIN_LOCKOUT_MIN
from core.time_utils import get_brasilia_time, get_client_ip

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/')
def index():
    return redirect(url_for('dashboard.dashboard') if 'user_id' in session else url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard.dashboard'))
    error = None
    if request.method == 'POST':
        token = request.form.get('_csrf_token', '')
        if not csrf_valid(token):
            return deny_response('csrf')
        client_ip = get_client_ip()
        if rate_limit_exceeded(client_ip):
            error = f'Muitas tentativas. Aguarde {_LOGIN_LOCKOUT_MIN} minutos.'
            return render_template('login.html', error=error)

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        users = storage.load_users()
        user = next((u for u in users
                     if u['username'] == username and u.get('ativo', True)), None)

        if user and verify_password(user['password'], password):
            if not _is_hashed(user['password']):
                user['password'] = hash_password(password)
                storage.save_users(users)
            permissoes = get_user_permissoes(user)
            session.permanent = True
            session.update({
                'user_id':   user['id'],
                'username':  user['username'],
                'name':      user['name'],
                'role':      user['role'],
                'permissoes': permissoes,
                'perfil_id': user.get('perfil_id'),
            })
            return redirect(url_for('dashboard.dashboard'))

        register_failed_login(client_ip)
        error = 'Usuário ou senha inválidos.'
    return render_template('login.html', error=error)


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))


@auth_bp.route('/acesso-negado')
def acesso_negado():
    return render_template('acesso_negado.html', motivo='manual',
                           hora=get_brasilia_time().strftime('%d/%m/%Y %H:%M:%S')), 403
