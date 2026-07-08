"""Cria o schema (se ainda não existir) e semeia os dados padrão (perfis,
config, usuários) na primeira execução. Idempotente: pode ser rodado a
cada start do app sem duplicar nada — é o equivalente, para o Oracle, do
antigo `init_data()` que criava os arquivos users.json/tickets.json/config.json
na primeira vez.

Uso: `python -m db.migrate` (a partir de backend/), ou importado por app.py.
"""
import logging

import oracledb

from core.security import hash_password
from core.storage import get_default_config, get_default_perfis
from .connection import get_cursor

logger = logging.getLogger(__name__)

_ORA_NAME_ALREADY_USED = 955  # ORA-00955: name is already used by an existing object

_DDL_STATEMENTS = [
    """
    CREATE TABLE PERFIS (
        ID          VARCHAR2(36)  PRIMARY KEY,
        NOME        VARCHAR2(200) NOT NULL,
        DESCRICAO   VARCHAR2(500),
        PADRAO      NUMBER(1)     DEFAULT 0 NOT NULL
    )
    """,
    """
    CREATE TABLE PERFIL_PERMISSOES (
        PERFIL_ID   VARCHAR2(36) NOT NULL REFERENCES PERFIS(ID) ON DELETE CASCADE,
        PERMISSAO   VARCHAR2(50) NOT NULL,
        CONSTRAINT PK_PERFIL_PERMISSOES PRIMARY KEY (PERFIL_ID, PERMISSAO)
    )
    """,
    """
    CREATE TABLE USERS (
        ID          VARCHAR2(36)  PRIMARY KEY,
        USERNAME    VARCHAR2(100) NOT NULL UNIQUE,
        PASSWORD    VARCHAR2(255) NOT NULL,
        NAME        VARCHAR2(200) NOT NULL,
        ROLE        VARCHAR2(20)  NOT NULL,
        EMAIL       VARCHAR2(200),
        ATIVO       NUMBER(1)     DEFAULT 1 NOT NULL,
        PERFIL_ID   VARCHAR2(36)
    )
    """,
    """
    CREATE TABLE TICKETS (
        ID                     VARCHAR2(36)  PRIMARY KEY,
        NUMERO                 VARCHAR2(20)  NOT NULL UNIQUE,
        NOME                   VARCHAR2(200) NOT NULL,
        OCORRENCIA             VARCHAR2(4000) NOT NULL,
        SISTEMA                VARCHAR2(100) NOT NULL,
        ARQUIVO_FILENAME       VARCHAR2(255),
        ARQUIVO_ORIGINAL_NAME  VARCHAR2(255),
        ARQUIVO_TIPO           VARCHAR2(20),
        DATA_CRIACAO           TIMESTAMP     NOT NULL,
        STATUS                 VARCHAR2(30)  NOT NULL,
        CRIADO_POR             VARCHAR2(200) NOT NULL,
        CRIADO_POR_ID          VARCHAR2(36)  NOT NULL
    )
    """,
    """
    CREATE TABLE TICKET_HISTORICO (
        ID         NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        TICKET_ID  VARCHAR2(36)  NOT NULL REFERENCES TICKETS(ID) ON DELETE CASCADE,
        ACAO       VARCHAR2(500) NOT NULL,
        POR        VARCHAR2(200) NOT NULL,
        DATA       TIMESTAMP     NOT NULL
    )
    """,
    """
    CREATE TABLE CONFIG_GERAL (
        ID                       NUMBER(1)     PRIMARY KEY,
        IP_CONTROL_ENABLED       NUMBER(1)     DEFAULT 0 NOT NULL,
        HORARIO_CONTROL_ENABLED  NUMBER(1)     DEFAULT 0 NOT NULL,
        NOME_SISTEMA             VARCHAR2(200) DEFAULT 'Tickets' NOT NULL,
        LOGO_FILENAME            VARCHAR2(255),
        COR_BOTAO                VARCHAR2(7)   DEFAULT '#111111' NOT NULL,
        COR_BOTAO_LIGHT          VARCHAR2(7)   DEFAULT '#f0f0f0' NOT NULL,
        COR_FUNDO                VARCHAR2(7)   DEFAULT '#f1f5f9' NOT NULL,
        COR_SIDEBAR              VARCHAR2(7)   DEFAULT '#0f172a' NOT NULL,
        COR_SIDEBAR_ATIVO        VARCHAR2(7)   DEFAULT '#111111' NOT NULL,
        COR_TEXTO                VARCHAR2(7)   DEFAULT '#0f172a' NOT NULL,
        COR_SIDEBAR_TEXTO        VARCHAR2(7)   DEFAULT '#94a3b8' NOT NULL
    )
    """,
    "CREATE TABLE IPS_PERMITIDOS (IP VARCHAR2(45) PRIMARY KEY)",
    """
    CREATE TABLE HORARIOS_CONTROLE (
        DIA     NUMBER(1)    PRIMARY KEY,
        NOME    VARCHAR2(30) NOT NULL,
        INICIO  VARCHAR2(5)  NOT NULL,
        FIM     VARCHAR2(5)  NOT NULL,
        ATIVO   NUMBER(1)    DEFAULT 0 NOT NULL
    )
    """,
    "CREATE TABLE SISTEMAS (NOME VARCHAR2(100) PRIMARY KEY)",
    """
    CREATE TABLE LOGS_AUDITORIA (
        ID            NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        DATA_HORA     TIMESTAMP     NOT NULL,
        USUARIO_ID    VARCHAR2(36),
        USUARIO_NOME  VARCHAR2(200),
        ACAO          VARCHAR2(50)  NOT NULL,
        DETALHES      VARCHAR2(1000),
        IP            VARCHAR2(45),
        ENTIDADE_TIPO VARCHAR2(30),
        ENTIDADE_ID   VARCHAR2(36)
    )
    """,
    "CREATE INDEX IDX_LOGS_DATA_HORA ON LOGS_AUDITORIA (DATA_HORA)",
    "CREATE INDEX IDX_LOGS_ACAO_IP ON LOGS_AUDITORIA (ACAO, IP, DATA_HORA)",
    """
    CREATE TABLE PASSWORD_RESET_TOKENS (
        TOKEN      VARCHAR2(64)  PRIMARY KEY,
        USER_ID    VARCHAR2(36)  NOT NULL,
        CRIADO_EM  TIMESTAMP     NOT NULL,
        EXPIRA_EM  TIMESTAMP     NOT NULL,
        USADO      NUMBER(1)     DEFAULT 0 NOT NULL
    )
    """,
    "CREATE INDEX IDX_RESET_USER_ID ON PASSWORD_RESET_TOKENS (USER_ID)",
]


