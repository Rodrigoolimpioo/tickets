from flask import Blueprint, render_template, request, send_from_directory, session

from core import storage
from core.config import PASSWORD_MIN, UPLOADS_DIR
from core.security import hash_password, login_required, permission_required, verify_password

misc_bp = Blueprint('misc', __name__)


@misc_bp.route('/meu-perfil', methods=['GET', 'POST'])
@login_required
@permission_required('meu_perfil')
def meu_perfil():
    users   = storage.load_users()
    user    = next((u for u in users if u['id'] == session['user_id']), None)
    success = error = None

    if request.method == 'POST':
        senha_atual = request.form.get('senha_atual', '').strip()
        nova_senha  = request.form.get('nova_senha', '').strip()
        confirmar   = request.form.get('confirmar_senha', '').strip()

        if not verify_password(user['password'], senha_atual):
            error = 'Senha atual incorreta.'
        elif nova_senha != confirmar:
            error = 'As senhas não coincidem.'
        elif len(nova_senha) < PASSWORD_MIN:
            error = f'A nova senha deve ter pelo menos {PASSWORD_MIN} caracteres.'
        else:
            user['password'] = hash_password(nova_senha)
            storage.save_users(users)
            success = 'Senha alterada com sucesso!'

    return render_template('perfil.html', user=user, success=success, error=error)


@misc_bp.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(UPLOADS_DIR, filename)


@misc_bp.route('/logo')
def serve_logo():
    cfg = storage.load_config()
    logo = cfg.get('personalizacao', {}).get('logo_filename')
    if logo:
        return send_from_directory(UPLOADS_DIR, logo)
    return '', 404
