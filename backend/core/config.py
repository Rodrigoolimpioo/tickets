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

STATUS_LIST = ['Aberto', 'Em Andamento', 'Resolvido', 'Incubado']
STATUS_LIST_MANUTENCAO = ['Aberta', 'Em Andamento', 'Concluída', 'Cancelada']
ROLES_VALIDOS = {'admin', 'supervisor', 'funcionario'}
HEX_COLOR_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')
TIME_RE = re.compile(r'^(?:[01]\d|2[0-3]):[0-5]\d$')
PASSWORD_MIN = 6

# Limite da coluna TICKET_HISTORICO.ACAO (VARCHAR2(4000 CHAR)) — truncar
# aqui evita repetir o ORA-12899 que já derrubou a rota em produção quando
# alguém colou um comentário maior que o limite antigo de 500.
HISTORICO_ACAO_MAX = 4000

# Módulos do sistema que podem ser liberados/bloqueados por perfil de acesso.
# Parametrizável em tempo real via Configurações → Perfis (web) ou /api/perfis (API).
PERMISSOES = [
    ('dashboard',        'Dashboard',                      'fa-gauge-high'),
    ('abrir_ticket',     'Abrir Tickets',                  'fa-circle-plus'),
    ('acompanhamento',   'Acompanhamento de Tickets',      'fa-list-check'),
    ('ver_ticket',       'Visualizar Detalhes do Ticket',  'fa-eye'),
    ('atualizar_ticket', 'Atualizar Status do Ticket',     'fa-pen-to-square'),
    ('comentar_ticket',  'Comentar em Tickets',            'fa-comment'),
    ('manutencao_ver',        'Visualizar Manutenções',    'fa-screwdriver-wrench'),
    ('manutencao_gerenciar',  'Gerenciar Manutenções',      'fa-toolbox'),
    ('relatorios_ver',        'Relatórios',                 'fa-chart-column'),
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

# ── E-mail (fluxo de "esqueci minha senha") ──────────────────────────
SMTP_HOST = os.environ.get('SMTP_HOST')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
SMTP_USER = os.environ.get('SMTP_USER')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD')
SMTP_FROM = os.environ.get('SMTP_FROM') or SMTP_USER

# URL pública usada para montar o link de redefinição de senha no e-mail.
APP_BASE_URL = os.environ.get('APP_BASE_URL', 'http://localhost:5000')

RESET_TOKEN_EXP_MINUTES = int(os.environ.get('RESET_TOKEN_EXP_MINUTES', '30'))

# ── Manutenção de equipamentos ────────────────────────────────────────
# Taxonomia fornecida pelo cliente, semeada uma vez em EQUIPAMENTO_TIPOS
# (ver db/migrate.py). Sem tela de CRUD na v1 — só alimenta o <select> ao
# cadastrar um equipamento em Configurações → Equipamentos.
EQUIPAMENTO_TIPOS_PADRAO = {
    'Cocção e preparo': [
        'Fogão industrial', 'Forno industrial', 'Forno combinado', 'Forno de convecção',
        'Forno elétrico', 'Forno SpeedOver', 'Fritadeira elétrica', 'Fritadeira a gás',
        'Coifa', 'Exaustor', 'Micro-ondas', 'Panela de pressão industrial',
        'Caldeirão industrial', 'Máquina de cozinhar massas',
    ],
    'Refrigeração e congelamento': [
        'Câmara fria', 'Câmara de congelamento', 'Geladeira industrial',
        'Refrigerador vertical', 'Freezer horizontal', 'Freezer vertical',
        'Balcão refrigerado', 'Mesa refrigerada', 'Expositor refrigerado',
        'Máquina de gelo', 'Unidade condensadora', 'Evaporador',
    ],
    'Processamento de alimentos': [
        'Processador de alimentos', 'Multiprocessador industrial', 'Cutter',
        'Liquidificador industrial', 'Mixer industrial', 'Batedeira planetária',
        'Masseira', 'Cilindro de massas', 'Modeladora', 'Fatiador de frios',
        'Moedor de carne', 'Serra-fita', 'Amaciador de carne',
        'Descascador de legumes', 'Cortador de legumes', 'Espremedor de frutas',
    ],
    'Conservação e embalagem': [
        'Seladora', 'Seladora a vácuo', 'Máquina de embalagem a vácuo',
        'Termoformadora', 'Embaladora', 'Datador', 'Etiquetadora', 'Balança',
        'Balança de precisão', 'Balança de plataforma',
    ],
    'Lavagem e higienização': [
        'Máquina de lavar louças', 'Lava-louças industrial', 'Pia industrial',
        'Lavadora de utensílios', 'Esterilizador', 'Dosador de produtos químicos',
    ],
    'Apoio e armazenamento': [
        'Bancada de inox', 'Mesa de inox', 'Prateleira', 'Estante',
        'Carrinho de transporte', 'Carro plataforma', 'Carro térmico',
        'Caixa térmica', 'Armário de inox',
    ],
    'Equipamentos elétricos e infraestrutura': [
        'Ar-condicionado', 'Climatizador', 'Ventilador industrial', 'Compressor',
        "Bomba d'água", 'Gerador', 'Nobreak', 'Quadro elétrico',
    ],
}

# ── WhatsApp (notificação de andamento de ticket via wa-service) ─────
# Serviço interno próprio (whatsapp-web.js), repositório separado
# (github.com/JuanDiniz/wa-service). Roda na mesma VM, escutando só em
# 127.0.0.1 — nunca é exposto à internet. Substituiu o Z-API (trial
# expirado, inviável pago pro volume de mensagens do projeto).
WA_SERVICE_URL = os.environ.get('WA_SERVICE_URL', 'http://127.0.0.1:3000')
WA_SERVICE_API_KEY = os.environ.get('WA_SERVICE_API_KEY')
