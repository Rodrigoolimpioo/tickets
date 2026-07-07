import os
import uuid

from flask import Blueprint, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from core import storage
from core.config import STATUS_LIST, UPLOADS_DIR
from core.security import login_required, permission_required, role_required
from core.time_utils import get_brasilia_time

tickets_bp = Blueprint('tickets', __name__)


@tickets_bp.route('/abrir-ticket', methods=['GET', 'POST'])
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
                if file and file.filename and storage.allowed_file(file.filename):
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
                    'numero': storage.get_next_ticket_number(),
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
                tickets = storage.load_tickets()
                tickets.append(ticket)
                storage.save_tickets(tickets)
                return redirect(url_for('tickets.ver_ticket', ticket_id=ticket['id']))

    return render_template('abrir_ticket.html', sistemas=storage.get_sistemas(), error=error)


@tickets_bp.route('/acompanhamento')
@login_required
@permission_required('acompanhamento')
def acompanhamento():
    tickets = storage.load_tickets()
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
                           sistemas=storage.get_sistemas(), status_list=STATUS_LIST,
                           filtro_status=filtro_status, filtro_sistema=filtro_sistema, busca=busca)


@tickets_bp.route('/ticket/<ticket_id>')
@login_required
@permission_required('ver_ticket')
def ver_ticket(ticket_id):
    tickets = storage.load_tickets()
    ticket = next((t for t in tickets if t['id'] == ticket_id), None)
    if not ticket:
        return redirect(url_for('tickets.acompanhamento'))
    if session['role'] == 'funcionario' and ticket.get('criado_por_id') != session['user_id']:
        return redirect(url_for('tickets.acompanhamento'))
    return render_template('ver_ticket.html', ticket=ticket, status_list=STATUS_LIST)


@tickets_bp.route('/ticket/<ticket_id>/atualizar', methods=['POST'])
@login_required
@permission_required('atualizar_ticket')
def atualizar_ticket(ticket_id):
    tickets = storage.load_tickets()
    ticket = next((t for t in tickets if t['id'] == ticket_id), None)
    if not ticket:
        return redirect(url_for('tickets.acompanhamento'))
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
        storage.save_tickets(tickets)
    return redirect(url_for('tickets.ver_ticket', ticket_id=ticket_id))


@tickets_bp.route('/ticket/<ticket_id>/excluir', methods=['POST'])
@login_required
@role_required('admin')
def excluir_ticket(ticket_id):
    tickets = storage.load_tickets()
    ticket = next((t for t in tickets if t['id'] == ticket_id), None)
    if ticket:
        if ticket.get('arquivo') and ticket['arquivo'].get('filename'):
            path = os.path.join(UPLOADS_DIR, ticket['arquivo']['filename'])
            if os.path.exists(path):
                os.remove(path)
        tickets = [t for t in tickets if t['id'] != ticket_id]
        storage.save_tickets(tickets)
    return redirect(url_for('tickets.acompanhamento'))


@tickets_bp.route('/ticket/<ticket_id>/comentar', methods=['POST'])
@login_required
@permission_required('comentar_ticket')
def comentar_ticket(ticket_id):
    tickets = storage.load_tickets()
    ticket = next((t for t in tickets if t['id'] == ticket_id), None)
    if not ticket:
        return redirect(url_for('tickets.acompanhamento'))
    if session['role'] == 'funcionario' and ticket.get('criado_por_id') != session['user_id']:
        return redirect(url_for('tickets.acompanhamento'))
    comentario = request.form.get('comentario', '').strip()
    if comentario:
        now = get_brasilia_time()
        ticket['historico'].append({'acao': f'Comentário: {comentario}',
                                    'por': session['name'],
                                    'data': now.strftime('%d/%m/%Y %H:%M:%S')})
        storage.save_tickets(tickets)
    return redirect(url_for('tickets.ver_ticket', ticket_id=ticket_id))
