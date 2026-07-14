-- Schema do Sistema Tickets no Oracle Autonomous Database.
-- Identificadores em maiúsculas, sem aspas duplas (evita problemas de
-- case-sensitivity do Oracle). Aplicado automaticamente e de forma
-- idempotente por `db/migrate.py` — este arquivo serve como referência
-- para execução manual (SQL*Plus, SQLcl, etc.) se preferir.

CREATE TABLE PERFIS (
    ID          VARCHAR2(36)  PRIMARY KEY,
    NOME        VARCHAR2(200) NOT NULL,
    DESCRICAO   VARCHAR2(500),
    PADRAO      NUMBER(1)     DEFAULT 0 NOT NULL
);

CREATE TABLE PERFIL_PERMISSOES (
    PERFIL_ID   VARCHAR2(36) NOT NULL REFERENCES PERFIS(ID) ON DELETE CASCADE,
    PERMISSAO   VARCHAR2(50) NOT NULL,
    CONSTRAINT PK_PERFIL_PERMISSOES PRIMARY KEY (PERFIL_ID, PERMISSAO)
);

CREATE TABLE USERS (
    ID          VARCHAR2(36)  PRIMARY KEY,
    USERNAME    VARCHAR2(100) NOT NULL UNIQUE,
    PASSWORD    VARCHAR2(255) NOT NULL,
    NAME        VARCHAR2(200) NOT NULL,
    ROLE        VARCHAR2(20)  NOT NULL,
    EMAIL       VARCHAR2(200),
    TELEFONE    VARCHAR2(20),
    ATIVO       NUMBER(1)     DEFAULT 1 NOT NULL,
    -- Sem FK para PERFIS: um perfil pode ser excluído e deixar usuários
    -- com perfil_id "órfão" — nesse caso o sistema cai no fallback por role
    -- (ver core/security.get_user_permissoes), igual ao comportamento antigo em JSON.
    PERFIL_ID   VARCHAR2(36)
);

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
    -- Sem FK para USERS: excluir um usuário não deve exigir excluir seus
    -- tickets (mesmo comportamento do JSON original).
    CRIADO_POR_ID          VARCHAR2(36)  NOT NULL
);

CREATE TABLE TICKET_HISTORICO (
    ID                    NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    TICKET_ID             VARCHAR2(36)  NOT NULL REFERENCES TICKETS(ID) ON DELETE CASCADE,
    ACAO                  VARCHAR2(500) NOT NULL,
    POR                   VARCHAR2(200) NOT NULL,
    DATA                  TIMESTAMP     NOT NULL,
    ARQUIVO_FILENAME      VARCHAR2(500),
    ARQUIVO_ORIGINAL_NAME VARCHAR2(500)
);

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
    COR_SIDEBAR_TEXTO        VARCHAR2(7)   DEFAULT '#94a3b8' NOT NULL,
    WHATSAPP_ENABLED         NUMBER(1)     DEFAULT 0 NOT NULL
);

CREATE TABLE IPS_PERMITIDOS (
    IP  VARCHAR2(45) PRIMARY KEY
);

-- Um toggle por status de ticket (ver core/config.STATUS_LIST) definindo
-- se aquela transição dispara notificação de WhatsApp, com uma mensagem
-- customizável por status (aceita placeholders — ver whatsapp_service.py).
-- MENSAGEM nula/vazia usa o texto padrão gerado pelo sistema.
CREATE TABLE WHATSAPP_STATUS_CONFIG (
    STATUS    VARCHAR2(30)   PRIMARY KEY,
    ATIVO     NUMBER(1)      DEFAULT 0 NOT NULL,
    MENSAGEM  VARCHAR2(1000)
);

CREATE TABLE HORARIOS_CONTROLE (
    DIA     NUMBER(1)    PRIMARY KEY,
    NOME    VARCHAR2(30) NOT NULL,
    INICIO  VARCHAR2(5)  NOT NULL,
    FIM     VARCHAR2(5)  NOT NULL,
    ATIVO   NUMBER(1)    DEFAULT 0 NOT NULL
);

CREATE TABLE SISTEMAS (
    NOME VARCHAR2(100) PRIMARY KEY
);

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
);
CREATE INDEX IDX_LOGS_DATA_HORA ON LOGS_AUDITORIA (DATA_HORA);
CREATE INDEX IDX_LOGS_ACAO_IP   ON LOGS_AUDITORIA (ACAO, IP, DATA_HORA);

CREATE TABLE PASSWORD_RESET_TOKENS (
    TOKEN      VARCHAR2(64)  PRIMARY KEY,
    USER_ID    VARCHAR2(36)  NOT NULL,
    CRIADO_EM  TIMESTAMP     NOT NULL,
    EXPIRA_EM  TIMESTAMP     NOT NULL,
    USADO      NUMBER(1)     DEFAULT 0 NOT NULL
);
CREATE INDEX IDX_RESET_USER_ID ON PASSWORD_RESET_TOKENS (USER_ID);
