from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
import json
import os
import re
import secrets
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
import pytz
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(os.path.dirname(BASE_DIR), 'frontend')

def _load_dotenv():
    env_file = os.path.join(BASE_DIR, '.env')
    if not os.path.exists(env_file):
        return
    with open(env_file, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

_load_dotenv()

app = Flask(
    __name__,
    template_folder=os.path.join(FRONTEND_DIR, 'templates'),
    static_folder=os.path.join(FRONTEND_DIR, 'static'),
)
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

DATA_DIR = os.path.join(BASE_DIR, 'data')
UPLOADS_DIR = os.path.join(BASE_DIR, 'uploads')

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'mp4', 'avi', 'mov', 'webm', 'mkv'}
LOGO_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

STATUS_LIST = ['Aberto', 'Em Andamento', 'Resolvido', 'Fechado']
ROLES_VALIDOS = {'admin', 'supervisor', 'funcionario'}
HEX_COLOR_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')

# Permissões disponíveis no sistema
PERMISSOES = [
    ('dashboard',        'Dashboard',                      'fa-gauge-high'),
    ('abrir_ticket',     'Abrir Tickets',                  'fa-circle-plus'),
    ('acompanhamento',   'Acompanhamento de Tickets',      'fa-list-check'),
    ('ver_ticket',       'Visualizar Detalhes do Ticket',  'fa-eye'),
    ('atualizar_ticket', 'Atualizar Status do Ticket',     'fa-pen-to-square'),
    ('comentar_ticket',  'Comentar em Tickets',            'fa-comment'),
    ('meu_perfil',       'Meu Perfil',                     'fa-user'),
]
PERMISSOES_IDS = [p[0] for p in PERMISSOES]

DIAS_SEMANA = [
    {'dia': 0, 'nome': 'Segunda-feira'},
    {'dia': 1, 'nome': 'Terça-feira'},
    {'dia': 2, 'nome': 'Quarta-feira'},
    {'dia': 3, 'nome': 'Quinta-feira'},
    {'dia': 4, 'nome': 'Sexta-feira'},
    {'dia': 5, 'nome': 'Sábado'},
    {'dia': 6, 'nome': 'Domingo'},
]

_login_attempts: dict = defaultdict(list)
_LOGIN_MAX = 5
_LOGIN_LOCKOUT_MIN = 15


# ─────────────────────────────────────────
#  SECURITY HELPERS
# ─────────────────────────────────────────

def valid_hex(value: str, default: str) -> str:
    return value if HEX_COLOR_RE.match(value or '') else default


def _is_hashed(stored: str) -> bool:
    return stored.startswith(('pbkdf2:', 'scrypt:', 'argon2'))


def verify_password(stored: str, provided: str) -> bool:
    if _is_hashed(stored):
        return check_password_hash(stored, provided)
    return stored == provided


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def _rate_limit_exceeded(ip: str) -> bool:
    now = datetime.utcnow()
    cutoff = now - timedelta(minutes=_LOGIN_LOCKOUT_MIN)
    _login_attempts[ip] = [t for t in _login_attempts[ip] if t > cutoff]
    return len(_login_attempts[ip]) >= _LOGIN_MAX


def _register_failed_login(ip: str) -> None:
    _login_attempts[ip].append(datetime.utcnow())


def get_user_permissoes(user: dict) -> list:
    """Retorna lista de permissões do usuário com base no seu perfil atribuído."""
    if user.get('role') == 'admin':
        return PERMISSOES_IDS[:]

    perfil_id = user.get('perfil_id')
    if perfil_id:
        cfg = load_config()
        perfil = next((p for p in cfg.get('perfis', []) if p['id'] == perfil_id), None)
        if perfil:
            return perfil.get('permissoes', [])

    # Fallback por role
    role = user.get('role', 'funcionario')
    if role == 'supervisor':
        return ['dashboard', 'acompanhamento', 'ver_ticket', 'atualizar_ticket', 'comentar_ticket', 'meu_perfil']
    return ['dashboard', 'abrir_ticket', 'acompanhamento', 'ver_ticket', 'comentar_ticket', 'meu_perfil']


# ─────────────────────────────────────────
#  DATA HELPERS
# ─────────────────────────────────────────

def get_brasilia_time():
    return datetime.now(pytz.timezone('America/Sao_Paulo'))


