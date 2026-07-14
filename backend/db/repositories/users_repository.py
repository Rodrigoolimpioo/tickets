from ..connection import get_cursor, rows_to_dicts


def _to_dict(row: dict) -> dict:
    return {
        'id': row['id'],
        'username': row['username'],
        'password': row['password'],
        'name': row['name'],
        'role': row['role'],
        'email': row['email'] or '',
        'telefone': row['telefone'] or '',
        'ativo': bool(row['ativo']),
        'perfil_id': row['perfil_id'],
    }


def list_users() -> list:
    with get_cursor() as cursor:
        cursor.execute(
            "SELECT ID, USERNAME, PASSWORD, NAME, ROLE, EMAIL, TELEFONE, ATIVO, PERFIL_ID FROM USERS"
        )
        rows = rows_to_dicts(cursor)
    return [_to_dict(r) for r in rows]


def save_users(users: list) -> None:
    ids_atuais = [u['id'] for u in users]

    with get_cursor(commit=True) as cursor:
        for user in users:
            cursor.execute(
                """
                MERGE INTO USERS dst
                USING (SELECT :id AS id FROM dual) src
                ON (dst.ID = src.id)
                WHEN MATCHED THEN UPDATE SET
                    USERNAME = :username, PASSWORD = :password, NAME = :name,
                    ROLE = :role, EMAIL = :email, TELEFONE = :telefone,
                    ATIVO = :ativo, PERFIL_ID = :perfil_id
                WHEN NOT MATCHED THEN INSERT (ID, USERNAME, PASSWORD, NAME, ROLE, EMAIL, TELEFONE, ATIVO, PERFIL_ID)
                    VALUES (:id, :username, :password, :name, :role, :email, :telefone, :ativo, :perfil_id)
                """,
                id=user['id'], username=user['username'], password=user['password'],
                name=user['name'], role=user['role'], email=user.get('email') or None,
                telefone=user.get('telefone') or None,
                ativo=1 if user.get('ativo', True) else 0, perfil_id=user.get('perfil_id'),
            )

        if ids_atuais:
            placeholders = ', '.join(f':id{i}' for i in range(len(ids_atuais)))
            binds = {f'id{i}': v for i, v in enumerate(ids_atuais)}
            cursor.execute(f"DELETE FROM USERS WHERE ID NOT IN ({placeholders})", binds)
        else:
            cursor.execute("DELETE FROM USERS")
