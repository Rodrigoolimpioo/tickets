from flask import Blueprint, redirect, request, session, url_for

from core.security import login_required, role_required
from core.services import usuarios_service

usuarios_bp = Blueprint('usuarios', __name__)


@usuarios_bp.route('/configuracoes/usuario/criar', methods=['POST'])
@login_required
@role_required('admin')
def cfg_criar_usuario():
    ok, err, _ = usuarios_service.criar_usuario(
        username=request.form.get('username', ''),
        password=request.form.get('password', ''),
        name=request.form.get('name', ''),
        role=request.form.get('role', 'funcionario'),
        email=request.form.get('email', ''),
        perfil_id=request.form.get('perfil_id', ''),
    )
    if not ok:
        return redirect(url_for('config.configuracoes', tab='usuarios', err=err))
    return redirect(url_for('config.configuracoes', tab='usuarios', msg='usuario_criado'))


@usuarios_bp.route('/configuracoes/usuario/<user_id>/toggle', methods=['POST'])
@login_required
@role_required('admin')
def cfg_toggle_usuario(user_id):
    usuarios_service.toggle_usuario(user_id, session['user_id'])
    return redirect(url_for('config.configuracoes', tab='usuarios'))


@usuarios_bp.route('/configuracoes/usuario/<user_id>/senha', methods=['POST'])
@login_required
@role_required('admin')
def cfg_alterar_senha(user_id):
    usuarios_service.alterar_senha(user_id, request.form.get('nova_senha', ''))
    return redirect(url_for('config.configuracoes', tab='usuarios', msg='senha_alterada'))


@usuarios_bp.route('/configuracoes/usuario/<user_id>/perfil', methods=['POST'])
@login_required
@role_required('admin')
def cfg_alterar_perfil_usuario(user_id):
    usuarios_service.alterar_perfil_usuario(user_id, request.form.get('perfil_id', ''))
    return redirect(url_for('config.configuracoes', tab='usuarios', msg='perfil_atualizado'))


@usuarios_bp.route('/configuracoes/usuario/<user_id>/excluir', methods=['POST'])
@login_required
@role_required('admin')
def cfg_excluir_usuario(user_id):
    usuarios_service.excluir_usuario(user_id, session['user_id'])
    return redirect(url_for('config.configuracoes', tab='usuarios', msg='usuario_excluido'))
