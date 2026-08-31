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
    UNIDADE                VARCHAR2(100),
    ARQUIVO_FILENAME       VARCHAR2(255),
    ARQUIVO_ORIGINAL_NAME  VARCHAR2(255),
    ARQUIVO_TIPO           VARCHAR2(20),
    DATA_CRIACAO           TIMESTAMP     NOT NULL,
    STATUS                 VARCHAR2(30)  NOT NULL,
    CRIADO_POR             VARCHAR2(200) NOT NULL,
    -- Sem FK para USERS: excluir um usuário não deve exigir excluir seus
    -- tickets (mesmo comportamento do JSON original).
    CRIADO_POR_ID          VARCHAR2(36)  NOT NULL,
    -- Preenchida quando o status sai do fluxo ativo (Resolvido/Incubado) e
    -- limpa se reabrir — usada no relatório de tickets (tempo de fechamento).
    DATA_FECHAMENTO        TIMESTAMP
);

CREATE TABLE TICKET_HISTORICO (
    ID                    NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    TICKET_ID             VARCHAR2(36)  NOT NULL REFERENCES TICKETS(ID) ON DELETE CASCADE,
    ACAO                  VARCHAR2(4000 CHAR) NOT NULL,
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
    IP    VARCHAR2(45)  PRIMARY KEY,
    -- Identificação opcional (ex.: "Escritório", "Casa do Rodrigo") só
    -- pra facilitar reconhecer a lista depois — não afeta a checagem.
    NOME  VARCHAR2(100)
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

CREATE TABLE UNIDADES (
    NOME VARCHAR2(100) PRIMARY KEY
);

-- Cadastro prévio de técnicos externos — mesmo padrão sem FK de
-- SISTEMAS/UNIDADES, usado como opções padrão no campo "Técnico" da
-- manutenção (ver MANUTENCOES.TECNICO abaixo).
CREATE TABLE TECNICOS (
    NOME VARCHAR2(200) PRIMARY KEY
);

-- Taxonomia fixa de tipos de equipamento (semeada em migrate.py a partir
-- de core/config.EQUIPAMENTO_TIPOS_PADRAO) — alimenta o <select> ao
-- cadastrar um equipamento em Configurações → Equipamentos.
CREATE TABLE EQUIPAMENTO_TIPOS (
    CATEGORIA VARCHAR2(100) NOT NULL,
    NOME      VARCHAR2(150) NOT NULL,
    CONSTRAINT PK_EQUIPAMENTO_TIPOS PRIMARY KEY (CATEGORIA, NOME)
);

CREATE TABLE EQUIPAMENTOS (
    ID            VARCHAR2(36)  PRIMARY KEY,
    NOME          VARCHAR2(200) NOT NULL,
    CATEGORIA     VARCHAR2(100),
    TIPO          VARCHAR2(150),
    -- Sem FK pra UNIDADES, mesmo padrão de SISTEMAS/TICKETS.
    UNIDADE       VARCHAR2(100) NOT NULL,
    NUMERO_SERIE  VARCHAR2(100),
    ATIVO         NUMBER(1)     DEFAULT 1 NOT NULL,
    DATA_CADASTRO TIMESTAMP     NOT NULL
);

CREATE TABLE MANUTENCOES (
    ID                  VARCHAR2(36)   PRIMARY KEY,
    NUMERO              VARCHAR2(20)   NOT NULL UNIQUE,
    -- Sem FK pra EQUIPAMENTOS: mesmo racional de TICKETS não ter FK pra
    -- USERS — excluir um equipamento não deve exigir excluir seu histórico
    -- de manutenções.
    EQUIPAMENTO_ID      VARCHAR2(36)   NOT NULL,
    UNIDADE             VARCHAR2(100)  NOT NULL,
    RESPONSAVEL_ID      VARCHAR2(36),
    RESPONSAVEL_NOME    VARCHAR2(200),
    DESCRICAO           VARCHAR2(4000 CHAR) NOT NULL,
    STATUS              VARCHAR2(30)   NOT NULL,
    DATA_CRIACAO        TIMESTAMP      NOT NULL,
    CRIADO_POR          VARCHAR2(200)  NOT NULL,
    CRIADO_POR_ID       VARCHAR2(36)   NOT NULL,
    ASSINATURA_FILENAME VARCHAR2(255),
    -- Campos espelhando a planilha física de controle de manutenção que o
    -- cliente já usava (máquina/serviço feito/motivo/valor/assinatura) —
    -- DESCRICAO acima cobre "motivo".
    FOTO_FILENAME       VARCHAR2(500),
    FOTO_ORIGINAL_NAME  VARCHAR2(500),
    VALOR               NUMBER(10,2),
    SERVICO_FEITO       VARCHAR2(2000 CHAR),
    -- Técnico/empresa terceirizada que executou o serviço — texto livre,
    -- diferente de RESPONSAVEL (usuário interno do sistema).
    TECNICO             VARCHAR2(200),
    EMPRESA             VARCHAR2(200),
    -- Preventiva ou Corretiva (ver core/config.TIPO_MANUTENCAO_LIST),
    -- definido na abertura da manutenção.
    TIPO                VARCHAR2(30)
);

CREATE TABLE MANUTENCAO_HISTORICO (
    ID                    NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    MANUTENCAO_ID         VARCHAR2(36)   NOT NULL REFERENCES MANUTENCOES(ID) ON DELETE CASCADE,
    ACAO                  VARCHAR2(4000 CHAR) NOT NULL,
    POR                   VARCHAR2(200)  NOT NULL,
    DATA                  TIMESTAMP      NOT NULL,
    ARQUIVO_FILENAME      VARCHAR2(500),
    ARQUIVO_ORIGINAL_NAME VARCHAR2(500)
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