def get_client_ip():
    fwd = request.headers.get('X-Forwarded-For')
    if fwd:
        return fwd.split(',')[0].strip()
    return request.remote_addr or '0.0.0.0'


def load_users():
    with open(os.path.join(DATA_DIR, 'users.json'), 'r', encoding='utf-8') as f:
        return json.load(f)


def save_users(users):
    with open(os.path.join(DATA_DIR, 'users.json'), 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def load_tickets():
    with open(os.path.join(DATA_DIR, 'tickets.json'), 'r', encoding='utf-8') as f:
        return json.load(f)


def save_tickets(tickets):
    with open(os.path.join(DATA_DIR, 'tickets.json'), 'w', encoding='utf-8') as f:
        json.dump(tickets, f, ensure_ascii=False, indent=2)


def get_default_perfis():
    return [
        {
            'id': 'perfil-supervisor',
            'nome': 'Supervisor',
            'descricao': 'Acompanha tickets e atualiza status',
            'permissoes': ['dashboard', 'acompanhamento', 'ver_ticket', 'atualizar_ticket', 'comentar_ticket', 'meu_perfil'],
            'padrao': True,
        },
        {
            'id': 'perfil-funcionario',
            'nome': 'Funcionário',
            'descricao': 'Abre e acompanha seus próprios tickets',
            'permissoes': ['dashboard', 'abrir_ticket', 'acompanhamento', 'ver_ticket', 'comentar_ticket', 'meu_perfil'],
            'padrao': True,
        },
    ]


def get_default_config():
    return {
        'ip_control': {
            'enabled': False,
            'ips': ['127.0.0.1', '::1']
        },
        'horario_control': {
            'enabled': False,
            'horarios': [
                {'dia': 0, 'nome': 'Segunda-feira',  'inicio': '08:00', 'fim': '18:00', 'ativo': True},
                {'dia': 1, 'nome': 'Terça-feira',    'inicio': '08:00', 'fim': '18:00', 'ativo': True},
                {'dia': 2, 'nome': 'Quarta-feira',   'inicio': '08:00', 'fim': '18:00', 'ativo': True},
                {'dia': 3, 'nome': 'Quinta-feira',   'inicio': '08:00', 'fim': '18:00', 'ativo': True},
                {'dia': 4, 'nome': 'Sexta-feira',    'inicio': '08:00', 'fim': '18:00', 'ativo': True},
                {'dia': 5, 'nome': 'Sábado',         'inicio': '08:00', 'fim': '12:00', 'ativo': False},
                {'dia': 6, 'nome': 'Domingo',        'inicio': '00:00', 'fim': '00:00', 'ativo': False},
            ]
        },
        'sistemas': ['Teknisa', 'Kdápio (Callcenter)', 'Lumia', 'iFood'],
        'personalizacao': {
            'cor_botao':         '#111111',
            'cor_botao_light':   '#f0f0f0',
            'cor_fundo':         '#f1f5f9',
            'cor_sidebar':       '#0f172a',
            'cor_sidebar_ativo': '#111111',
            'cor_texto':         '#0f172a',
            'nome_sistema':      'Tickets',
            'logo_filename':     None,
        },
        'perfis': get_default_perfis(),
    }


def load_config():
    cfg_file = os.path.join(DATA_DIR, 'config.json')
    defaults = get_default_config()
    if not os.path.exists(cfg_file):
        return defaults
    with open(cfg_file, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    for key, val in defaults.items():
        if key not in cfg:
            cfg[key] = val
    return cfg


def get_sistemas():
    return load_config().get('sistemas', ['Teknisa', 'Kdápio (Callcenter)', 'Lumia', 'iFood'])


def save_config(cfg):
    with open(os.path.join(DATA_DIR, 'config.json'), 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def get_next_ticket_number():
    tickets = load_tickets()
    if not tickets:
        return 'TKT-0001'
    numbers = []
    for t in tickets:
        try:
            numbers.append(int(t['numero'].split('-')[1]))
        except (KeyError, IndexError, ValueError):
            pass
    return f'TKT-{(max(numbers) + 1 if numbers else 1):04d}'


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_role_label(role):
    return {'admin': 'Administrador', 'supervisor': 'Supervisor', 'funcionario': 'Funcionário'}.get(role, role)


app.jinja_env.globals['get_role_label'] = get_role_label
app.jinja_env.globals['PERMISSOES'] = PERMISSOES


@app.context_processor
def inject_global_config():
    cfg = load_config()
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
    return response


# ─────────────────────────────────────────
#  DECORATORS
# ─────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if session.get('role') not in roles:
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated
    return decorator


def permission_required(perm):
    """Verifica se o usuário tem a permissão. Admin sempre passa."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if session.get('role') == 'admin':
                return f(*args, **kwargs)
            if perm not in session.get('permissoes', []):
                return render_template(
                    'acesso_negado.html',
                    motivo='permissao',
                    hora=get_brasilia_time().strftime('%d/%m/%Y %H:%M:%S')
                ), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


# ─────────────────────────────────────────
#  ACCESS CONTROL MIDDLEWARE
# ─────────────────────────────────────────

ENDPOINTS_LIVRES = {'static', 'uploaded_file', 'serve_logo', 'acesso_negado', 'logout'}


@app.before_request
def check_access_controls():
    if request.endpoint in ENDPOINTS_LIVRES or request.endpoint is None:
        return None

    cfg = load_config()
    now = get_brasilia_time()

    ip_cfg = cfg.get('ip_control', {})
    if ip_cfg.get('enabled', False):
        client_ip = get_client_ip()
        allowed = ip_cfg.get('ips', [])
        if allowed and client_ip not in allowed:
            session.clear()
            return render_template(
                'acesso_negado.html', motivo='ip',
                ip=client_ip, hora=now.strftime('%d/%m/%Y %H:%M:%S')
            ), 403

    h_cfg = cfg.get('horario_control', {})
    if h_cfg.get('enabled', False) and request.endpoint not in ('login',):
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
            return render_template(
                'acesso_negado.html', motivo='horario',
                hora=now.strftime('%d/%m/%Y %H:%M:%S'),
                nome_dia=nome_dia, inicio=inicio_dia, fim=fim_dia
            ), 403

    return None


# ─────────────────────────────────────────
#  ROUTES — AUTH
# ─────────────────────────────────────────

@app.route('/')
def index():
    return redirect(url_for('dashboard') if 'user_id' in session else url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    error = None
    if request.method == 'POST':
        client_ip = get_client_ip()
        if _rate_limit_exceeded(client_ip):
            error = f'Muitas tentativas. Aguarde {_LOGIN_LOCKOUT_MIN} minutos.'
            return render_template('login.html', error=error)

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        users = load_users()
        user = next((u for u in users
                     if u['username'] == username and u.get('ativo', True)), None)

        if user and verify_password(user['password'], password):
            if not _is_hashed(user['password']):
                user['password'] = hash_password(password)
                save_users(users)
            permissoes = get_user_permissoes(user)
            session.update({
                'user_id':   user['id'],
                'username':  user['username'],
                'name':      user['name'],
                'role':      user['role'],
                'permissoes': permissoes,
                'perfil_id': user.get('perfil_id'),
            })
            return redirect(url_for('dashboard'))

        _register_failed_login(client_ip)
        error = 'Usuário ou senha inválidos.'
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/acesso-negado')
def acesso_negado():
    return render_template('acesso_negado.html', motivo='manual',
                           hora=get_brasilia_time().strftime('%d/%m/%Y %H:%M:%S')), 403


# ─────────────────────────────────────────
#  ROUTES — DASHBOARD
# ─────────────────────────────────────────

@app.route('/dashboard')
@login_required
@permission_required('dashboard')
def dashboard():
    tickets = load_tickets()
    if session['role'] == 'funcionario':
        tickets = [t for t in tickets if t.get('criado_por_id') == session['user_id']]

    stats = {
        'total':        len(tickets),
        'aberto':       sum(1 for t in tickets if t['status'] == 'Aberto'),
        'em_andamento': sum(1 for t in tickets if t['status'] == 'Em Andamento'),
        'resolvido':    sum(1 for t in tickets if t['status'] == 'Resolvido'),
        'fechado':      sum(1 for t in tickets if t['status'] == 'Fechado'),
    }
    sistemas_stats = {s: sum(1 for t in tickets if t.get('sistema') == s) for s in get_sistemas()}
    recentes = sorted(tickets, key=lambda x: x.get('data_criacao', ''), reverse=True)[:5]
    return render_template('dashboard.html', stats=stats, recentes=recentes, sistemas_stats=sistemas_stats)


# ─────────────────────────────────────────
#  ROUTES — TICKETS
# ─────────────────────────────────────────

@app.route('/abrir-ticket', methods=['GET', 'POST'])
@login_required
@permission_required('abrir_ticket')
def abrir_ticket():
    error = None
    if request.method == 'POST':
        nome       = request.form.get('nome', '').strip()
        ocorrencia = request.form.get('ocorrencia', '').strip()
        sistema    = request.form.get('sistema', '')

        if not nome or not ocorrencia or not sistema:
            error = 'Preencha todos os campos obrigatórios.'
        else:
            arquivo_info = None
            if 'arquivo' in request.files:
                file = request.files['arquivo']
                if file and file.filename and allowed_file(file.filename):
                    ext = file.filename.rsplit('.', 1)[1].lower()
                    fname = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
                    file.save(os.path.join(UPLOADS_DIR, fname))
                    arquivo_info = {
                        'filename': fname,
                        'original_name': file.filename,
                        'tipo': 'video' if ext in {'mp4', 'avi', 'mov', 'webm', 'mkv'} else 'imagem'
                    }
                elif file and file.filename:
                    error = 'Formato de arquivo não permitido.'

            if not error:
                now = get_brasilia_time()
                ticket = {
                    'id': str(uuid.uuid4()),
                    'numero': get_next_ticket_number(),
                    'nome': nome,
                    'ocorrencia': ocorrencia,
                    'sistema': sistema,
                    'arquivo': arquivo_info,
                    'data_criacao': now.strftime('%Y-%m-%dT%H:%M:%S'),
                    'data_formatada': now.strftime('%d/%m/%Y %H:%M:%S'),
                    'status': 'Aberto',
                    'criado_por': session['name'],
                    'criado_por_id': session['user_id'],
                    'historico': [{'acao': 'Ticket aberto', 'por': session['name'],
                                   'data': now.strftime('%d/%m/%Y %H:%M:%S')}]
                }
                tickets = load_tickets()
                tickets.append(ticket)
                save_tickets(tickets)
                return redirect(url_for('ver_ticket', ticket_id=ticket['id']))

    return render_template('abrir_ticket.html', sistemas=get_sistemas(), error=error)


@app.route('/acompanhamento')
@login_required
@permission_required('acompanhamento')
def acompanhamento():
    tickets = load_tickets()
    if session['role'] == 'funcionario':
        tickets = [t for t in tickets if t.get('criado_por_id') == session['user_id']]

    filtro_status  = request.args.get('status', '')
    filtro_sistema = request.args.get('sistema', '')
    busca          = request.args.get('busca', '').strip().lower()

    if filtro_status:  tickets = [t for t in tickets if t['status'] == filtro_status]
    if filtro_sistema: tickets = [t for t in tickets if t.get('sistema') == filtro_sistema]
    if busca:          tickets = [t for t in tickets if
                                  busca in t.get('nome', '').lower() or
                                  busca in t.get('numero', '').lower() or
                                  busca in t.get('criado_por', '').lower()]

    tickets = sorted(tickets, key=lambda x: x.get('data_criacao', ''), reverse=True)
    return render_template('acompanhamento.html', tickets=tickets,
                           sistemas=get_sistemas(), status_list=STATUS_LIST,
                           filtro_status=filtro_status, filtro_sistema=filtro_sistema, busca=busca)


@app.route('/ticket/<ticket_id>')
@login_required
@permission_required('ver_ticket')
def ver_ticket(ticket_id):
    tickets = load_tickets()
    ticket = next((t for t in tickets if t['id'] == ticket_id), None)
    if not ticket:
        return redirect(url_for('acompanhamento'))
    if session['role'] == 'funcionario' and ticket.get('criado_por_id') != session['user_id']:
        return redirect(url_for('acompanhamento'))
    return render_template('ver_ticket.html', ticket=ticket, status_list=STATUS_LIST)


@app.route('/ticket/<ticket_id>/atualizar', methods=['POST'])
@login_required
@permission_required('atualizar_ticket')
def atualizar_ticket(ticket_id):
    tickets = load_tickets()
    ticket = next((t for t in tickets if t['id'] == ticket_id), None)
    if not ticket:
        return redirect(url_for('acompanhamento'))
    novo_status = request.form.get('status', '')
    comentario  = request.form.get('comentario', '').strip()
    if novo_status in STATUS_LIST:
        now = get_brasilia_time()
        ticket['status'] = novo_status
        entrada = f'Status alterado para "{novo_status}"'
        if comentario:
            entrada += f' — {comentario}'
        ticket['historico'].append({'acao': entrada, 'por': session['name'],
                                    'data': now.strftime('%d/%m/%Y %H:%M:%S')})
        save_tickets(tickets)
    return redirect(url_for('ver_ticket', ticket_id=ticket_id))


@app.route('/ticket/<ticket_id>/excluir', methods=['POST'])
@login_required
@role_required('admin')
def excluir_ticket(ticket_id):
    tickets = load_tickets()
    ticket = next((t for t in tickets if t['id'] == ticket_id), None)
    if ticket:
        if ticket.get('arquivo') and ticket['arquivo'].get('filename'):
            path = os.path.join(UPLOADS_DIR, ticket['arquivo']['filename'])
            if os.path.exists(path):
                os.remove(path)
        tickets = [t for t in tickets if t['id'] != ticket_id]
        save_tickets(tickets)
    return redirect(url_for('acompanhamento'))


@app.route('/ticket/<ticket_id>/comentar', methods=['POST'])
@login_required
@permission_required('comentar_ticket')
def comentar_ticket(ticket_id):
    tickets = load_tickets()
    ticket = next((t for t in tickets if t['id'] == ticket_id), None)
    if not ticket:
        return redirect(url_for('acompanhamento'))
    if session['role'] == 'funcionario' and ticket.get('criado_por_id') != session['user_id']:
        return redirect(url_for('acompanhamento'))
    comentario = request.form.get('comentario', '').strip()
    if comentario:
        now = get_brasilia_time()
        ticket['historico'].append({'acao': f'Comentário: {comentario}',
                                    'por': session['name'],
                                    'data': now.strftime('%d/%m/%Y %H:%M:%S')})
        save_tickets(tickets)
    return redirect(url_for('ver_ticket', ticket_id=ticket_id))


# ─────────────────────────────────────────
#  ROUTES — CONFIGURAÇÕES
# ─────────────────────────────────────────

@app.route('/configuracoes')
@login_required
@role_required('admin')
def configuracoes():
    users   = load_users()
    cfg     = load_config()
    tickets = load_tickets()
    tab     = request.args.get('tab', 'usuarios')
    msg     = request.args.get('msg', '')
    err     = request.args.get('err', '')
    stats   = {
        'total_usuarios': len(users),
        'total_tickets':  len(tickets),
        'abertos':        sum(1 for t in tickets if t['status'] == 'Aberto'),
    }
    current_ip  = get_client_ip()
    perfis      = cfg.get('perfis', [])
    perfis_dict = {p['id']: p for p in perfis}
    return render_template('configuracoes.html',
                           users=users, cfg=cfg, tab=tab,
                           stats=stats, current_ip=current_ip,
                           msg=msg, err=err,
                           perfis=perfis, perfis_dict=perfis_dict)


@app.route('/admin')
@login_required
@role_required('admin')
def admin():
    return redirect(url_for('configuracoes'))


# ── Usuários ─────────────────────────────

@app.route('/configuracoes/usuario/criar', methods=['POST'])
@login_required
@role_required('admin')
def cfg_criar_usuario():
    users    = load_users()
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    name     = request.form.get('name', '').strip()
    role     = request.form.get('role', 'funcionario')
    email    = request.form.get('email', '').strip()
    perfil_id = request.form.get('perfil_id', '').strip() or None

    if not (username and password and name):
        return redirect(url_for('configuracoes', tab='usuarios', err='campos_obrigatorios'))
    if any(u['username'] == username for u in users):
        return redirect(url_for('configuracoes', tab='usuarios', err='usuario_existe'))
    if role not in ROLES_VALIDOS:
        role = 'funcionario'

    # Valida perfil_id
    if perfil_id:
        cfg = load_config()
        if not any(p['id'] == perfil_id for p in cfg.get('perfis', [])):
            perfil_id = None

    novo = {'id': str(uuid.uuid4()), 'username': username,
            'password': hash_password(password), 'name': name,
            'role': role, 'email': email, 'ativo': True}
    if perfil_id:
        novo['perfil_id'] = perfil_id
    users.append(novo)
    save_users(users)
    return redirect(url_for('configuracoes', tab='usuarios', msg='usuario_criado'))


@app.route('/configuracoes/usuario/<user_id>/toggle', methods=['POST'])
@login_required
@role_required('admin')
def cfg_toggle_usuario(user_id):
    if user_id == session['user_id']:
        return redirect(url_for('configuracoes', tab='usuarios'))
    users = load_users()
    user  = next((u for u in users if u['id'] == user_id), None)
    if user:
        user['ativo'] = not user.get('ativo', True)
        save_users(users)
    return redirect(url_for('configuracoes', tab='usuarios'))


@app.route('/configuracoes/usuario/<user_id>/senha', methods=['POST'])
@login_required
@role_required('admin')
def cfg_alterar_senha(user_id):
    users      = load_users()
    user       = next((u for u in users if u['id'] == user_id), None)
    nova_senha = request.form.get('nova_senha', '').strip()
    if user and nova_senha and len(nova_senha) >= 4:
        user['password'] = hash_password(nova_senha)
        save_users(users)
    return redirect(url_for('configuracoes', tab='usuarios', msg='senha_alterada'))


@app.route('/configuracoes/usuario/<user_id>/perfil', methods=['POST'])
@login_required
@role_required('admin')
def cfg_alterar_perfil_usuario(user_id):
    users     = load_users()
    user      = next((u for u in users if u['id'] == user_id), None)
    if user:
        perfil_id = request.form.get('perfil_id', '').strip() or None
        if perfil_id:
            cfg = load_config()
            if not any(p['id'] == perfil_id for p in cfg.get('perfis', [])):
                perfil_id = None
        if perfil_id:
            user['perfil_id'] = perfil_id
        elif 'perfil_id' in user:
            del user['perfil_id']
        save_users(users)
    return redirect(url_for('configuracoes', tab='usuarios', msg='perfil_atualizado'))


# ── IPs Permitidos ────────────────────────

@app.route('/configuracoes/usuario/<user_id>/excluir', methods=['POST'])
@login_required
@role_required('admin')
def cfg_excluir_usuario(user_id):
    if user_id == session['user_id']:
        return redirect(url_for('configuracoes', tab='usuarios'))
    users = load_users()
    users = [u for u in users if u['id'] != user_id]
    save_users(users)
    return redirect(url_for('configuracoes', tab='usuarios', msg='usuario_excluido'))


@app.route('/configuracoes/ip/toggle', methods=['POST'])
@login_required
@role_required('admin')
def cfg_ip_toggle():
    cfg = load_config()
    cfg['ip_control']['enabled'] = not cfg['ip_control'].get('enabled', False)
    save_config(cfg)
    return redirect(url_for('configuracoes', tab='ips'))


@app.route('/configuracoes/ip/adicionar', methods=['POST'])
@login_required
@role_required('admin')
def cfg_ip_adicionar():
    cfg = load_config()
    ip  = request.form.get('ip', '').strip()
    if ip and ip not in cfg['ip_control']['ips']:
        cfg['ip_control']['ips'].append(ip)
        save_config(cfg)
    return redirect(url_for('configuracoes', tab='ips'))


@app.route('/configuracoes/ip/remover', methods=['POST'])
@login_required
@role_required('admin')
def cfg_ip_remover():
    cfg = load_config()
    ip  = request.form.get('ip', '').strip()
    if ip in cfg['ip_control']['ips']:
        cfg['ip_control']['ips'].remove(ip)
        save_config(cfg)
    return redirect(url_for('configuracoes', tab='ips'))


# ── Controle de Horários ──────────────────

@app.route('/configuracoes/horario/toggle', methods=['POST'])
@login_required
@role_required('admin')
def cfg_horario_toggle():
    cfg = load_config()
    cfg['horario_control']['enabled'] = not cfg['horario_control'].get('enabled', False)
    save_config(cfg)
    return redirect(url_for('configuracoes', tab='horarios'))


@app.route('/configuracoes/horario/atualizar', methods=['POST'])
@login_required
@role_required('admin')
def cfg_horario_atualizar():
    cfg = load_config()
    for h in cfg['horario_control']['horarios']:
        dia = str(h['dia'])
        h['ativo']  = f'ativo_{dia}' in request.form
        h['inicio'] = request.form.get(f'inicio_{dia}', h['inicio'])
        h['fim']    = request.form.get(f'fim_{dia}',    h['fim'])
    save_config(cfg)
    return redirect(url_for('configuracoes', tab='horarios', msg='horarios_salvos'))


# ── Sistemas ──────────────────────────────

@app.route('/configuracoes/sistema/adicionar', methods=['POST'])
@login_required
@role_required('admin')
def cfg_sistema_adicionar():
    cfg = load_config()
    nome = request.form.get('nome', '').strip()
    if nome and nome not in cfg['sistemas']:
        cfg['sistemas'].append(nome)
        save_config(cfg)
    return redirect(url_for('configuracoes', tab='sistemas', msg='sistema_adicionado'))


@app.route('/configuracoes/sistema/remover', methods=['POST'])
@login_required
@role_required('admin')
def cfg_sistema_remover():
    cfg = load_config()
    nome = request.form.get('nome', '').strip()
    if nome in cfg['sistemas']:
        cfg['sistemas'].remove(nome)
        save_config(cfg)
    return redirect(url_for('configuracoes', tab='sistemas', msg='sistema_removido'))


# ── Perfis de Acesso ──────────────────────

@app.route('/configuracoes/perfil/criar', methods=['POST'])
@login_required
@role_required('admin')
def cfg_perfil_criar():
    cfg  = load_config()
    nome = request.form.get('nome', '').strip()
    desc = request.form.get('descricao', '').strip()
    perms = [p for p in request.form.getlist('permissoes') if p in PERMISSOES_IDS]

    if not nome:
        return redirect(url_for('configuracoes', tab='perfis', err='nome_obrigatorio'))

    cfg.setdefault('perfis', []).append({
        'id':         str(uuid.uuid4()),
        'nome':       nome,
        'descricao':  desc,
        'permissoes': perms,
        'padrao':     False,
    })
    save_config(cfg)
    return redirect(url_for('configuracoes', tab='perfis', msg='perfil_criado'))


@app.route('/configuracoes/perfil/<perfil_id>/atualizar', methods=['POST'])
@login_required
@role_required('admin')
def cfg_perfil_atualizar(perfil_id):
    cfg    = load_config()
    perfil = next((p for p in cfg.get('perfis', []) if p['id'] == perfil_id), None)
    if perfil:
        novo_nome = request.form.get('nome', '').strip()
        if novo_nome:
            perfil['nome'] = novo_nome
        perfil['descricao'] = request.form.get('descricao', '').strip()
        perfil['permissoes'] = [p for p in request.form.getlist('permissoes') if p in PERMISSOES_IDS]
        save_config(cfg)
    return redirect(url_for('configuracoes', tab='perfis', msg='perfil_atualizado'))


@app.route('/configuracoes/perfil/<perfil_id>/excluir', methods=['POST'])
@login_required
@role_required('admin')
def cfg_perfil_excluir(perfil_id):
    cfg    = load_config()
    perfil = next((p for p in cfg.get('perfis', []) if p['id'] == perfil_id), None)
    if perfil and not perfil.get('padrao', False):
        cfg['perfis'] = [p for p in cfg['perfis'] if p['id'] != perfil_id]
        save_config(cfg)
    return redirect(url_for('configuracoes', tab='perfis', msg='perfil_removido'))


# ── Personalização ────────────────────────

@app.route('/configuracoes/personalizacao/salvar', methods=['POST'])
@login_required
@role_required('admin')
def cfg_personalizacao_salvar():
    cfg = load_config()
    p = cfg['personalizacao']
    p['cor_botao']         = valid_hex(request.form.get('cor_botao'),         p['cor_botao'])
    p['cor_botao_light']   = valid_hex(request.form.get('cor_botao_light'),   p['cor_botao_light'])
    p['cor_fundo']         = valid_hex(request.form.get('cor_fundo'),         p['cor_fundo'])
    p['cor_sidebar']       = valid_hex(request.form.get('cor_sidebar'),       p['cor_sidebar'])
    p['cor_sidebar_ativo'] = valid_hex(request.form.get('cor_sidebar_ativo'), p['cor_sidebar_ativo'])
    p['cor_texto']         = valid_hex(request.form.get('cor_texto'),         p['cor_texto'])
    p['nome_sistema']      = request.form.get('nome_sistema', 'Tickets').strip() or 'Tickets'
    save_config(cfg)
    return redirect(url_for('configuracoes', tab='personalizacao', msg='personalizacao_salva'))


@app.route('/configuracoes/logo/upload', methods=['POST'])
@login_required
@role_required('admin')
def cfg_logo_upload():
    cfg = load_config()
    if 'logo' not in request.files:
        return redirect(url_for('configuracoes', tab='personalizacao', err='logo_invalido'))
    file = request.files['logo']
    if not file or not file.filename:
        return redirect(url_for('configuracoes', tab='personalizacao', err='logo_invalido'))
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in LOGO_EXTENSIONS:
        return redirect(url_for('configuracoes', tab='personalizacao', err='logo_invalido'))
    old_logo = cfg['personalizacao'].get('logo_filename')
    if old_logo:
        old_path = os.path.join(UPLOADS_DIR, old_logo)
        if os.path.exists(old_path):
            os.remove(old_path)
    fname = f"logo_{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(UPLOADS_DIR, fname))
    cfg['personalizacao']['logo_filename'] = fname
    save_config(cfg)
    return redirect(url_for('configuracoes', tab='personalizacao', msg='logo_salvo'))


@app.route('/configuracoes/logo/remover', methods=['POST'])
@login_required
@role_required('admin')
def cfg_logo_remover():
    cfg = load_config()
    logo = cfg['personalizacao'].get('logo_filename')
    if logo:
        path = os.path.join(UPLOADS_DIR, logo)
        if os.path.exists(path):
            os.remove(path)
        cfg['personalizacao']['logo_filename'] = None
        save_config(cfg)
    return redirect(url_for('configuracoes', tab='personalizacao', msg='logo_removido'))


# ─────────────────────────────────────────
#  ROUTES — PERFIL & MISC
# ─────────────────────────────────────────

@app.route('/meu-perfil', methods=['GET', 'POST'])
@login_required
@permission_required('meu_perfil')
def meu_perfil():
    users   = load_users()
    user    = next((u for u in users if u['id'] == session['user_id']), None)
    success = error = None

    if request.method == 'POST':
        senha_atual = request.form.get('senha_atual', '').strip()
        nova_senha  = request.form.get('nova_senha', '').strip()
        confirmar   = request.form.get('confirmar_senha', '').strip()

        if not verify_password(user['password'], senha_atual):
            error = 'Senha atual incorreta.'
        elif nova_senha != confirmar:
            error = 'As senhas não coincidem.'
        elif len(nova_senha) < 4:
            error = 'A nova senha deve ter pelo menos 4 caracteres.'
        else:
            user['password'] = hash_password(nova_senha)
            save_users(users)
            success = 'Senha alterada com sucesso!'

    return render_template('perfil.html', user=user, success=success, error=error)


@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(UPLOADS_DIR, filename)


@app.route('/logo')
def serve_logo():
    cfg = load_config()
    logo = cfg.get('personalizacao', {}).get('logo_filename')
    if logo:
        return send_from_directory(UPLOADS_DIR, logo)
    return '', 404


@app.route('/api/stats')
@login_required
def api_stats():
    tickets = load_tickets()
    if session['role'] == 'funcionario':
        tickets = [t for t in tickets if t.get('criado_por_id') == session['user_id']]
    return jsonify({s: sum(1 for t in tickets if t['status'] == s) for s in STATUS_LIST} |
                   {'total': len(tickets)})


# ─────────────────────────────────────────
#  INIT & RUN
# ─────────────────────────────────────────

def init_data():
    users_file   = os.path.join(DATA_DIR, 'users.json')
    tickets_file = os.path.join(DATA_DIR, 'tickets.json')
    config_file  = os.path.join(DATA_DIR, 'config.json')

    if not os.path.exists(users_file):
        save_users([
            {'id': '1', 'username': 'admin',
             'password': hash_password('admin123'), 'name': 'Administrador',
             'role': 'admin', 'email': 'admin@tickets.local', 'ativo': True},
            {'id': '2', 'username': 'supervisor',
             'password': hash_password('super123'), 'name': 'Supervisor',
             'role': 'supervisor', 'email': 'supervisor@tickets.local', 'ativo': True,
             'perfil_id': 'perfil-supervisor'},
            {'id': '3', 'username': 'funcionario',
             'password': hash_password('func123'), 'name': 'Funcionário',
             'role': 'funcionario', 'email': 'funcionario@tickets.local', 'ativo': True,
             'perfil_id': 'perfil-funcionario'},
        ])

    if not os.path.exists(tickets_file):
        save_tickets([])

    if not os.path.exists(config_file):
        save_config(get_default_config())


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
