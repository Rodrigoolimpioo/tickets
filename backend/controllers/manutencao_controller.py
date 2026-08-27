import base64
import os
import uuid

from flask import Blueprint, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from core import storage
from core.audit import log_evento
from core.config import HISTORICO_ACAO_MAX, STATUS_LIST_MANUTENCAO, UPLOADS_DIR
from core.security import login_required, permission_required
from core.time_utils import get_brasilia_time

manutencao_bp = Blueprint('manutencao', __name__)


def _pode_ver(manutencao: dict) -> bool:
    """Funcionário só vê manutenção que ele abriu ou da qual é responsável
    — mesma regra de tickets (ver tickets_controller)."""
    if session['role'] != 'funcionario':
        return True
    return (manutencao.get('criado_por_id') == session['user_id']
            or manutencao.get('responsavel_id') == session['user_id'])


@manutencao_bp.route('/manutencoes')
@login_required
@permission_required('manutencao_ver')
def manutencoes():
    itens = storage.load_manutencoes()
    if session['role'] == 'funcionario':
        itens = [m for m in itens if _pode_ver(m)]

    filtro_status  = request.args.get('status', '')
    filtro_unidade = request.args.get('unidade', '')
    busca          = request.args.get('busca', '').strip().lower()

    if filtro_status:  itens = [m for m in itens if m['status'] == filtro_status]
    if filtro_unidade: itens = [m for m in itens if m.get('unidade') == filtro_unidade]
    if busca:          itens = [m for m in itens if
                                busca in m.get('numero', '').lower() or
                                busca in m.get('descricao', '').lower() or
                                busca in m.get('responsavel_nome', '').lower()]

    equipamentos_por_id = {e['id']: e for e in storage.load_equipamentos()}
    for m in itens:
        m['equipamento_nome'] = equipamentos_por_id.get(m['equipamento_id'], {}).get('nome', '—')

    itens = sorted(itens, key=lambda x: x.get('data_criacao', ''), reverse=True)
    return render_template('manutencoes.html', manutencoes=itens,
                           unidades=storage.get_unidades(), status_list=STATUS_LIST_MANUTENCAO,
                           filtro_status=filtro_status, filtro_unidade=filtro_unidade, busca=busca)


@manutencao_bp.route('/manutencoes/nova', methods=['GET', 'POST'])
@login_required
@permission_required('manutencao_gerenciar')
def nova_manutencao():
    error = None
    equipamentos = [e for e in storage.load_equipamentos() if e.get('ativo', True)]
    usuarios = [u for u in storage.load_users() if u.get('ativo', True)]

    if request.method == 'POST':
        equipamento_id = request.form.get('equipamento_id', '')
        descricao      = request.form.get('descricao', '').strip()
        responsavel_id = request.form.get('responsavel_id', '') or None

        equipamento = next((e for e in equipamentos if e['id'] == equipamento_id), None)
        if not equipamento or not descricao:
            error = 'Preencha todos os campos obrigatórios.'
        else:
            responsavel = next((u for u in usuarios if u['id'] == responsavel_id), None) if responsavel_id else None
            now = get_brasilia_time()
            manutencao = {
                'id': str(uuid.uuid4()),
                'numero': storage.get_next_manutencao_numero(),
                'equipamento_id': equipamento['id'],
                'unidade': equipamento['unidade'],
                'responsavel_id': responsavel['id'] if responsavel else None,
                'responsavel_nome': responsavel['name'] if responsavel else '',
                'descricao': descricao,
                'data_criacao': now.strftime('%Y-%m-%dT%H:%M:%S'),
                'data_formatada': now.strftime('%d/%m/%Y %H:%M:%S'),
                'status': STATUS_LIST_MANUTENCAO[0],
                'criado_por': session['name'],
                'criado_por_id': session['user_id'],
                'assinatura_filename': None,
                'historico': [{'acao': 'Manutenção aberta', 'por': session['name'],
                               'data': now.strftime('%d/%m/%Y %H:%M:%S')}],
            }
            itens = storage.load_manutencoes()
            itens.append(manutencao)
            storage.save_manutencoes(itens)
            log_evento('manutencao_criada', detalhes=f"{manutencao['numero']} — {equipamento['nome']}",
                       entidade_tipo='manutencao', entidade_id=manutencao['id'])
            return redirect(url_for('manutencao.ver_manutencao', manutencao_id=manutencao['id']))

    return render_template('abrir_manutencao.html', equipamentos=equipamentos, usuarios=usuarios, error=error)


