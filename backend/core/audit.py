from flask import session

from db.repositories import logs_repository

from .time_utils import get_brasilia_time, get_client_ip

# Ações conhecidas — usadas na tela de Logs para montar o filtro por tipo.
ACOES = [
    'login_sucesso', 'login_falha', 'logout',
    'ticket_criado', 'ticket_atualizado', 'ticket_comentado', 'ticket_excluido',
    'usuario_criado', 'usuario_ativado', 'usuario_desativado',
    'usuario_senha_alterada', 'usuario_perfil_alterado', 'usuario_excluido',
    'perfil_criado', 'perfil_atualizado', 'perfil_excluido',
    'config_ip_ativado', 'config_ip_desativado', 'config_ip_adicionado', 'config_ip_removido',
    'config_horario_ativado', 'config_horario_desativado', 'config_horario_atualizado',
    'config_sistema_adicionado', 'config_sistema_removido',
    'config_personalizacao_atualizada', 'config_logo_atualizado', 'config_logo_removido',
    'config_whatsapp_ativado', 'config_whatsapp_desativado',
    'config_whatsapp_status_atualizado',
    'whatsapp_enviado', 'whatsapp_falhou',
]


def log_evento(acao: str, detalhes: str = None, entidade_tipo: str = None,
                entidade_id: str = None, usuario_id: str = None, usuario_nome: str = None) -> None:
    """Registra um evento de auditoria. Usa a sessão atual como autor por
    padrão (usuario_id/usuario_nome só precisam ser passados explicitamente
    em casos sem sessão ainda montada, como uma tentativa de login)."""
    logs_repository.registrar(
        acao=acao,
        quando=get_brasilia_time(),
        usuario_id=usuario_id if usuario_id is not None else session.get('user_id'),
        usuario_nome=usuario_nome if usuario_nome is not None else session.get('name'),
        detalhes=detalhes,
        ip=get_client_ip(),
        entidade_tipo=entidade_tipo,
        entidade_id=entidade_id,
    )
