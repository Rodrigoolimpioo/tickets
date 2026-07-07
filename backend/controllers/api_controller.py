"""Controller da API JSON, autenticada por token JWT (Bearer).

Existe ao lado das telas web (que usam sessão/cookie) para permitir que
outros clientes — um frontend SPA, um app mobile, integrações externas —
se autentiquem e consumam o mesmo modelo de permissões por perfil
(Admin / Supervisor / Funcionário ou perfis customizados), sem depender
de cookies de sessão.
"""
from flask import Blueprint, g, jsonify, request

from core import storage
from core.config import PERMISSOES, ROLES_VALIDOS, STATUS_LIST
from core.security import (
    api_permission_required, api_role_required, generate_token,
    jwt_required, rate_limit_exceeded, register_failed_login, verify_password,
)
from core.services import perfis_service, usuarios_service
from core.time_utils import get_client_ip

api_bp = Blueprint('api', __name__, url_prefix='/api')


# ─────────────────────────────────────────
#  AUTENTICAÇÃO — geração e inspeção do token
# ─────────────────────────────────────────

@api_bp.route('/auth/token', methods=['POST'])
def auth_token():
    """Gera um JWT com claims de identidade (role, permissoes do perfil,
    perfil_id). Aceita JSON ou form-urlencoded: {username, password}."""
    data = request.get_json(silent=True) or request.form
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    client_ip = get_client_ip()
    if rate_limit_exceeded(client_ip):
        return jsonify({'error': 'muitas_tentativas'}), 429

    users = storage.load_users()
    user = next((u for u in users
                 if u['username'] == username and u.get('ativo', True)), None)

    if not user or not verify_password(user['password'], password):
        register_failed_login(client_ip)
        return jsonify({'error': 'credenciais_invalidas'}), 401

    token_data = generate_token(user)
    return jsonify({
        'access_token': token_data['access_token'],
        'token_type': token_data['token_type'],
        'expires_in': token_data['expires_in'],
        'user': {
            'id': user['id'],
            'username': user['username'],
            'name': user['name'],
            'role': user['role'],
            'perfil_id': user.get('perfil_id'),
            'permissoes': token_data['claims']['permissoes'],
        },
    })


@api_bp.route('/auth/me')
@jwt_required
def auth_me():
    claims = g.jwt_claims
    return jsonify({
        'id': claims.get('sub'),
        'username': claims.get('username'),
        'name': claims.get('name'),
        'role': claims.get('role'),
        'perfil_id': claims.get('perfil_id'),
        'permissoes': claims.get('permissoes', []),
    })


# ─────────────────────────────────────────
#  MÓDULOS / PERMISSÕES — parametrização
# ─────────────────────────────────────────

@api_bp.route('/modulos')
@jwt_required
def modulos():
    """Lista os módulos do sistema e se o token atual tem acesso a cada
    um — usado pelo frontend para montar menus/telas dinamicamente."""
    claims = g.jwt_claims
    liberados = set(claims.get('permissoes', []))
    return jsonify([
        {
            'id': modulo_id,
            'nome': nome,
            'icone': icone,
            'liberado': claims.get('role') == 'admin' or modulo_id in liberados,
        }
        for modulo_id, nome, icone in PERMISSOES
    ])


@api_bp.route('/stats')
@jwt_required
@api_permission_required('dashboard')
def stats():
    claims = g.jwt_claims
    tickets = storage.load_tickets()
    if claims.get('role') == 'funcionario':
        tickets = [t for t in tickets if t.get('criado_por_id') == claims.get('sub')]
    return jsonify({s: sum(1 for t in tickets if t['status'] == s) for s in STATUS_LIST} |
                    {'total': len(tickets)})


# ─────────────────────────────────────────
#  PERFIS DE ACESSO — parametrizável a qualquer momento
# ─────────────────────────────────────────

