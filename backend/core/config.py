import os
import re
import secrets
from datetime import timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(os.path.dirname(BASE_DIR), 'frontend')


def _load_dotenv():
    env_file = os.path.join(BASE_DIR, '.env')
    if not os.path.exists(env_file):
        return
    with open(env_file, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_dotenv()

SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)

# Chave/algoritmo usados para assinar os tokens JWT emitidos pela API.
# Por padrão reaproveita a SECRET_KEY para não exigir configuração extra,
# mas pode ser sobrescrita via env para rotacionar tokens sem derrubar sessões web.
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or SECRET_KEY
JWT_ALGORITHM = 'HS256'
JWT_EXP_HOURS = int(os.environ.get('JWT_EXP_HOURS', '8'))

SESSION_LIFETIME = timedelta(hours=8)

UPLOADS_DIR = os.path.join(BASE_DIR, 'uploads')

# Oracle Autonomous Database (modo thin do oracledb — sem Instant Client)
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_DSN = os.environ.get('DB_DSN')
DB_WALLET_DIR = os.environ.get('DB_WALLET_DIR')
DB_WALLET_PASSWORD = os.environ.get('DB_WALLET_PASSWORD')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'mp4', 'avi', 'mov', 'webm', 'mkv'}
LOGO_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_CONTENT_LENGTH = 100 * 1024 * 1024

STATUS_LIST = ['Aberto', 'Em Andamento', 'Resolvido', 'Fechado']
ROLES_VALIDOS = {'admin', 'supervisor', 'funcionario'}
HEX_COLOR_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')
TIME_RE = re.compile(r'^(?:[01]\d|2[0-3]):[0-5]\d$')
PASSWORD_MIN = 8

# Módulos do sistema que podem ser liberados/bloqueados por perfil de acesso.
# Parametrizável em tempo real via Configurações → Perfis (web) ou /api/perfis (API).
PERMISSOES = [
    ('dashboard',        'Dashboard',                      'fa-gauge-high'),
    ('abrir_ticket',     'Abrir Tickets',                  'fa-circle-plus'),
    ('acompanhamento',   'Acompanhamento de Tickets',      'fa-list-check'),
    ('ver_ticket',       'Visualizar Detalhes do Ticket',  'fa-eye'),
    ('atualizar_ticket', 'Atualizar Status do Ticket',     'fa-pen-to-square'),
    ('comentar_ticket',  'Comentar em Tickets',            'fa-comment'),
    ('meu_perfil',       'Meu Perfil',                     'fa-user'),
]
PERMISSOES_IDS = [p[0] for p in PERMISSOES]

DIAS_SEMANA = [
    {'dia': 0, 'nome': 'Segunda-feira'},
    {'dia': 1, 'nome': 'Terça-feira'},
    {'dia': 2, 'nome': 'Quarta-feira'},
    {'dia': 3, 'nome': 'Quinta-feira'},
    {'dia': 4, 'nome': 'Sexta-feira'},
    {'dia': 5, 'nome': 'Sábado'},
    {'dia': 6, 'nome': 'Domingo'},
]

_LOGIN_MAX = 5
_LOGIN_LOCKOUT_MIN = 15

# Kill switch temporário via env — desliga o rate limit de tentativas de
# login sem precisar mexer em código/redeploy. Reative colocando
# LOGIN_RATE_LIMIT_ENABLED=true (ou removendo a variável) no .env.
LOGIN_RATE_LIMIT_ENABLED = os.environ.get('LOGIN_RATE_LIMIT_ENABLED', 'true').strip().lower() != 'false'
