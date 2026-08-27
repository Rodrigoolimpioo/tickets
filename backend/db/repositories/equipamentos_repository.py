import uuid
from datetime import datetime

from ..connection import get_cursor, rows_to_dicts

_DATA_CADASTRO_FMT = '%Y-%m-%dT%H:%M:%S'


def list_tipos() -> dict:
    """Taxonomia fixa (semeada em migrate.py) — {categoria: [tipos]},
    usada só pra alimentar o <select> ao cadastrar um equipamento."""
    with get_cursor() as cursor:
        cursor.execute("SELECT CATEGORIA, NOME FROM EQUIPAMENTO_TIPOS ORDER BY CATEGORIA, NOME")
        rows = rows_to_dicts(cursor)
    tipos: dict = {}
    for r in rows:
        tipos.setdefault(r['categoria'], []).append(r['nome'])
    return tipos


def _to_dict(row: dict) -> dict:
    cadastro: datetime = row['data_cadastro']
    return {
        'id': row['id'],
        'nome': row['nome'],
        'categoria': row['categoria'],
        'tipo': row['tipo'],
        'unidade': row['unidade'],
        'numero_serie': row['numero_serie'] or '',
        'ativo': bool(row['ativo']),
        'data_cadastro': cadastro.strftime(_DATA_CADASTRO_FMT) if cadastro else None,
    }


def list_equipamentos() -> list:
    with get_cursor() as cursor:
        cursor.execute(
            """
            SELECT ID, NOME, CATEGORIA, TIPO, UNIDADE, NUMERO_SERIE, ATIVO, DATA_CADASTRO
            FROM EQUIPAMENTOS
            """
        )
        rows = rows_to_dicts(cursor)
    return [_to_dict(r) for r in rows]


def save_equipamentos(equipamentos: list) -> None:
    ids_atuais = [e['id'] for e in equipamentos]

    with get_cursor(commit=True) as cursor:
        for e in equipamentos:
            data_cadastro = (
                datetime.strptime(e['data_cadastro'], _DATA_CADASTRO_FMT)
                if e.get('data_cadastro') else datetime.utcnow()
            )
            cursor.execute(
                """
                MERGE INTO EQUIPAMENTOS dst
                USING (SELECT :id AS id FROM dual) src
                ON (dst.ID = src.id)
                WHEN MATCHED THEN UPDATE SET
                    NOME = :nome, CATEGORIA = :categoria, TIPO = :tipo, UNIDADE = :unidade,
                    NUMERO_SERIE = :numero_serie, ATIVO = :ativo
                WHEN NOT MATCHED THEN INSERT (
                    ID, NOME, CATEGORIA, TIPO, UNIDADE, NUMERO_SERIE, ATIVO, DATA_CADASTRO
                ) VALUES (
                    :id, :nome, :categoria, :tipo, :unidade, :numero_serie, :ativo, :data_cadastro
                )
                """,
                id=e.get('id') or str(uuid.uuid4()), nome=e['nome'],
                categoria=e.get('categoria'), tipo=e.get('tipo'), unidade=e['unidade'],
                numero_serie=e.get('numero_serie') or None,
                ativo=1 if e.get('ativo', True) else 0, data_cadastro=data_cadastro,
            )

        if ids_atuais:
            placeholders = ', '.join(f':id{i}' for i in range(len(ids_atuais)))
            binds = {f'id{i}': v for i, v in enumerate(ids_atuais)}
            cursor.execute(f"DELETE FROM EQUIPAMENTOS WHERE ID NOT IN ({placeholders})", binds)
        else:
            cursor.execute("DELETE FROM EQUIPAMENTOS")
