from flask import Blueprint, redirect, render_template, request, session, url_for

from core import storage
from core.audit import log_evento
from core.security import (
    csrf_valid, deny_response, get_user_permissoes,
    rate_limit_exceeded, register_failed_login, register_rate_limited_event,
    verify_password, hash_password, _is_hashed,
)
from core.config import _LOGIN_LOCKOUT_MIN
from core.services import password_reset_service
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
            if user.get('role') != 'admin':
                cfg = storage.load_config()
                ip_cfg = cfg.get('ip_control', {})
                if ip_cfg.get('enabled', False):
                    client_ip = get_client_ip()
                    allowed = ip_cfg.get('ips', [])
                    if allowed and client_ip not in allowed:
                        error = f'Acesso não permitido para o IP {client_ip}.'
                        return render_template('login.html', error=error)
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
            log_evento('login_sucesso')
            return redirect(url_for('dashboard.dashboard'))

        register_failed_login(client_ip, username=username or None)
        error = 'Usuário ou senha inválidos.'
    return render_template('login.html', error=error)


@auth_bp.route('/logout')
def logout():
    if 'user_id' in session:
        log_evento('logout')
    session.clear()
    return redirect(url_for('auth.login'))


@auth_bp.route('/acesso-negado')
def acesso_negado():
    return render_template('acesso_negado.html', motivo='manual',
                           hora=get_brasilia_time().strftime('%d/%m/%Y %H:%M:%S')), 403


@auth_bp.route('/esqueci-senha', methods=['GET', 'POST'])
def esqueci_senha():
    if 'user_id' in session:
        return redirect(url_for('dashboard.dashboard'))
    enviado = False
    if request.method == 'POST':
        token = request.form.get('_csrf_token', '')
        if not csrf_valid(token):
            return deny_response('csrf')
        client_ip = get_client_ip()
        # Limite mais generoso que o de login (não é força bruta de senha,
        # é só pra não deixar alguém disparar e-mails em looping).
        if not rate_limit_exceeded(client_ip, acao='reset_senha_solicitado', limite=5, janela_minutos=15):
            email = request.form.get('email', '')
            password_reset_service.solicitar_reset(email)
            register_rate_limited_event(client_ip, 'reset_senha_solicitado', detalhes=email)
        enviado = True
    return render_template('esqueci_senha.html', enviado=enviado)


@auth_bp.route('/resetar-senha/<token>', methods=['GET', 'POST'])
def resetar_senha(token):
    if 'user_id' in session:
        return redirect(url_for('dashboard.dashboard'))

    user = password_reset_service.validar_token(token)
    if not user:
        return render_template('resetar_senha.html', invalido=True, token=token)

    error = None
    if request.method == 'POST':
        csrf = request.form.get('_csrf_token', '')
        if not csrf_valid(csrf):
            return deny_response('csrf')
        ok, err = password_reset_service.redefinir_senha(
            token,
            request.form.get('nova_senha', ''),
            request.form.get('confirmar_senha', ''),
        )
        if ok:
            log_evento('usuario_senha_alterada', detalhes=f"{user['username']} (via reset por e-mail)",
                       entidade_tipo='usuario', entidade_id=user['id'],
                       usuario_id=user['id'], usuario_nome=user['name'])
            return render_template('resetar_senha.html', sucesso=True, token=token)
        error = {
            'senhas_diferentes': 'As senhas não coincidem.',
            'senha_curta': 'A senha deve ter pelo menos 8 caracteres.',
            'token_invalido': 'Esse link é inválido ou já expirou.',
        }.get(err, 'Não foi possível redefinir a senha.')

    return render_template('resetar_senha.html', token=token, error=error)
