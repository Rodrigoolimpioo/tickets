import uuid

from ..config import PERMISSOES_IDS
from .. import storage

"""Regras de negócio dos perfis de acesso (roles parametrizáveis). Um
perfil é uma lista de módulos liberados (`permissoes`); Admin sempre tem
acesso total, Supervisor e Funcionário vêm com perfis padrão editáveis,
e novos perfis podem ser criados a qualquer momento — tanto pela tela de
Configurações quanto pelos endpoints /api/perfis."""


def listar_perfis() -> list:
    return storage.load_config().get('perfis', [])


def obter_perfil(perfil_id: str):
    return next((p for p in listar_perfis() if p['id'] == perfil_id), None)


def _sanitize_permissoes(permissoes) -> list:
    return [p for p in (permissoes or []) if p in PERMISSOES_IDS]


def criar_perfil(nome: str, descricao: str, permissoes):
    nome = (nome or '').strip()
    if not nome:
        return False, 'nome_obrigatorio', None

    cfg = storage.load_config()
    perfil = {
        'id': str(uuid.uuid4()),
        'nome': nome,
        'descricao': (descricao or '').strip(),
        'permissoes': _sanitize_permissoes(permissoes),
        'padrao': False,
    }
    cfg.setdefault('perfis', []).append(perfil)
    storage.save_config(cfg)
    return True, None, perfil


def atualizar_perfil(perfil_id: str, nome: str, descricao: str, permissoes):
    cfg = storage.load_config()
    perfil = next((p for p in cfg.get('perfis', []) if p['id'] == perfil_id), None)
    if not perfil:
        return False, 'perfil_nao_encontrado'

    nome = (nome or '').strip()
    if nome:
        perfil['nome'] = nome
    perfil['descricao'] = (descricao or '').strip()
    perfil['permissoes'] = _sanitize_permissoes(permissoes)
    storage.save_config(cfg)
    return True, None


def excluir_perfil(perfil_id: str):
    cfg = storage.load_config()
    perfil = next((p for p in cfg.get('perfis', []) if p['id'] == perfil_id), None)
    if not perfil:
        return False, 'perfil_nao_encontrado'
    if perfil.get('padrao', False):
        return False, 'perfil_padrao_nao_pode_ser_excluido'
    cfg['perfis'] = [p for p in cfg['perfis'] if p['id'] != perfil_id]
    storage.save_config(cfg)
    return True, None
