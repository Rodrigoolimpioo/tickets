from flask import Blueprint, redirect, request, url_for

from core.audit import log_evento
from core.security import login_required, role_required
from core.services import perfis_service

perfis_bp = Blueprint('perfis', __name__)


@perfis_bp.route('/configuracoes/perfil/criar', methods=['POST'])
@login_required
@role_required('admin')
def cfg_perfil_criar():
    nome = request.form.get('nome', '')
    ok, err, perfil = perfis_service.criar_perfil(
        nome=nome,
        descricao=request.form.get('descricao', ''),
        permissoes=request.form.getlist('permissoes'),
    )
    if not ok:
        return redirect(url_for('config.configuracoes', tab='perfis', err=err))
    log_evento('perfil_criado', detalhes=nome, entidade_tipo='perfil', entidade_id=perfil['id'])
    return redirect(url_for('config.configuracoes', tab='perfis', msg='perfil_criado'))


@perfis_bp.route('/configuracoes/perfil/<perfil_id>/atualizar', methods=['POST'])
@login_required
@role_required('admin')
def cfg_perfil_atualizar(perfil_id):
    nome = request.form.get('nome', '')
    ok, _ = perfis_service.atualizar_perfil(
        perfil_id,
        nome=nome,
        descricao=request.form.get('descricao', ''),
        permissoes=request.form.getlist('permissoes'),
    )
    if ok:
        log_evento('perfil_atualizado', detalhes=nome, entidade_tipo='perfil', entidade_id=perfil_id)
    return redirect(url_for('config.configuracoes', tab='perfis', msg='perfil_atualizado'))


@perfis_bp.route('/configuracoes/perfil/<perfil_id>/excluir', methods=['POST'])
@login_required
@role_required('admin')
def cfg_perfil_excluir(perfil_id):
    perfil = perfis_service.obter_perfil(perfil_id)
    ok, _ = perfis_service.excluir_perfil(perfil_id)
    if ok:
        log_evento('perfil_excluido', detalhes=perfil['nome'] if perfil else perfil_id,
                   entidade_tipo='perfil', entidade_id=perfil_id)
    return redirect(url_for('config.configuracoes', tab='perfis', msg='perfil_removido'))
