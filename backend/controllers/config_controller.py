import os
import uuid

from flask import Blueprint, redirect, render_template, request, url_for

from db.repositories import logs_repository

from core import storage
from core.audit import ACOES, log_evento
from core.config import LOGO_EXTENSIONS, UPLOADS_DIR
from core.security import login_required, role_required, valid_hex, valid_ip, valid_time
from core.time_utils import get_client_ip

config_bp = Blueprint('config', __name__)


@config_bp.route('/configuracoes')
@login_required
@role_required('admin')
def configuracoes():
    users        = storage.load_users()
    cfg          = storage.load_config()
    ticket_stats = storage.get_ticket_stats()
    tab          = request.args.get('tab', 'usuarios')
    msg          = request.args.get('msg', '')
    err          = request.args.get('err', '')
    stats        = {
        'total_usuarios': len(users),
        'total_tickets':  ticket_stats['total'],
        'abertos':        ticket_stats['abertos'],
    }
    current_ip  = get_client_ip()
    perfis      = cfg.get('perfis', [])
    perfis_dict = {p['id']: p for p in perfis}

    logs = []
    filtro_acao = filtro_usuario = busca_logs = ''
    if tab == 'logs':
        filtro_acao    = request.args.get('acao', '')
        filtro_usuario = request.args.get('usuario', '')
        busca_logs     = request.args.get('busca', '')
        logs = logs_repository.listar(acao=filtro_acao, usuario=filtro_usuario, busca=busca_logs)

    return render_template('configuracoes.html',
                           users=users, cfg=cfg, tab=tab,
                           stats=stats, current_ip=current_ip,
                           msg=msg, err=err,
                           perfis=perfis, perfis_dict=perfis_dict,
                           logs=logs, acoes_log=ACOES,
                           filtro_acao=filtro_acao, filtro_usuario=filtro_usuario, busca_logs=busca_logs)


@config_bp.route('/admin')
@login_required
@role_required('admin')
def admin():
    return redirect(url_for('config.configuracoes'))


# ── IPs Permitidos ────────────────────────

@config_bp.route('/configuracoes/ip/toggle', methods=['POST'])
@login_required
@role_required('admin')
def cfg_ip_toggle():
    cfg = storage.load_config()
    ligando = not cfg['ip_control'].get('enabled', False)
    cfg['ip_control']['enabled'] = ligando
    # Ao ativar, garante que quem está ativando não fique trancado pra fora —
    # adiciona o IP de quem fez a requisição se ele ainda não estiver na lista.
    if ligando:
        client_ip = get_client_ip()
        if client_ip not in cfg['ip_control']['ips']:
            cfg['ip_control']['ips'].append(client_ip)
    storage.save_config(cfg)
    log_evento('config_ip_ativado' if ligando else 'config_ip_desativado')
    return redirect(url_for('config.configuracoes', tab='ips'))


@config_bp.route('/configuracoes/ip/adicionar', methods=['POST'])
@login_required
@role_required('admin')
def cfg_ip_adicionar():
    cfg = storage.load_config()
    ip  = request.form.get('ip', '').strip()
    if ip and valid_ip(ip) and ip not in cfg['ip_control']['ips']:
        cfg['ip_control']['ips'].append(ip)
        storage.save_config(cfg)
        log_evento('config_ip_adicionado', detalhes=ip)
    return redirect(url_for('config.configuracoes', tab='ips'))


@config_bp.route('/configuracoes/ip/remover', methods=['POST'])
@login_required
@role_required('admin')
def cfg_ip_remover():
    cfg = storage.load_config()
    ip  = request.form.get('ip', '').strip()
    if ip in cfg['ip_control']['ips']:
        cfg['ip_control']['ips'].remove(ip)
        storage.save_config(cfg)
        log_evento('config_ip_removido', detalhes=ip)
    return redirect(url_for('config.configuracoes', tab='ips'))


# ── Controle de Horários ──────────────────

@config_bp.route('/configuracoes/horario/toggle', methods=['POST'])
@login_required
@role_required('admin')
def cfg_horario_toggle():
    cfg = storage.load_config()
    ligando = not cfg['horario_control'].get('enabled', False)
    cfg['horario_control']['enabled'] = ligando
    storage.save_config(cfg)
    log_evento('config_horario_ativado' if ligando else 'config_horario_desativado')
    return redirect(url_for('config.configuracoes', tab='horarios'))