@manutencao_bp.route('/manutencao/<manutencao_id>')
@login_required
@permission_required('manutencao_ver')
def ver_manutencao(manutencao_id):
    itens = storage.load_manutencoes()
    manutencao = next((m for m in itens if m['id'] == manutencao_id), None)
    if not manutencao or not _pode_ver(manutencao):
        return redirect(url_for('manutencao.manutencoes'))
    equipamento = next((e for e in storage.load_equipamentos() if e['id'] == manutencao['equipamento_id']), None)
    return render_template('ver_manutencao.html', manutencao=manutencao, equipamento=equipamento,
                           status_list=STATUS_LIST_MANUTENCAO)


@manutencao_bp.route('/manutencao/<manutencao_id>/atualizar', methods=['POST'])
@login_required
@permission_required('manutencao_gerenciar')
def atualizar_manutencao(manutencao_id):
    itens = storage.load_manutencoes()
    manutencao = next((m for m in itens if m['id'] == manutencao_id), None)
    if not manutencao:
        return redirect(url_for('manutencao.manutencoes'))
    novo_status = request.form.get('status', '')
    comentario  = request.form.get('comentario', '').strip()
    if novo_status in STATUS_LIST_MANUTENCAO:
        now = get_brasilia_time()
        manutencao['status'] = novo_status
        entrada = f'Status alterado para "{novo_status}"'
        if comentario:
            entrada += f' — {comentario}'
        entrada = entrada[:HISTORICO_ACAO_MAX]
        manutencao['historico'].append({'acao': entrada, 'por': session['name'],
                                        'data': now.strftime('%d/%m/%Y %H:%M:%S')})
        storage.save_manutencoes(itens)
        log_evento('manutencao_atualizada', detalhes=f"{manutencao['numero']} — {entrada}",
                   entidade_tipo='manutencao', entidade_id=manutencao_id)
    return redirect(url_for('manutencao.ver_manutencao', manutencao_id=manutencao_id))


@manutencao_bp.route('/manutencao/<manutencao_id>/comentar', methods=['POST'])
@login_required
@permission_required('manutencao_gerenciar')
def comentar_manutencao(manutencao_id):
    itens = storage.load_manutencoes()
    manutencao = next((m for m in itens if m['id'] == manutencao_id), None)
    if not manutencao:
        return redirect(url_for('manutencao.manutencoes'))
    comentario = request.form.get('comentario', '').strip()

    arquivo_info = None
    if 'arquivo' in request.files:
        file = request.files['arquivo']
        if file and file.filename and storage.allowed_file(file.filename):
            fname = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
            file.save(os.path.join(UPLOADS_DIR, fname))
            arquivo_info = {'filename': fname, 'original_name': file.filename}

    if comentario or arquivo_info:
        now = get_brasilia_time()
        acao = f'Observação: {comentario}' if comentario else 'Anexo adicionado'
        entrada = {'acao': acao[:HISTORICO_ACAO_MAX], 'por': session['name'],
                   'data': now.strftime('%d/%m/%Y %H:%M:%S')}
        if arquivo_info:
            entrada['arquivo'] = arquivo_info
        manutencao['historico'].append(entrada)
        storage.save_manutencoes(itens)
        log_evento('manutencao_comentada', detalhes=f"{manutencao['numero']} — {(comentario or 'anexo')[:200]}",
                   entidade_tipo='manutencao', entidade_id=manutencao_id)
    return redirect(url_for('manutencao.ver_manutencao', manutencao_id=manutencao_id))


@manutencao_bp.route('/manutencao/<manutencao_id>/assinatura', methods=['POST'])
@login_required
@permission_required('manutencao_gerenciar')
def assinar_manutencao(manutencao_id):
    itens = storage.load_manutencoes()
    manutencao = next((m for m in itens if m['id'] == manutencao_id), None)
    if not manutencao:
        return redirect(url_for('manutencao.manutencoes'))

    data_url = request.form.get('assinatura_png', '')
    if data_url.startswith('data:image/png;base64,'):
        png_bytes = base64.b64decode(data_url.split(',', 1)[1])
        fname = f"assinatura_{uuid.uuid4().hex}.png"
        with open(os.path.join(UPLOADS_DIR, fname), 'wb') as f:
            f.write(png_bytes)
        manutencao['assinatura_filename'] = fname
        now = get_brasilia_time()
        manutencao['historico'].append({
            'acao': 'Assinatura do prestador de serviço registrada',
            'por': session['name'], 'data': now.strftime('%d/%m/%Y %H:%M:%S'),
        })
        storage.save_manutencoes(itens)
        log_evento('manutencao_assinatura_registrada', detalhes=manutencao['numero'],
                   entidade_tipo='manutencao', entidade_id=manutencao_id)
    return redirect(url_for('manutencao.ver_manutencao', manutencao_id=manutencao_id))
