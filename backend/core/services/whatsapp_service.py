from .. import storage
from ..config import APP_BASE_URL
from ..whatsapp import enviar_whatsapp

"""Regra de negócio da notificação de andamento de ticket via WhatsApp,
chamada pelos controllers depois que o ticket já foi salvo (best-effort —
nunca deve impedir a abertura/atualização do ticket em si).

Regra de negócio (definida pelo cliente): administradores são notificados
quando um ticket é aberto; quando um ticket recebe uma resposta (mudança de
status), são notificados quem abriu o ticket (se for supervisor ou
funcionário) e, sempre, todos os supervisores — que atuam como uma camada
de acompanhamento geral, independente de terem aberto o ticket ou não.
Cada evento respeita o toggle + mensagem customizável daquele status em
Configurações → WhatsApp."""

_ROLES_NOTIFICADOS_NA_ABERTURA_DO_PROPRIO_TICKET = {'supervisor', 'funcionario'}


class _PlaceholdersSeguro(dict):
    """dict usado com str.format_map: variável desconhecida no template
    vira string vazia em vez de estourar KeyError — um typo no placeholder
    não pode quebrar o envio da mensagem."""
    def __missing__(self, key):
        return ''


def _link_ticket(ticket: dict) -> str:
    return f"{APP_BASE_URL.rstrip('/')}/ticket/{ticket['id']}"


def _montar_mensagem(ticket: dict, novo_status: str, comentario: str, atualizado_por: str,
                      template: str = '') -> str:
    link = _link_ticket(ticket)
    dados = _PlaceholdersSeguro(
        numero=ticket['numero'],
        sistema=ticket['sistema'],
        status=novo_status,
        comentario=comentario or '',
        atualizado_por=atualizado_por,
        criado_por=ticket.get('criado_por', ''),
        link=link,
    )

    if template:
        try:
            return template.format_map(dados)
        except (ValueError, IndexError):
            pass  # template malformado (ex.: "{" solto) — cai no texto padrão abaixo

    linhas = [
        f"🎫 Ticket {ticket['numero']} — {ticket['sistema']}",
        f'Status: {novo_status}',
    ]
    if comentario:
        linhas.append(comentario)
    linhas.append(f'Atualizado por {atualizado_por}')
    linhas.append(link)
    return '\n'.join(linhas)


def _config_status(novo_status: str):
    """Retorna (ativo, template) para o status, ou (False, '') se o
    WhatsApp estiver desligado no geral."""
    cfg = storage.load_config()
    wpp = cfg.get('whatsapp', {})
    if not wpp.get('enabled'):
        return False, ''
    ativo = wpp.get('status_ativo', {}).get(novo_status, False)
    template = wpp.get('status_mensagem', {}).get(novo_status, '')
    return ativo, template


def notificar_ticket_aberto(ticket: dict) -> None:
    """Dispara para todo admin ativo com telefone cadastrado, gatilhado
    pelo toggle do status 'Aberto'. A {comentario} do template, aqui,
    recebe a descrição da ocorrência (não há comentário de resposta ainda
    nesse ponto do fluxo). A mensagem inclui um link direto pro ticket —
    login sem sessão ativa redireciona de volta pra cá depois de logar
    (ver core.security.safe_next_path)."""
    ativo, template = _config_status('Aberto')
    if not ativo:
        return

    admins = [u for u in storage.load_users()
              if u.get('role') == 'admin' and u.get('ativo', True) and u.get('telefone')]
    if not admins:
        return

    mensagem = _montar_mensagem(ticket, 'Aberto', ticket.get('ocorrencia', ''),
                                 ticket.get('criado_por', ''), template)
    for admin in admins:
        enviar_whatsapp(admin['telefone'], mensagem)


def notificar_status_ticket(ticket: dict, novo_status: str, comentario: str, atualizado_por: str) -> None:
    """Dispara para quem abriu o ticket (só se for supervisor ou
    funcionário) e sempre para todos os supervisores ativos com telefone —
    administrador não recebe notificação de resposta (só a de abertura,
    via notificar_ticket_aberto). Um mesmo telefone nunca recebe duas
    mensagens (ex.: supervisor que abriu o próprio ticket)."""
    ativo, template = _config_status(novo_status)
    if not ativo:
        return

    usuarios = storage.load_users()
    telefones = set()

    criador = next((u for u in usuarios if u['id'] == ticket.get('criado_por_id')), None)
    if (criador and criador.get('role') in _ROLES_NOTIFICADOS_NA_ABERTURA_DO_PROPRIO_TICKET
            and criador.get('telefone')):
        telefones.add(criador['telefone'])

    for u in usuarios:
        if u.get('role') == 'supervisor' and u.get('ativo', True) and u.get('telefone'):
            telefones.add(u['telefone'])

    if not telefones:
        return

    mensagem = _montar_mensagem(ticket, novo_status, comentario, atualizado_por, template)
    for telefone in telefones:
        enviar_whatsapp(telefone, mensagem)
