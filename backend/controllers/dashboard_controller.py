from flask import Blueprint, render_template, request, session

from core import storage
from core.security import login_required, permission_required

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/dashboard')
@login_required
@permission_required('dashboard')
def dashboard():
    tab = request.args.get('tab', 'tickets')
    pode_ver_manutencao = session['role'] == 'admin' or 'manutencao_ver' in session.get('permissoes', [])
    if tab == 'manutencoes' and not pode_ver_manutencao:
        tab = 'tickets'

    tickets = storage.load_tickets()
    if session['role'] == 'funcionario':
        tickets = [t for t in tickets if t.get('criado_por_id') == session['user_id']]

    stats = {
        'total':        len(tickets),
        'aberto':       sum(1 for t in tickets if t['status'] == 'Aberto'),
        'em_andamento': sum(1 for t in tickets if t['status'] == 'Em Andamento'),
        'resolvido':    sum(1 for t in tickets if t['status'] == 'Resolvido'),
        'fechado':      sum(1 for t in tickets if t['status'] == 'Incubado'),
    }
    sistemas_stats = {s: sum(1 for t in tickets if t.get('sistema') == s) for s in storage.get_sistemas()}
    recentes = sorted(tickets, key=lambda x: x.get('data_criacao', ''), reverse=True)[:5]

    manut_stats = {'total': 0, 'aberta': 0, 'em_andamento': 0, 'concluida': 0,
                   'cancelada': 0, 'valor_total': 0}
    manut_recentes = []
    unidades_stats = {}

    if pode_ver_manutencao:
        manutencoes = storage.load_manutencoes()
        if session['role'] == 'funcionario':
            manutencoes = [m for m in manutencoes if m.get('criado_por_id') == session['user_id']
                           or m.get('responsavel_id') == session['user_id']]

        manut_stats = {
            'total':         len(manutencoes),
            'aberta':        sum(1 for m in manutencoes if m['status'] == 'Aberta'),
            'em_andamento':  sum(1 for m in manutencoes if m['status'] == 'Em Andamento'),
            'concluida':     sum(1 for m in manutencoes if m['status'] == 'Concluída'),
            'cancelada':     sum(1 for m in manutencoes if m['status'] == 'Cancelada'),
            'valor_total':   sum(m['valor'] for m in manutencoes if m.get('valor') is not None),
        }
        unidades_stats = {u: sum(1 for m in manutencoes if m.get('unidade') == u) for u in storage.get_unidades()}

        equipamentos_por_id = {e['id']: e for e in storage.load_equipamentos()}
        manut_recentes = sorted(manutencoes, key=lambda x: x.get('data_criacao', ''), reverse=True)[:5]
        for m in manut_recentes:
            m['equipamento_nome'] = equipamentos_por_id.get(m['equipamento_id'], {}).get('nome', '—')

    return render_template('dashboard.html', tab=tab, pode_ver_manutencao=pode_ver_manutencao,
                           stats=stats, recentes=recentes, sistemas_stats=sistemas_stats,
                           manut_stats=manut_stats, manut_recentes=manut_recentes,
                           unidades_stats=unidades_stats)
