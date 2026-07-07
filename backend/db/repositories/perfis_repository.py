from ..connection import get_cursor, rows_to_dicts


def list_perfis() -> list:
    with get_cursor() as cursor:
        cursor.execute("SELECT ID, NOME, DESCRICAO, PADRAO FROM PERFIS")
        perfis = rows_to_dicts(cursor)

        cursor.execute("SELECT PERFIL_ID, PERMISSAO FROM PERFIL_PERMISSOES")
        permissoes_por_perfil: dict = {}
        for row in rows_to_dicts(cursor):
            permissoes_por_perfil.setdefault(row['perfil_id'], []).append(row['permissao'])

    return [
        {
            'id': p['id'],
            'nome': p['nome'],
            'descricao': p['descricao'] or '',
            'permissoes': permissoes_por_perfil.get(p['id'], []),
            'padrao': bool(p['padrao']),
        }
        for p in perfis
    ]


def save_perfis(perfis: list) -> None:
    # Transações separadas para PERFIS e para PERFIL_PERMISSOES — ver o
    # comentário equivalente em tickets_repository.save_tickets: MERGE no
    # pai + DML na tabela filha (FK) na mesma transação reproduziu um
    # ORA-12860 (deadlock) no Autonomous Database.
    ids_atuais = [p['id'] for p in perfis]

    with get_cursor(commit=True) as cursor:
        for perfil in perfis:
            cursor.execute(
                """
                MERGE INTO PERFIS dst
                USING (SELECT :id AS id FROM dual) src
                ON (dst.ID = src.id)
                WHEN MATCHED THEN UPDATE SET
                    NOME = :nome, DESCRICAO = :descricao, PADRAO = :padrao
                WHEN NOT MATCHED THEN INSERT (ID, NOME, DESCRICAO, PADRAO)
                    VALUES (:id, :nome, :descricao, :padrao)
                """,
                id=perfil['id'], nome=perfil['nome'],
                descricao=perfil.get('descricao') or None,
                padrao=1 if perfil.get('padrao') else 0,
            )

        if ids_atuais:
            placeholders = ', '.join(f':id{i}' for i in range(len(ids_atuais)))
            binds = {f'id{i}': v for i, v in enumerate(ids_atuais)}
            cursor.execute(f"DELETE FROM PERFIS WHERE ID NOT IN ({placeholders})", binds)
        else:
            cursor.execute("DELETE FROM PERFIS")

    # DELETE e INSERT em transações separadas: reinserir a mesma PK
    # composta (perfil_id, permissao) recém-apagada na mesma transação
    # também reproduziu o ORA-12860 nesta base (mesmo caso de
    # config_repository.save_config para IPS_PERMITIDOS/SISTEMAS).
    with get_cursor(commit=True) as cursor:
        for perfil in perfis:
            cursor.execute("DELETE FROM PERFIL_PERMISSOES WHERE PERFIL_ID = :id", id=perfil['id'])

    with get_cursor(commit=True) as cursor:
        for perfil in perfis:
            for permissao in perfil.get('permissoes', []):
                cursor.execute(
                    "INSERT INTO PERFIL_PERMISSOES (PERFIL_ID, PERMISSAO) VALUES (:perfil_id, :permissao)",
                    perfil_id=perfil['id'], permissao=permissao,
                )