@api_bp.route('/perfis', methods=['GET'])
@jwt_required
@api_role_required('admin')
def api_listar_perfis():
    return jsonify(perfis_service.listar_perfis())


@api_bp.route('/perfis', methods=['POST'])
@jwt_required
@api_role_required('admin')
def api_criar_perfil():
    data = request.get_json(silent=True) or {}
    ok, err, perfil = perfis_service.criar_perfil(
        nome=data.get('nome', ''),
        descricao=data.get('descricao', ''),
        permissoes=data.get('permissoes', []),
    )
    if not ok:
        return jsonify({'error': err}), 400
    return jsonify(perfil), 201


@api_bp.route('/perfis/<perfil_id>', methods=['PUT'])
@jwt_required
@api_role_required('admin')
def api_atualizar_perfil(perfil_id):
    data = request.get_json(silent=True) or {}
    ok, err = perfis_service.atualizar_perfil(
        perfil_id,
        nome=data.get('nome', ''),
        descricao=data.get('descricao', ''),
        permissoes=data.get('permissoes', []),
    )
    if not ok:
        return jsonify({'error': err}), 400
    return jsonify(perfis_service.obter_perfil(perfil_id))


@api_bp.route('/perfis/<perfil_id>', methods=['DELETE'])
@jwt_required
@api_role_required('admin')
def api_excluir_perfil(perfil_id):
    ok, err = perfis_service.excluir_perfil(perfil_id)
    if not ok:
        return jsonify({'error': err}), 400
    return '', 204


# ─────────────────────────────────────────
#  USUÁRIOS — criação/edição de acessos
# ─────────────────────────────────────────

@api_bp.route('/usuarios', methods=['GET'])
@jwt_required
@api_role_required('admin')
def api_listar_usuarios():
    return jsonify(usuarios_service.listar_usuarios())


@api_bp.route('/usuarios', methods=['POST'])
@jwt_required
@api_role_required('admin')
def api_criar_usuario():
    data = request.get_json(silent=True) or {}
    role = data.get('role', 'funcionario')
    if role not in ROLES_VALIDOS:
        return jsonify({'error': 'role_invalido'}), 400
    ok, err, user = usuarios_service.criar_usuario(
        username=data.get('username', ''),
        password=data.get('password', ''),
        name=data.get('name', ''),
        role=role,
        email=data.get('email', ''),
        perfil_id=data.get('perfil_id'),
    )
    if not ok:
        return jsonify({'error': err}), 400
    return jsonify(user), 201


@api_bp.route('/usuarios/<user_id>/toggle', methods=['POST'])
@jwt_required
@api_role_required('admin')
def api_toggle_usuario(user_id):
    ok, err = usuarios_service.toggle_usuario(user_id, g.jwt_claims.get('sub'))
    if not ok:
        return jsonify({'error': err}), 400
    return '', 204


@api_bp.route('/usuarios/<user_id>/senha', methods=['POST'])
@jwt_required
@api_role_required('admin')
def api_alterar_senha(user_id):
    data = request.get_json(silent=True) or {}
    ok, err = usuarios_service.alterar_senha(user_id, data.get('nova_senha', ''))
    if not ok:
        return jsonify({'error': err}), 400
    return '', 204


@api_bp.route('/usuarios/<user_id>/perfil', methods=['POST'])
@jwt_required
@api_role_required('admin')
def api_alterar_perfil_usuario(user_id):
    data = request.get_json(silent=True) or {}
    ok, err = usuarios_service.alterar_perfil_usuario(user_id, data.get('perfil_id'))
    if not ok:
        return jsonify({'error': err}), 400
    return '', 204


@api_bp.route('/usuarios/<user_id>', methods=['DELETE'])
@jwt_required
@api_role_required('admin')
def api_excluir_usuario(user_id):
    ok, err = usuarios_service.excluir_usuario(user_id, g.jwt_claims.get('sub'))
    if not ok:
        return jsonify({'error': err}), 400
    return '', 204
