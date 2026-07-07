from db.repositories import config_repository, tickets_repository, users_repository

from .config import ALLOWED_EXTENSIONS

# ─────────────────────────────────────────
#  USUÁRIOS / TICKETS (Oracle Autonomous Database)
# ─────────────────────────────────────────
#  Mesma assinatura pública de quando isso era JSON em disco — controllers
#  e services não sabem (nem precisam saber) que a persistência agora é
#  SQL. Toda a camada de acesso a dados vive em db/repositories/*.py.

def load_users():
    return users_repository.list_users()


def save_users(users):
    users_repository.save_users(users)


def load_tickets():
    return tickets_repository.list_tickets()


def save_tickets(tickets):
    tickets_repository.save_tickets(tickets)


# ─────────────────────────────────────────
#  CONFIGURAÇÃO / PERFIS DE ACESSO
# ─────────────────────────────────────────

def get_default_perfis():
    return [
        {
            'id': 'perfil-supervisor',
            'nome': 'Supervisor',
            'descricao': 'Acompanha tickets e atualiza status',
            'permissoes': ['dashboard', 'acompanhamento', 'ver_ticket', 'atualizar_ticket', 'comentar_ticket', 'meu_perfil'],
            'padrao': True,
        },
        {
            'id': 'perfil-funcionario',
            'nome': 'Funcionário',
            'descricao': 'Abre e acompanha seus próprios tickets',
            'permissoes': ['dashboard', 'abrir_ticket', 'acompanhamento', 'ver_ticket', 'comentar_ticket', 'meu_perfil'],
            'padrao': True,
        },
    ]


def get_default_config():
    return {
        'ip_control': {
            'enabled': False,
            'ips': ['127.0.0.1', '::1']
        },
        'horario_control': {
            'enabled': False,
            'horarios': [
                {'dia': 0, 'nome': 'Segunda-feira',  'inicio': '08:00', 'fim': '18:00', 'ativo': True},
                {'dia': 1, 'nome': 'Terça-feira',    'inicio': '08:00', 'fim': '18:00', 'ativo': True},
                {'dia': 2, 'nome': 'Quarta-feira',   'inicio': '08:00', 'fim': '18:00', 'ativo': True},
                {'dia': 3, 'nome': 'Quinta-feira',   'inicio': '08:00', 'fim': '18:00', 'ativo': True},
                {'dia': 4, 'nome': 'Sexta-feira',    'inicio': '08:00', 'fim': '18:00', 'ativo': True},
                {'dia': 5, 'nome': 'Sábado',         'inicio': '08:00', 'fim': '12:00', 'ativo': False},
                {'dia': 6, 'nome': 'Domingo',        'inicio': '00:00', 'fim': '00:00', 'ativo': False},
            ]
        },
        'sistemas': ['Teknisa', 'Kdápio (Callcenter)', 'Lumia', 'iFood'],
        'personalizacao': {
            'cor_botao':          '#111111',
            'cor_botao_light':    '#f0f0f0',
            'cor_fundo':          '#f1f5f9',
            'cor_sidebar':        '#0f172a',
            'cor_sidebar_ativo':  '#111111',
            'cor_texto':          '#0f172a',
            'cor_sidebar_texto':  '#94a3b8',
            'nome_sistema':       'Tickets',
            'logo_filename':      None,
        },
        'perfis': get_default_perfis(),
    }


def load_config():
    return config_repository.get_config()


def save_config(cfg):
    config_repository.save_config(cfg)


def get_sistemas():
    return load_config().get('sistemas', ['Teknisa', 'Kdápio (Callcenter)', 'Lumia', 'iFood'])


def get_next_ticket_number():
    return tickets_repository.get_next_ticket_number()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_role_label(role):
    return {'admin': 'Administrador', 'supervisor': 'Supervisor', 'funcionario': 'Funcionário'}.get(role, role)
