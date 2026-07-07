from datetime import datetime

from ..connection import get_cursor, rows_to_dicts

_DATA_CRIACAO_FMT = '%Y-%m-%dT%H:%M:%S'
_DATA_FORMATADA_FMT = '%d/%m/%Y %H:%M:%S'


def _ticket_to_dict(row: dict, historico: list) -> dict:
    criacao: datetime = row['data_criacao']
    arquivo = None
    if row['arquivo_filename']:
        arquivo = {
            'filename': row['arquivo_filename'],
            'original_name': row['arquivo_original_name'],
            'tipo': row['arquivo_tipo'],
        }
    return {
        'id': row['id'],
        'numero': row['numero'],
        'nome': row['nome'],
        'ocorrencia': row['ocorrencia'],
        'sistema': row['sistema'],
        'arquivo': arquivo,
        'data_criacao': criacao.strftime(_DATA_CRIACAO_FMT),
        'data_formatada': criacao.strftime(_DATA_FORMATADA_FMT),
        'status': row['status'],
        'criado_por': row['criado_por'],
        'criado_por_id': row['criado_por_id'],
        'historico': historico,
    }


def list_tickets() -> list:
    with get_cursor() as cursor:
        cursor.execute(
            """
            SELECT ID, NUMERO, NOME, OCORRENCIA, SISTEMA, ARQUIVO_FILENAME,
                   ARQUIVO_ORIGINAL_NAME, ARQUIVO_TIPO, DATA_CRIACAO, STATUS,
                   CRIADO_POR, CRIADO_POR_ID
            FROM TICKETS
            """
        )
        tickets = rows_to_dicts(cursor)

        cursor.execute(
            "SELECT ID, TICKET_ID, ACAO, POR, DATA FROM TICKET_HISTORICO ORDER BY ID"
        )
        historico_por_ticket: dict = {}
        for row in rows_to_dicts(cursor):
            historico_por_ticket.setdefault(row['ticket_id'], []).append({
                'acao': row['acao'],
                'por': row['por'],
                'data': row['data'].strftime(_DATA_FORMATADA_FMT),
            })

    return [_ticket_to_dict(t, historico_por_ticket.get(t['id'], [])) for t in tickets]


def get_ticket_stats() -> dict:
    with get_cursor() as cursor:
        cursor.execute(
            """
            SELECT
                COUNT(*)                                          AS total,
                SUM(CASE WHEN STATUS = 'Aberto' THEN 1 ELSE 0 END) AS abertos
            FROM TICKETS
            """
        )
        row = cursor.fetchone()
    return {'total': row[0], 'abertos': row[1] or 0}


def get_next_ticket_number() -> str:
    with get_cursor() as cursor:
        cursor.execute("SELECT NVL(MAX(TO_NUMBER(SUBSTR(NUMERO, 5))), 0) + 1 FROM TICKETS")
        proximo = cursor.fetchone()[0]
    return f'TKT-{int(proximo):04d}'


def save_tickets(tickets: list) -> None:
    # As três etapas abaixo rodam em transações separadas de propósito.
    # Fazer o MERGE em TICKETS e, na mesma transação, mexer em
    # TICKET_HISTORICO (tabela filha via FK) reproduziu de forma
    # determinística um ORA-12860 (deadlock por sibling row lock) no
    # Autonomous Database — aparentemente uma interação entre o MERGE e a
    # sequence da coluna IDENTITY da tabela filha. Commitar entre as
    # etapas elimina o problema.
    ids_atuais = [t['id'] for t in tickets]

    with get_cursor(commit=True) as cursor:
        for ticket in tickets:
            arquivo = ticket.get('arquivo') or {}
            data_criacao = datetime.strptime(ticket['data_criacao'], _DATA_CRIACAO_FMT)
            cursor.execute(
                """
                MERGE INTO TICKETS dst
                USING (SELECT :id AS id FROM dual) src
                ON (dst.ID = src.id)
                WHEN MATCHED THEN UPDATE SET
                    NUMERO = :numero, NOME = :nome, OCORRENCIA = :ocorrencia,
                    SISTEMA = :sistema, ARQUIVO_FILENAME = :arquivo_filename,
                    ARQUIVO_ORIGINAL_NAME = :arquivo_original_name, ARQUIVO_TIPO = :arquivo_tipo,
                    DATA_CRIACAO = :data_criacao, STATUS = :status,
                    CRIADO_POR = :criado_por, CRIADO_POR_ID = :criado_por_id
                WHEN NOT MATCHED THEN INSERT (
                    ID, NUMERO, NOME, OCORRENCIA, SISTEMA, ARQUIVO_FILENAME,
                    ARQUIVO_ORIGINAL_NAME, ARQUIVO_TIPO, DATA_CRIACAO, STATUS,
                    CRIADO_POR, CRIADO_POR_ID
                ) VALUES (
                    :id, :numero, :nome, :ocorrencia, :sistema, :arquivo_filename,
                    :arquivo_original_name, :arquivo_tipo, :data_criacao, :status,
                    :criado_por, :criado_por_id
                )
                """,
                id=ticket['id'], numero=ticket['numero'], nome=ticket['nome'],
                ocorrencia=ticket['ocorrencia'], sistema=ticket['sistema'],
                arquivo_filename=arquivo.get('filename'),
                arquivo_original_name=arquivo.get('original_name'),
                arquivo_tipo=arquivo.get('tipo'), data_criacao=data_criacao,
                status=ticket['status'], criado_por=ticket['criado_por'],
                criado_por_id=ticket['criado_por_id'],
            )

        if ids_atuais:
            placeholders = ', '.join(f':id{i}' for i in range(len(ids_atuais)))
            binds = {f'id{i}': v for i, v in enumerate(ids_atuais)}
            cursor.execute(f"DELETE FROM TICKETS WHERE ID NOT IN ({placeholders})", binds)
        else:
            cursor.execute("DELETE FROM TICKETS")

    with get_cursor(commit=True) as cursor:
        for ticket in tickets:
            cursor.execute("DELETE FROM TICKET_HISTORICO WHERE TICKET_ID = :id", id=ticket['id'])
            for entrada in ticket.get('historico', []):
                cursor.execute(
                    "INSERT INTO TICKET_HISTORICO (TICKET_ID, ACAO, POR, DATA) "
                    "VALUES (:ticket_id, :acao, :por, :data)",
                    ticket_id=ticket['id'], acao=entrada['acao'], por=entrada['por'],
                    data=datetime.strptime(entrada['data'], _DATA_FORMATADA_FMT),
                )
