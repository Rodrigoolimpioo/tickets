import os

from flask import Flask, request, session

from core import storage
from core.config import (
    FRONTEND_DIR, MAX_CONTENT_LENGTH, PERMISSOES, SECRET_KEY,
    SESSION_LIFETIME, UPLOADS_DIR,
)
from core.security import csrf_valid, deny_response, get_csrf_token
from core.time_utils import get_brasilia_time, get_client_ip
from core.storage import get_role_label

from controllers.auth_controller import auth_bp
from controllers.dashboard_controller import dashboard_bp
from controllers.tickets_controller import tickets_bp
from controllers.config_controller import config_bp
from controllers.usuarios_controller import usuarios_bp
from controllers.perfis_controller import perfis_bp
from controllers.misc_controller import misc_bp
from controllers.api_controller import api_bp

app = Flask(
    __name__,
    template_folder=os.path.join(FRONTEND_DIR, 'templates'),
    static_folder=os.path.join(FRONTEND_DIR, 'static'),
)
app.secret_key = SECRET_KEY
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False   # Mudar para True em produção com HTTPS
app.config['PERMANENT_SESSION_LIFETIME'] = SESSION_LIFETIME
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

os.makedirs(UPLOADS_DIR, exist_ok=True)

# ─────────────────────────────────────────
#  ROTAS — registro dos controllers/blueprints
# ─────────────────────────────────────────

app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(tickets_bp)
app.register_blueprint(config_bp)
app.register_blueprint(usuarios_bp)
app.register_blueprint(perfis_bp)
app.register_blueprint(misc_bp)
app.register_blueprint(api_bp)


app.jinja_env.globals['get_role_label'] = get_role_label
app.jinja_env.globals['PERMISSOES']    = PERMISSOES
app.jinja_env.globals['csrf_token']    = get_csrf_token


@app.context_processor
def inject_global_config():
    cfg = storage.load_config()
    pers = cfg.get('personalizacao', {})
    perfis = cfg.get('perfis', [])
    perfis_dict = {p['id']: p for p in perfis}
    return {
        'cfg_global': cfg,
        'g_nome_sistema': pers.get('nome_sistema', 'Tickets'),
        'g_logo': pers.get('logo_filename'),
        'g_permissoes': session.get('permissoes', []),
        'g_perfis': perfis,
        'g_perfis_dict': perfis_dict,
        'now': get_brasilia_time(),
    }


@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        "font-src 'self' https://cdnjs.cloudflare.com; "
        "img-src 'self' data: blob:; "
        "connect-src 'self';"
    )
    return response


# ─────────────────────────────────────────
#  MIDDLEWARE DE CONTROLE DE ACESSO
# ─────────────────────────────────────────

ENDPOINTS_LIVRES = {
    'static', 'misc.uploaded_file', 'misc.serve_logo',
    'auth.acesso_negado', 'auth.logout', 'api.auth_token',
}


@app.before_request
def check_access_controls():
    if request.endpoint in ENDPOINTS_LIVRES or request.endpoint is None:
        return None

    is_api = request.path.startswith('/api/')

    # Proteção CSRF nos POSTs feitos via cookie de sessão.
    # Rotas /api/* autenticam por Bearer token (sem cookie), então não se
    # aplica — o próprio jwt_required cuida da autenticação delas.
    if request.method == 'POST' and not is_api:
        token = request.form.get('_csrf_token', '') or request.headers.get('X-CSRF-Token', '')
        if not csrf_valid(token):
            return deny_response('csrf')

    cfg = storage.load_config()
    now = get_brasilia_time()

    ip_cfg = cfg.get('ip_control', {})
    if ip_cfg.get('enabled', False):
        client_ip = get_client_ip()
        allowed = ip_cfg.get('ips', [])
        if allowed and client_ip not in allowed:
            session.clear()
            return deny_response('ip', ip=client_ip)

    h_cfg = cfg.get('horario_control', {})
    if h_cfg.get('enabled', False) and request.endpoint not in ('auth.login',):
        dia_atual = now.weekday()
        hora_atual = now.strftime('%H:%M')
        horarios = h_cfg.get('horarios', [])
        reg = next((h for h in horarios if h['dia'] == dia_atual), None)

        bloqueado = False
        if reg is None:
            bloqueado = True
        elif not reg.get('ativo', False):
            bloqueado = True
        elif not (reg['inicio'] <= hora_atual <= reg['fim']):
            bloqueado = True

        if bloqueado:
            session.clear()
            inicio_dia = reg['inicio'] if reg else '--'
            fim_dia    = reg['fim']    if reg else '--'
            nome_dia   = reg['nome']   if reg else '—'
            return deny_response('horario', nome_dia=nome_dia, inicio=inicio_dia, fim=fim_dia)

    return None


# ─────────────────────────────────────────
#  INIT & RUN
# ─────────────────────────────────────────

def init_data():
    """Cria o schema no Oracle (se ainda não existir) e semeia os dados
    padrão. Idempotente — seguro de chamar a cada start do app."""
    from db import migrate
    migrate.run()


if __name__ == '__main__':
    init_data()
    print('=' * 60)
    print('  SISTEMA TICKETS — Iniciando...')
    print('=' * 60)
    print('  Acesse: http://localhost:5000')
    print()
    print('  Usuarios padrao:')
    print('  admin       / admin123  (Administrador)')
    print('  supervisor  / super123  (Supervisor)')
    print('  funcionario / func123   (Funcionario)')
    print('=' * 60)
    app.run(debug=False, host='0.0.0.0', port=5000)
