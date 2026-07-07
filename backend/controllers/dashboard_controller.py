from flask import Blueprint, render_template, session

from core import storage
from core.security import login_required, permission_required

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/dashboard')
@login_required
@permission_required('dashboard')
def dashboard():
    tickets = storage.load_tickets()
    if session['role'] == 'funcionario':
        tickets = [t for t in tickets if t.get('criado_por_id') == session['user_id']]

    stats = {
        'total':        len(tickets),
        'aberto':       sum(1 for t in tickets if t['status'] == 'Aberto'),
        'em_andamento': sum(1 for t in tickets if t['status'] == 'Em Andamento'),
        'resolvido':    sum(1 for t in tickets if t['status'] == 'Resolvido'),
        'fechado':      sum(1 for t in tickets if t['status'] == 'Fechado'),
    }
    sistemas_stats = {s: sum(1 for t in tickets if t.get('sistema') == s) for s in storage.get_sistemas()}
    recentes = sorted(tickets, key=lambda x: x.get('data_criacao', ''), reverse=True)[:5]
    return render_template('dashboard.html', stats=stats, recentes=recentes, sistemas_stats=sistemas_stats)
