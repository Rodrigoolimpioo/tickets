import threading
import time

from db.repositories import config_repository, tickets_repository, users_repository

from .config import ALLOWED_EXTENSIONS

# Cache em memória da config — evita abrir conexão Oracle em cada requisição.
# TTL de 60s: mudanças pelo admin aparecem em até 1 minuto sem cache.
# save_config() invalida imediatamente.
_cfg_cache: dict | None = None
_cfg_cache_at: float = 0.0
_cfg_cache_ttl: float = 60.0
_cfg_lock = threading.Lock()

_usr_cache: list | None = None
_usr_cache_at: float = 0.0
_usr_cache_ttl: float = 30.0
_usr_lock = threading.Lock()

_stats_cache: dict | None = None
_stats_cache_at: float = 0.0
_stats_cache_ttl: float = 15.0
_stats_lock = threading.Lock()

# ─────────────────────────────────────────
#  USUÁRIOS / TICKETS (Oracle Autonomous Database)
# ─────────────────────────────────────────
#  Mesma assinatura pública de quando isso era JSON em disco — controllers
#  e services não sabem (nem precisam saber) que a persistência agora é
#  SQL. Toda a camada de acesso a dados vive em db/repositories/*.py.

def load_users():
    global _usr_cache, _usr_cache_at
    if _usr_cache is not None and (time.monotonic() - _usr_cache_at) < _usr_cache_ttl:
        return _usr_cache
    with _usr_lock:
        if _usr_cache is not None and (time.monotonic() - _usr_cache_at) < _usr_cache_ttl:
            return _usr_cache
        _usr_cache = users_repository.list_users()
        _usr_cache_at = time.monotonic()
        return _usr_cache


def save_users(users):
    global _usr_cache, _usr_cache_at
    users_repository.save_users(users)
    with _usr_lock:
        _usr_cache = None
        _usr_cache_at = 0.0


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
    global _cfg_cache, _cfg_cache_at
    if _cfg_cache is not None and (time.monotonic() - _cfg_cache_at) < _cfg_cache_ttl:
        return _cfg_cache
    with _cfg_lock:
        if _cfg_cache is not None and (time.monotonic() - _cfg_cache_at) < _cfg_cache_ttl:
            return _cfg_cache
        _cfg_cache = config_repository.get_config()
        _cfg_cache_at = time.monotonic()
        return _cfg_cache


def save_config(cfg):
    global _cfg_cache, _cfg_cache_at
    config_repository.save_config(cfg)
    with _cfg_lock:
        _cfg_cache = None
        _cfg_cache_at = 0.0


def get_sistemas():
    return load_config().get('sistemas', ['Teknisa', 'Kdápio (Callcenter)', 'Lumia', 'iFood'])


def get_ticket_stats():
    global _stats_cache, _stats_cache_at
    if _stats_cache is not None and (time.monotonic() - _stats_cache_at) < _stats_cache_ttl:
        return _stats_cache
    with _stats_lock:
        if _stats_cache is not None and (time.monotonic() - _stats_cache_at) < _stats_cache_ttl:
            return _stats_cache
        _stats_cache = tickets_repository.get_ticket_stats()
        _stats_cache_at = time.monotonic()
        return _stats_cache


def get_next_ticket_number():
    return tickets_repository.get_next_ticket_number()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_role_label(role):
    return {'admin': 'Administrador', 'supervisor': 'Supervisor', 'funcionario': 'Funcionário'}.get(role, role)
