from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
import json
import os
import uuid
from datetime import datetime
import pytz
from werkzeug.utils import secure_filename
from functools import wraps

app = Flask(__name__)
app.secret_key = 'tickets-sistema-2024-secretkey'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
UPLOADS_DIR = os.path.join(BASE_DIR, 'uploads')

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'mp4', 'avi', 'mov', 'webm', 'mkv'}
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB

SISTEMAS = ['Teknisa', 'Kdápio (Callcenter)', 'Lumia', 'iFood']
STATUS_LIST = ['Aberto', 'Em Andamento', 'Resolvido', 'Fechado']

DIAS_SEMANA = [
    {'dia': 0, 'nome': 'Segunda-feira'},
    {'dia': 1, 'nome': 'Terça-feira'},
    {'dia': 2, 'nome': 'Quarta-feira'},
    {'dia': 3, 'nome': 'Quinta-feira'},
    {'dia': 4, 'nome': 'Sexta-feira'},
    {'dia': 5, 'nome': 'Sábado'},
    {'dia': 6, 'nome': 'Domingo'},
]


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
        }
    }


def load_config():
    cfg_file = os.path.join(DATA_DIR, 'config.json')
    if not os.path.exists(cfg_file):
        return get_default_config()
    with open(cfg_file, 'r', encoding='utf-8') as f:
        return json.load(f)


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


# ─────────────────────────────────────────
#  ACCESS CONTROL MIDDLEWARE
# ─────────────────────────────────────────

ENDPOINTS_LIVRES = {'static', 'uploaded_file', 'acesso_negado', 'logout'}


@app.before_request
def check_access_controls():
    if request.endpoint in ENDPOINTS_LIVRES or request.endpoint is None:
        return None

    cfg = load_config()
    now = get_brasilia_time()

    # ── IP Control ──────────────────────────────────────
    ip_cfg = cfg.get('ip_control', {})
    if ip_cfg.get('enabled', False):
        client_ip = get_client_ip()
        allowed = ip_cfg.get('ips', [])
        if allowed and client_ip not in allowed:
            session.clear()
            return render_template(
                'acesso_negado.html',
                motivo='ip',
                ip=client_ip,
                hora=now.strftime('%d/%m/%Y %H:%M:%S')
            ), 403

    # ── Horário Control ─────────────────────────────────
    h_cfg = cfg.get('horario_control', {})
    if h_cfg.get('enabled', False) and request.endpoint not in ('login',):
        dia_atual = now.weekday()          # 0 = segunda
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
                'acesso_negado.html',
                motivo='horario',
                hora=now.strftime('%d/%m/%Y %H:%M:%S'),
                nome_dia=nome_dia,
                inicio=inicio_dia,
                fim=fim_dia
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
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        users = load_users()
        user = next((u for u in users
                     if u['username'] == username
                     and u['password'] == password
                     and u.get('ativo', True)), None)
        if user:
            session.update({'user_id': user['id'], 'username': user['username'],
                            'name': user['name'], 'role': user['role']})
            return redirect(url_for('dashboard'))
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
    sistemas_stats = {s: sum(1 for t in tickets if t.get('sistema') == s) for s in SISTEMAS}
    recentes = sorted(tickets, key=lambda x: x.get('data_criacao', ''), reverse=True)[:5]
    return render_template('dashboard.html', stats=stats, recentes=recentes, sistemas_stats=sistemas_stats)


# ─────────────────────────────────────────
#  ROUTES — TICKETS
# ─────────────────────────────────────────

@app.route('/abrir-ticket', methods=['GET', 'POST'])
@login_required
def abrir_ticket():
    if session['role'] == 'supervisor':
        return redirect(url_for('dashboard'))

    error = None
    if request.method == 'POST':
        nome      = request.form.get('nome', '').strip()
        ocorrencia = request.form.get('ocorrencia', '').strip()
        sistema   = request.form.get('sistema', '')

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

    return render_template('abrir_ticket.html', sistemas=SISTEMAS, error=error)


@app.route('/acompanhamento')
@login_required
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
                           sistemas=SISTEMAS, status_list=STATUS_LIST,
                           filtro_status=filtro_status, filtro_sistema=filtro_sistema, busca=busca)


@app.route('/ticket/<ticket_id>')
@login_required
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
def atualizar_ticket(ticket_id):
    if session['role'] == 'funcionario':
        return redirect(url_for('ver_ticket', ticket_id=ticket_id))
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


@app.route('/ticket/<ticket_id>/comentar', methods=['POST'])
@login_required
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
    current_ip = get_client_ip()
    return render_template('configuracoes.html',
                           users=users, cfg=cfg, tab=tab,
                           stats=stats, current_ip=current_ip,
                           msg=msg, err=err)


# Rota legada — redireciona para configurações
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

    if not (username and password and name):
        return redirect(url_for('configuracoes', tab='usuarios', err='campos_obrigatorios'))
    if any(u['username'] == username for u in users):
        return redirect(url_for('configuracoes', tab='usuarios', err='usuario_existe'))

    users.append({'id': str(uuid.uuid4()), 'username': username,
                  'password': password, 'name': name,
                  'role': role, 'email': email, 'ativo': True})
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
    users     = load_users()
    user      = next((u for u in users if u['id'] == user_id), None)
    nova_senha = request.form.get('nova_senha', '').strip()
    if user and nova_senha and len(nova_senha) >= 4:
        user['password'] = nova_senha
        save_users(users)
    return redirect(url_for('configuracoes', tab='usuarios', msg='senha_alterada'))


# ── IPs Permitidos ────────────────────────

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
    # Não permite remover o IP atual se o controle estiver ativo
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


# ─────────────────────────────────────────
#  ROUTES — PERFIL & MISC
# ─────────────────────────────────────────

@app.route('/meu-perfil', methods=['GET', 'POST'])
@login_required
def meu_perfil():
    users   = load_users()
    user    = next((u for u in users if u['id'] == session['user_id']), None)
    success = error = None

    if request.method == 'POST':
        senha_atual  = request.form.get('senha_atual', '').strip()
        nova_senha   = request.form.get('nova_senha', '').strip()
        confirmar    = request.form.get('confirmar_senha', '').strip()

        if user['password'] != senha_atual:
            error = 'Senha atual incorreta.'
        elif nova_senha != confirmar:
            error = 'As senhas não coincidem.'
        elif len(nova_senha) < 4:
            error = 'A nova senha deve ter pelo menos 4 caracteres.'
        else:
            user['password'] = nova_senha
            save_users(users)
            success = 'Senha alterada com sucesso!'

    return render_template('perfil.html', user=user, success=success, error=error)


@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(UPLOADS_DIR, filename)


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
            {'id': '1', 'username': 'admin',       'password': 'admin123', 'name': 'Administrador',
             'role': 'admin',       'email': 'admin@tickets.local',       'ativo': True},
            {'id': '2', 'username': 'supervisor',   'password': 'super123', 'name': 'Supervisor',
             'role': 'supervisor',  'email': 'supervisor@tickets.local',   'ativo': True},
            {'id': '3', 'username': 'funcionario',  'password': 'func123',  'name': 'Funcionário',
             'role': 'funcionario', 'email': 'funcionario@tickets.local',  'ativo': True},
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
