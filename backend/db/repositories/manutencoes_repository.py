from datetime import datetime

from ..connection import get_cursor, rows_to_dicts

_DATA_CRIACAO_FMT = '%Y-%m-%dT%H:%M:%S'
_DATA_FORMATADA_FMT = '%d/%m/%Y %H:%M:%S'


def _manutencao_to_dict(row: dict, historico: list) -> dict:
    criacao: datetime = row['data_criacao']
    foto = None
    if row.get('foto_filename'):
        foto = {'filename': row['foto_filename'], 'original_name': row['foto_original_name']}
    return {
        'id': row['id'],
        'numero': row['numero'],
        'equipamento_id': row['equipamento_id'],
        'unidade': row['unidade'],
        'responsavel_id': row['responsavel_id'],
        'responsavel_nome': row['responsavel_nome'] or '',
        'descricao': row['descricao'],
        'data_criacao': criacao.strftime(_DATA_CRIACAO_FMT),
        'data_formatada': criacao.strftime(_DATA_FORMATADA_FMT),
        'status': row['status'],
        'criado_por': row['criado_por'],
        'criado_por_id': row['criado_por_id'],
        'assinatura_filename': row['assinatura_filename'],
        'foto_equipamento': foto,
        'valor': float(row['valor']) if row.get('valor') is not None else None,
        'servico_feito': row.get('servico_feito') or '',
        'tecnico': row.get('tecnico') or '',
        'empresa': row.get('empresa') or '',
        'tipo': row.get('tipo') or '',
        'historico': historico,
    }


def list_manutencoes() -> list:
    with get_cursor() as cursor:
        cursor.execute(
            """
            SELECT ID, NUMERO, EQUIPAMENTO_ID, UNIDADE, RESPONSAVEL_ID, RESPONSAVEL_NOME,
                   DESCRICAO, DATA_CRIACAO, STATUS, CRIADO_POR, CRIADO_POR_ID, ASSINATURA_FILENAME,
                   FOTO_FILENAME, FOTO_ORIGINAL_NAME, VALOR, SERVICO_FEITO, TECNICO, EMPRESA, TIPO
            FROM MANUTENCOES
            """
        )
        manutencoes = rows_to_dicts(cursor)

        cursor.execute(
            """
            SELECT ID, MANUTENCAO_ID, ACAO, POR, DATA, ARQUIVO_FILENAME, ARQUIVO_ORIGINAL_NAME
            FROM MANUTENCAO_HISTORICO ORDER BY ID
            """
        )
        historico_por_manutencao: dict = {}
        for row in rows_to_dicts(cursor):
            entrada = {
                'acao': row['acao'], 'por': row['por'],
                'data': row['data'].strftime(_DATA_FORMATADA_FMT),
            }
            if row['arquivo_filename']:
                entrada['arquivo'] = {
                    'filename': row['arquivo_filename'],
                    'original_name': row['arquivo_original_name'],
                }
            historico_por_manutencao.setdefault(row['manutencao_id'], []).append(entrada)

    return [_manutencao_to_dict(m, historico_por_manutencao.get(m['id'], [])) for m in manutencoes]


def get_next_manutencao_numero() -> str:
    with get_cursor() as cursor:
        cursor.execute("SELECT NVL(MAX(TO_NUMBER(SUBSTR(NUMERO, 5))), 0) + 1 FROM MANUTENCOES")
        proximo = cursor.fetchone()[0]
    return f'MNT-{int(proximo):04d}'


