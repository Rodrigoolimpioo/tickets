from ..connection import get_cursor, rows_to_dicts
from . import perfis_repository


def get_config() -> dict:
    with get_cursor() as cursor:
        cursor.execute(
            """
            SELECT IP_CONTROL_ENABLED, HORARIO_CONTROL_ENABLED, NOME_SISTEMA,
                   LOGO_FILENAME, COR_BOTAO, COR_BOTAO_LIGHT, COR_FUNDO, COR_SIDEBAR,
                   COR_SIDEBAR_ATIVO, COR_TEXTO, COR_SIDEBAR_TEXTO,
                   WHATSAPP_ENABLED
            FROM CONFIG_GERAL WHERE ID = 1
            """
        )
        geral = rows_to_dicts(cursor)

        cursor.execute("SELECT IP FROM IPS_PERMITIDOS ORDER BY IP")
        ips = [r['ip'] for r in rows_to_dicts(cursor)]

        cursor.execute(
            "SELECT DIA, NOME, INICIO, FIM, ATIVO FROM HORARIOS_CONTROLE ORDER BY DIA"
        )
        horarios = [
            {'dia': r['dia'], 'nome': r['nome'], 'inicio': r['inicio'],
             'fim': r['fim'], 'ativo': bool(r['ativo'])}
            for r in rows_to_dicts(cursor)
        ]

        cursor.execute("SELECT NOME FROM SISTEMAS ORDER BY NOME")
        sistemas = [r['nome'] for r in rows_to_dicts(cursor)]

        cursor.execute("SELECT STATUS, ATIVO, MENSAGEM FROM WHATSAPP_STATUS_CONFIG")
        wpp_rows = rows_to_dicts(cursor)
        status_ativo = {r['status']: bool(r['ativo']) for r in wpp_rows}
        status_mensagem = {r['status']: r['mensagem'] or '' for r in wpp_rows}

    g = geral[0]
    return {
        'ip_control': {'enabled': bool(g['ip_control_enabled']), 'ips': ips},
        'horario_control': {'enabled': bool(g['horario_control_enabled']), 'horarios': horarios},
        'sistemas': sistemas,
        'personalizacao': {
            'cor_botao': g['cor_botao'],
            'cor_botao_light': g['cor_botao_light'],
            'cor_fundo': g['cor_fundo'],
            'cor_sidebar': g['cor_sidebar'],
            'cor_sidebar_ativo': g['cor_sidebar_ativo'],
            'cor_texto': g['cor_texto'],
            'cor_sidebar_texto': g['cor_sidebar_texto'],
            'nome_sistema': g['nome_sistema'],
            'logo_filename': g['logo_filename'],
        },
        'whatsapp': {
            'enabled': bool(g['whatsapp_enabled']),
            'status_ativo': status_ativo,
            'status_mensagem': status_mensagem,
        },
        'perfis': perfis_repository.list_perfis(),
    }


def save_config(cfg: dict) -> None:
    # Cada tabela é gravada em sua própria transação. Fazer DML em mais de
    # uma tabela dentro da mesma transação reproduziu, de forma
    # determinística, um ORA-12860 (deadlock por sibling row lock) neste
    # Autonomous Database — mesmo entre tabelas sem FK entre si (ver
    # tickets_repository.save_tickets para outro caso do mesmo problema).
    pers = cfg['personalizacao']

    wpp = cfg.get('whatsapp', {})

    with get_cursor(commit=True) as cursor:
        cursor.execute(
            """
            UPDATE CONFIG_GERAL SET
                IP_CONTROL_ENABLED = :ip_enabled,
                HORARIO_CONTROL_ENABLED = :horario_enabled,
                NOME_SISTEMA = :nome_sistema, LOGO_FILENAME = :logo,
                COR_BOTAO = :cor_botao, COR_BOTAO_LIGHT = :cor_botao_light,
                COR_FUNDO = :cor_fundo, COR_SIDEBAR = :cor_sidebar,
                COR_SIDEBAR_ATIVO = :cor_sidebar_ativo, COR_TEXTO = :cor_texto,
                COR_SIDEBAR_TEXTO = :cor_sidebar_texto,
                WHATSAPP_ENABLED = :whatsapp_enabled
            WHERE ID = 1
            """,
            ip_enabled=1 if cfg['ip_control']['enabled'] else 0,
            horario_enabled=1 if cfg['horario_control']['enabled'] else 0,
            nome_sistema=pers['nome_sistema'], logo=pers.get('logo_filename'),
            cor_botao=pers['cor_botao'], cor_botao_light=pers['cor_botao_light'],
            cor_fundo=pers['cor_fundo'], cor_sidebar=pers['cor_sidebar'],
            cor_sidebar_ativo=pers['cor_sidebar_ativo'], cor_texto=pers['cor_texto'],
            cor_sidebar_texto=pers['cor_sidebar_texto'],
            whatsapp_enabled=1 if wpp.get('enabled') else 0,
        )

    # DELETE e INSERT também separados em transações distintas: reinserir
    # a mesma PK (o mesmo IP) que acabou de ser apagada, na mesma
    # transação, também reproduziu o ORA-12860 nesta base.
    with get_cursor(commit=True) as cursor:
        cursor.execute("DELETE FROM IPS_PERMITIDOS")
    with get_cursor(commit=True) as cursor:
        for ip in cfg['ip_control']['ips']:
            cursor.execute("INSERT INTO IPS_PERMITIDOS (IP) VALUES (:ip)", ip=ip)

    with get_cursor(commit=True) as cursor:
        for h in cfg['horario_control']['horarios']:
            cursor.execute(
                """
                MERGE INTO HORARIOS_CONTROLE dst
                USING (SELECT :dia AS dia FROM dual) src
                ON (dst.DIA = src.dia)
                WHEN MATCHED THEN UPDATE SET
                    NOME = :nome, INICIO = :inicio, FIM = :fim, ATIVO = :ativo
                WHEN NOT MATCHED THEN INSERT (DIA, NOME, INICIO, FIM, ATIVO)
                    VALUES (:dia, :nome, :inicio, :fim, :ativo)
                """,
                dia=h['dia'], nome=h['nome'], inicio=h['inicio'], fim=h['fim'],
                ativo=1 if h['ativo'] else 0,
            )

    with get_cursor(commit=True) as cursor:
        status_mensagem = wpp.get('status_mensagem', {})
        for status, ativo in wpp.get('status_ativo', {}).items():
            cursor.execute(
                """
                MERGE INTO WHATSAPP_STATUS_CONFIG dst
                USING (SELECT :status AS status FROM dual) src
                ON (dst.STATUS = src.status)
                WHEN MATCHED THEN UPDATE SET ATIVO = :ativo, MENSAGEM = :mensagem
                WHEN NOT MATCHED THEN INSERT (STATUS, ATIVO, MENSAGEM) VALUES (:status, :ativo, :mensagem)
                """,
                status=status, ativo=1 if ativo else 0,
                mensagem=status_mensagem.get(status) or None,
            )

    with get_cursor(commit=True) as cursor:
        cursor.execute("DELETE FROM SISTEMAS")
    with get_cursor(commit=True) as cursor:
        for sistema in cfg['sistemas']:
            cursor.execute("INSERT INTO SISTEMAS (NOME) VALUES (:nome)", nome=sistema)

    perfis_repository.save_perfis(cfg.get('perfis', []))
