from flask import Blueprint, redirect, request, url_for

from core.security import login_required, role_required
from core.services import perfis_service

perfis_bp = Blueprint('perfis', __name__)


@perfis_bp.route('/configuracoes/perfil/criar', methods=['POST'])
@login_required
@role_required('admin')
def cfg_perfil_criar():
    ok, err, _ = perfis_service.criar_perfil(
        nome=request.form.get('nome', ''),
        descricao=request.form.get('descricao', ''),
        permissoes=request.form.getlist('permissoes'),
    )
    if not ok:
        return redirect(url_for('config.configuracoes', tab='perfis', err=err))
    return redirect(url_for('config.configuracoes', tab='perfis', msg='perfil_criado'))


@perfis_bp.route('/configuracoes/perfil/<perfil_id>/atualizar', methods=['POST'])
@login_required
@role_required('admin')
def cfg_perfil_atualizar(perfil_id):
    perfis_service.atualizar_perfil(
        perfil_id,
        nome=request.form.get('nome', ''),
        descricao=request.form.get('descricao', ''),
        permissoes=request.form.getlist('permissoes'),
    )
    return redirect(url_for('config.configuracoes', tab='perfis', msg='perfil_atualizado'))


@perfis_bp.route('/configuracoes/perfil/<perfil_id>/excluir', methods=['POST'])
@login_required
@role_required('admin')
def cfg_perfil_excluir(perfil_id):
    perfis_service.excluir_perfil(perfil_id)
    return redirect(url_for('config.configuracoes', tab='perfis', msg='perfil_removido'))