def save_manutencoes(manutencoes: list) -> None:
    # Mesmo motivo documentado em tickets_repository.save_tickets: MERGE na
    # tabela pai e DML na tabela filha (histórico) na mesma transação
    # reproduz ORA-12860 (deadlock por sibling row lock) nesse Autonomous DB.
    ids_atuais = [m['id'] for m in manutencoes]

    with get_cursor(commit=True) as cursor:
        for m in manutencoes:
            data_criacao = datetime.strptime(m['data_criacao'], _DATA_CRIACAO_FMT)
            cursor.execute(
                """
                MERGE INTO MANUTENCOES dst
                USING (SELECT :id AS id FROM dual) src
                ON (dst.ID = src.id)
                WHEN MATCHED THEN UPDATE SET
                    NUMERO = :numero, EQUIPAMENTO_ID = :equipamento_id, UNIDADE = :unidade,
                    RESPONSAVEL_ID = :responsavel_id, RESPONSAVEL_NOME = :responsavel_nome,
                    DESCRICAO = :descricao, DATA_CRIACAO = :data_criacao, STATUS = :status,
                    CRIADO_POR = :criado_por, CRIADO_POR_ID = :criado_por_id,
                    ASSINATURA_FILENAME = :assinatura_filename,
                    FOTO_FILENAME = :foto_filename, FOTO_ORIGINAL_NAME = :foto_original_name,
                    VALOR = :valor, SERVICO_FEITO = :servico_feito,
                    TECNICO = :tecnico, EMPRESA = :empresa, TIPO = :tipo
                WHEN NOT MATCHED THEN INSERT (
                    ID, NUMERO, EQUIPAMENTO_ID, UNIDADE, RESPONSAVEL_ID, RESPONSAVEL_NOME,
                    DESCRICAO, DATA_CRIACAO, STATUS, CRIADO_POR, CRIADO_POR_ID, ASSINATURA_FILENAME,
                    FOTO_FILENAME, FOTO_ORIGINAL_NAME, VALOR, SERVICO_FEITO, TECNICO, EMPRESA, TIPO
                ) VALUES (
                    :id, :numero, :equipamento_id, :unidade, :responsavel_id, :responsavel_nome,
                    :descricao, :data_criacao, :status, :criado_por, :criado_por_id, :assinatura_filename,
                    :foto_filename, :foto_original_name, :valor, :servico_feito, :tecnico, :empresa, :tipo
                )
                """,
                id=m['id'], numero=m['numero'], equipamento_id=m['equipamento_id'],
                unidade=m['unidade'], responsavel_id=m.get('responsavel_id'),
                responsavel_nome=m.get('responsavel_nome') or None, descricao=m['descricao'],
                data_criacao=data_criacao, status=m['status'], criado_por=m['criado_por'],
                criado_por_id=m['criado_por_id'], assinatura_filename=m.get('assinatura_filename'),
                foto_filename=(m.get('foto_equipamento') or {}).get('filename'),
                foto_original_name=(m.get('foto_equipamento') or {}).get('original_name'),
                valor=m.get('valor'), servico_feito=m.get('servico_feito') or None,
                tecnico=m.get('tecnico') or None, empresa=m.get('empresa') or None,
                tipo=m.get('tipo') or None,
            )

        if ids_atuais:
            placeholders = ', '.join(f':id{i}' for i in range(len(ids_atuais)))
            binds = {f'id{i}': v for i, v in enumerate(ids_atuais)}
            cursor.execute(f"DELETE FROM MANUTENCOES WHERE ID NOT IN ({placeholders})", binds)
        else:
            cursor.execute("DELETE FROM MANUTENCOES")

    with get_cursor(commit=True) as cursor:
        for m in manutencoes:
            cursor.execute("DELETE FROM MANUTENCAO_HISTORICO WHERE MANUTENCAO_ID = :id", id=m['id'])
            for entrada in m.get('historico', []):
                arquivo = entrada.get('arquivo') or {}
                cursor.execute(
                    """
                    INSERT INTO MANUTENCAO_HISTORICO
                        (MANUTENCAO_ID, ACAO, POR, DATA, ARQUIVO_FILENAME, ARQUIVO_ORIGINAL_NAME)
                    VALUES (:manutencao_id, :acao, :por, :data, :arquivo_filename, :arquivo_original_name)
                    """,
                    manutencao_id=m['id'], acao=entrada['acao'], por=entrada['por'],
                    data=datetime.strptime(entrada['data'], _DATA_FORMATADA_FMT),
                    arquivo_filename=arquivo.get('filename'),
                    arquivo_original_name=arquivo.get('original_name'),
                )