def _create_tables(cursor):
    for ddl in _DDL_STATEMENTS:
        try:
            cursor.execute(ddl)
        except oracledb.DatabaseError as exc:
            (error,) = exc.args
            if getattr(error, 'code', None) == _ORA_NAME_ALREADY_USED:
                continue
            raise


def _seed_perfis(cursor):
    cursor.execute("SELECT COUNT(*) FROM PERFIS")
    if cursor.fetchone()[0] > 0:
        return
    for perfil in get_default_perfis():
        cursor.execute(
            "INSERT INTO PERFIS (ID, NOME, DESCRICAO, PADRAO) VALUES (:id, :nome, :descricao, :padrao)",
            id=perfil['id'], nome=perfil['nome'],
            descricao=perfil.get('descricao') or None,
            padrao=1 if perfil.get('padrao') else 0,
        )
        for permissao in perfil.get('permissoes', []):
            cursor.execute(
                "INSERT INTO PERFIL_PERMISSOES (PERFIL_ID, PERMISSAO) VALUES (:perfil_id, :permissao)",
                perfil_id=perfil['id'], permissao=permissao,
            )
    logger.info('Perfis padrão semeados.')


def _seed_config(cursor):
    cursor.execute("SELECT COUNT(*) FROM CONFIG_GERAL")
    if cursor.fetchone()[0] > 0:
        return
    defaults = get_default_config()
    pers = defaults['personalizacao']
    cursor.execute(
        """
        INSERT INTO CONFIG_GERAL (
            ID, IP_CONTROL_ENABLED, HORARIO_CONTROL_ENABLED, NOME_SISTEMA,
            LOGO_FILENAME, COR_BOTAO, COR_BOTAO_LIGHT, COR_FUNDO, COR_SIDEBAR,
            COR_SIDEBAR_ATIVO, COR_TEXTO, COR_SIDEBAR_TEXTO
        ) VALUES (
            1, :ip_enabled, :horario_enabled, :nome_sistema,
            :logo, :cor_botao, :cor_botao_light, :cor_fundo, :cor_sidebar,
            :cor_sidebar_ativo, :cor_texto, :cor_sidebar_texto
        )
        """,
        ip_enabled=1 if defaults['ip_control']['enabled'] else 0,
        horario_enabled=1 if defaults['horario_control']['enabled'] else 0,
        nome_sistema=pers['nome_sistema'], logo=pers.get('logo_filename'),
        cor_botao=pers['cor_botao'], cor_botao_light=pers['cor_botao_light'],
        cor_fundo=pers['cor_fundo'], cor_sidebar=pers['cor_sidebar'],
        cor_sidebar_ativo=pers['cor_sidebar_ativo'], cor_texto=pers['cor_texto'],
        cor_sidebar_texto=pers['cor_sidebar_texto'],
    )
    for ip in defaults['ip_control']['ips']:
        cursor.execute("INSERT INTO IPS_PERMITIDOS (IP) VALUES (:ip)", ip=ip)
    for h in defaults['horario_control']['horarios']:
        cursor.execute(
            "INSERT INTO HORARIOS_CONTROLE (DIA, NOME, INICIO, FIM, ATIVO) "
            "VALUES (:dia, :nome, :inicio, :fim, :ativo)",
            dia=h['dia'], nome=h['nome'], inicio=h['inicio'], fim=h['fim'],
            ativo=1 if h['ativo'] else 0,
        )
    for sistema in defaults['sistemas']:
        cursor.execute("INSERT INTO SISTEMAS (NOME) VALUES (:nome)", nome=sistema)
    logger.info('Configuração padrão semeada.')