@config_bp.route('/configuracoes/horario/atualizar', methods=['POST'])
@login_required
@role_required('admin')
def cfg_horario_atualizar():
    cfg = storage.load_config()
    for h in cfg['horario_control']['horarios']:
        dia = str(h['dia'])
        h['ativo']  = f'ativo_{dia}' in request.form
        t_inicio = request.form.get(f'inicio_{dia}', h['inicio'])
        t_fim    = request.form.get(f'fim_{dia}',    h['fim'])
        h['inicio'] = t_inicio if valid_time(t_inicio) else h['inicio']
        h['fim']    = t_fim    if valid_time(t_fim)    else h['fim']
    storage.save_config(cfg)
    log_evento('config_horario_atualizado')
    return redirect(url_for('config.configuracoes', tab='horarios', msg='horarios_salvos'))


# ── Sistemas ──────────────────────────────

@config_bp.route('/configuracoes/sistema/adicionar', methods=['POST'])
@login_required
@role_required('admin')
def cfg_sistema_adicionar():
    cfg = storage.load_config()
    nome = request.form.get('nome', '').strip()
    if nome and nome not in cfg['sistemas']:
        cfg['sistemas'].append(nome)
        storage.save_config(cfg)
        log_evento('config_sistema_adicionado', detalhes=nome)
    return redirect(url_for('config.configuracoes', tab='sistemas', msg='sistema_adicionado'))


@config_bp.route('/configuracoes/sistema/remover', methods=['POST'])
@login_required
@role_required('admin')
def cfg_sistema_remover():
    cfg = storage.load_config()
    nome = request.form.get('nome', '').strip()
    if nome in cfg['sistemas']:
        cfg['sistemas'].remove(nome)
        storage.save_config(cfg)
        log_evento('config_sistema_removido', detalhes=nome)
    return redirect(url_for('config.configuracoes', tab='sistemas', msg='sistema_removido'))


# ── Personalização ────────────────────────

@config_bp.route('/configuracoes/personalizacao/salvar', methods=['POST'])
@login_required
@role_required('admin')
def cfg_personalizacao_salvar():
    cfg = storage.load_config()
    p = cfg['personalizacao']
    p['cor_botao']         = valid_hex(request.form.get('cor_botao'),         p['cor_botao'])
    p['cor_botao_light']   = valid_hex(request.form.get('cor_botao_light'),   p['cor_botao_light'])
    p['cor_fundo']         = valid_hex(request.form.get('cor_fundo'),         p['cor_fundo'])
    p['cor_sidebar']       = valid_hex(request.form.get('cor_sidebar'),       p['cor_sidebar'])
    p['cor_sidebar_ativo'] = valid_hex(request.form.get('cor_sidebar_ativo'), p['cor_sidebar_ativo'])
    p['cor_texto']         = valid_hex(request.form.get('cor_texto'),         p['cor_texto'])
    p['cor_sidebar_texto'] = valid_hex(request.form.get('cor_sidebar_texto'), p['cor_sidebar_texto'])
    p['nome_sistema']      = request.form.get('nome_sistema', 'Tickets').strip() or 'Tickets'
    storage.save_config(cfg)
    log_evento('config_personalizacao_atualizada')
    return redirect(url_for('config.configuracoes', tab='personalizacao', msg='personalizacao_salva'))


@config_bp.route('/configuracoes/logo/upload', methods=['POST'])
@login_required
@role_required('admin')
def cfg_logo_upload():
    cfg = storage.load_config()
    if 'logo' not in request.files:
        return redirect(url_for('config.configuracoes', tab='personalizacao', err='logo_invalido'))
    file = request.files['logo']
    if not file or not file.filename:
        return redirect(url_for('config.configuracoes', tab='personalizacao', err='logo_invalido'))
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in LOGO_EXTENSIONS:
        return redirect(url_for('config.configuracoes', tab='personalizacao', err='logo_invalido'))
    old_logo = cfg['personalizacao'].get('logo_filename')
    if old_logo:
        old_path = os.path.join(UPLOADS_DIR, old_logo)
        if os.path.exists(old_path):
            os.remove(old_path)
    fname = f"logo_{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(UPLOADS_DIR, fname))
    cfg['personalizacao']['logo_filename'] = fname
    storage.save_config(cfg)
    log_evento('config_logo_atualizado')
    return redirect(url_for('config.configuracoes', tab='personalizacao', msg='logo_salvo'))


@config_bp.route('/configuracoes/logo/remover', methods=['POST'])
@login_required
@role_required('admin')
def cfg_logo_remover():
    cfg = storage.load_config()
    logo = cfg['personalizacao'].get('logo_filename')
    if logo:
        path = os.path.join(UPLOADS_DIR, logo)
        if os.path.exists(path):
            os.remove(path)
        cfg['personalizacao']['logo_filename'] = None
        storage.save_config(cfg)
        log_evento('config_logo_removido')
    return redirect(url_for('config.configuracoes', tab='personalizacao', msg='logo_removido'))
