from flask import Blueprint, Response, render_template, request, session

from core import reports, storage
from core.config import STATUS_LIST, STATUS_LIST_MANUTENCAO
from core.security import login_required, permission_required

relatorios_bp = Blueprint('relatorios', __name__)


def _dentro_periodo(data_criacao: str, inicio: str, fim: str) -> bool:
    # data_criacao é 'YYYY-MM-DDTHH:MM:SS'; inicio/fim são 'YYYY-MM-DD' (input type=date)
    data = data_criacao[:10]
    if inicio and data < inicio:
        return False
    if fim and data > fim:
        return False
    return True


def _filtrar_manutencoes(args):
    itens = storage.load_manutencoes()
    if session['role'] == 'funcionario':
        itens = [m for m in itens if m.get('criado_por_id') == session['user_id']
                 or m.get('responsavel_id') == session['user_id']]

    inicio = args.get('inicio', '')
    fim = args.get('fim', '')
    unidade = args.get('unidade', '')
    equipamento_id = args.get('equipamento_id', '')
    status = args.get('status', '')
    responsavel_id = args.get('responsavel_id', '')

    if inicio or fim:
        itens = [m for m in itens if _dentro_periodo(m['data_criacao'], inicio, fim)]
    if unidade:        itens = [m for m in itens if m.get('unidade') == unidade]
    if equipamento_id: itens = [m for m in itens if m.get('equipamento_id') == equipamento_id]
    if status:         itens = [m for m in itens if m.get('status') == status]
    if responsavel_id: itens = [m for m in itens if m.get('responsavel_id') == responsavel_id]

    equipamentos_por_id = {e['id']: e for e in storage.load_equipamentos()}
    for m in itens:
        m['equipamento_nome'] = equipamentos_por_id.get(m['equipamento_id'], {}).get('nome', '—')
        m['valor_formatado'] = f"{m['valor']:.2f}".replace('.', ',') if m.get('valor') is not None else ''

    return sorted(itens, key=lambda x: x.get('data_criacao', ''), reverse=True)


def _filtrar_tickets(args):
    itens = storage.load_tickets()
    if session['role'] == 'funcionario':
        itens = [t for t in itens if t.get('criado_por_id') == session['user_id']]

    inicio = args.get('inicio', '')
    fim = args.get('fim', '')
    unidade = args.get('unidade', '')
    status = args.get('status', '')

    if inicio or fim:
        itens = [t for t in itens if _dentro_periodo(t['data_criacao'], inicio, fim)]
    if unidade: itens = [t for t in itens if t.get('unidade') == unidade]
    if status:  itens = [t for t in itens if t.get('status') == status]

    return sorted(itens, key=lambda x: x.get('data_criacao', ''), reverse=True)


_COLUNAS_MANUTENCOES = [
    ('numero', 'Número'), ('equipamento_nome', 'Máquinario'), ('unidade', 'Unidade'),
    ('status', 'Status'), ('responsavel_nome', 'Responsável'), ('tecnico', 'Técnico'),
    ('empresa', 'Empresa'), ('descricao', 'Motivo'),
    ('servico_feito', 'Serviço Feito'), ('valor_formatado', 'Valor R$'),
    ('criado_por', 'Aberto por'), ('data_formatada', 'Data'),
]
_COLUNAS_TICKETS = [
    ('numero', 'Número'), ('nome', 'Nome'), ('sistema', 'Sistema'), ('unidade', 'Unidade'),
    ('status', 'Status'), ('criado_por', 'Aberto por'), ('data_formatada', 'Data'),
    ('data_fechamento_formatada', 'Data de Fechamento'),
]


@relatorios_bp.route('/relatorios')
@login_required
@permission_required('relatorios_ver')
def relatorios():
    aba = request.args.get('aba', 'manutencoes')
    manutencoes = _filtrar_manutencoes(request.args) if aba == 'manutencoes' else []
    tickets = _filtrar_tickets(request.args) if aba == 'tickets' else []

    return render_template(
        'relatorios.html', aba=aba, manutencoes=manutencoes, tickets=tickets,
        unidades=storage.get_unidades(), equipamentos=storage.load_equipamentos(),
        usuarios=storage.load_users(), status_list_manutencao=STATUS_LIST_MANUTENCAO,
        status_list_ticket=STATUS_LIST, filtros=request.args,
    )


@relatorios_bp.route('/relatorios/manutencoes/exportar')
@login_required
@permission_required('relatorios_ver')
def exportar_manutencoes():
    linhas = _filtrar_manutencoes(request.args)
    formato = request.args.get('formato', 'xlsx')
    if formato == 'pdf':
        buffer = reports.gerar_pdf('Relatório de Manutenções', _COLUNAS_MANUTENCOES, linhas)
        return Response(buffer.getvalue(), mimetype='application/pdf',
                        headers={'Content-Disposition': 'attachment; filename=manutencoes.pdf'})
    buffer = reports.gerar_excel('Manutenções', _COLUNAS_MANUTENCOES, linhas)
    return Response(buffer.getvalue(), mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    headers={'Content-Disposition': 'attachment; filename=manutencoes.xlsx'})


@relatorios_bp.route('/relatorios/tickets/exportar')
@login_required
@permission_required('relatorios_ver')
def exportar_tickets():
    linhas = _filtrar_tickets(request.args)
    formato = request.args.get('formato', 'xlsx')
    if formato == 'pdf':
        buffer = reports.gerar_pdf('Relatório de Tickets', _COLUNAS_TICKETS, linhas)
        return Response(buffer.getvalue(), mimetype='application/pdf',
                        headers={'Content-Disposition': 'attachment; filename=tickets.pdf'})
    buffer = reports.gerar_excel('Tickets', _COLUNAS_TICKETS, linhas)
    return Response(buffer.getvalue(), mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    headers={'Content-Disposition': 'attachment; filename=tickets.xlsx'})