def _seed_users(cursor):
    cursor.execute("SELECT COUNT(*) FROM USERS")
    if cursor.fetchone()[0] > 0:
        return
    usuarios_padrao = [
        {'id': '1', 'username': 'admin', 'password': hash_password('admin123'),
         'name': 'Administrador', 'role': 'admin', 'email': 'admin@tickets.local',
         'ativo': 1, 'perfil_id': None},
        {'id': '2', 'username': 'supervisor', 'password': hash_password('super123'),
         'name': 'Supervisor', 'role': 'supervisor', 'email': 'supervisor@tickets.local',
         'ativo': 1, 'perfil_id': 'perfil-supervisor'},
        {'id': '3', 'username': 'funcionario', 'password': hash_password('func123'),
         'name': 'Funcionário', 'role': 'funcionario', 'email': 'funcionario@tickets.local',
         'ativo': 1, 'perfil_id': 'perfil-funcionario'},
    ]
    for u in usuarios_padrao:
        cursor.execute(
            "INSERT INTO USERS (ID, USERNAME, PASSWORD, NAME, ROLE, EMAIL, ATIVO, PERFIL_ID) "
            "VALUES (:id, :username, :password, :name, :role, :email, :ativo, :perfil_id)",
            **u,
        )
    logger.info('Usuários padrão semeados (admin/supervisor/funcionario).')


def run():
    """Idempotente: cria as tabelas que ainda não existem e semeia os
    dados padrão apenas se as tabelas estiverem vazias."""
    with get_cursor(commit=True) as cursor:
        _create_tables(cursor)
        _seed_perfis(cursor)
        _seed_config(cursor)
        _seed_users(cursor)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run()
    print('Schema Oracle criado/verificado e dados padrão semeados com sucesso.')
