from flask import Blueprint, redirect, request, session, url_for

from core.audit import log_evento
from core.security import login_required, role_required
from core.services import usuarios_service

usuarios_bp = Blueprint('usuarios', __name__)


def _usuario(user_id):
    return next((u for u in usuarios_service.listar_usuarios() if u['id'] == user_id), None)


def _nome_usuario(user_id):
    user = _usuario(user_id)
    return user['username'] if user else user_id


@usuarios_bp.route('/configuracoes/usuario/criar', methods=['POST'])
@login_required
@role_required('admin')
def cfg_criar_usuario():
    username = request.form.get('username', '')
    ok, err, novo = usuarios_service.criar_usuario(
        username=username,
        password=request.form.get('password', ''),
        name=request.form.get('name', ''),
        role=request.form.get('role', 'funcionario'),
        email=request.form.get('email', ''),
        telefone=request.form.get('telefone', ''),
        perfil_id=request.form.get('perfil_id', ''),
    )
    if not ok:
        return redirect(url_for('config.configuracoes', tab='usuarios', err=err))
    log_evento('usuario_criado', detalhes=f"{username} (role: {novo['role']})",
               entidade_tipo='usuario', entidade_id=novo['id'])
    return redirect(url_for('config.configuracoes', tab='usuarios', msg='usuario_criado'))


@usuarios_bp.route('/configuracoes/usuario/<user_id>/toggle', methods=['POST'])
@login_required
@role_required('admin')
def cfg_toggle_usuario(user_id):
    antes = _usuario(user_id)
    ok, _ = usuarios_service.toggle_usuario(user_id, session['user_id'])
    if ok and antes:
        # toggle inverte o estado — "antes" ainda reflete o valor pré-troca
        acao = 'usuario_desativado' if antes.get('ativo', True) else 'usuario_ativado'
        log_evento(acao, detalhes=antes['username'], entidade_tipo='usuario', entidade_id=user_id)
    return redirect(url_for('config.configuracoes', tab='usuarios'))


@usuarios_bp.route('/configuracoes/usuario/<user_id>/senha', methods=['POST'])
@login_required
@role_required('admin')
def cfg_alterar_senha(user_id):
    nome = _nome_usuario(user_id)
    ok, _ = usuarios_service.alterar_senha(user_id, request.form.get('nova_senha', ''))
    if ok:
        log_evento('usuario_senha_alterada', detalhes=nome, entidade_tipo='usuario', entidade_id=user_id)
    return redirect(url_for('config.configuracoes', tab='usuarios', msg='senha_alterada'))


@usuarios_bp.route('/configuracoes/usuario/<user_id>/perfil', methods=['POST'])
@login_required
@role_required('admin')
def cfg_alterar_perfil_usuario(user_id):
    nome = _nome_usuario(user_id)
    perfil_id = request.form.get('perfil_id', '')
    ok, _ = usuarios_service.alterar_perfil_usuario(user_id, perfil_id)
    if ok:
        log_evento('usuario_perfil_alterado', detalhes=f'{nome} → {perfil_id or "(sem perfil)"}',
                   entidade_tipo='usuario', entidade_id=user_id)
    return redirect(url_for('config.configuracoes', tab='usuarios', msg='perfil_atualizado'))


@usuarios_bp.route('/configuracoes/usuario/<user_id>/excluir', methods=['POST'])
@login_required
@role_required('admin')
def cfg_excluir_usuario(user_id):
    nome = _nome_usuario(user_id)
    ok, _ = usuarios_service.excluir_usuario(user_id, session['user_id'])
    if ok:
        log_evento('usuario_excluido', detalhes=nome, entidade_tipo='usuario', entidade_id=user_id)
    return redirect(url_for('config.configuracoes', tab='usuarios', msg='usuario_excluido'))
