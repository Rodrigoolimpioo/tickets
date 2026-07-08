from datetime import datetime

from ..connection import get_cursor, rows_to_dicts

_DATA_FMT = '%d/%m/%Y %H:%M:%S'


def registrar(acao: str, quando: datetime, usuario_id: str = None, usuario_nome: str = None,
              detalhes: str = None, ip: str = None, entidade_tipo: str = None,
              entidade_id: str = None) -> None:
    with get_cursor(commit=True) as cursor:
        cursor.execute(
            """
            INSERT INTO LOGS_AUDITORIA
                (DATA_HORA, USUARIO_ID, USUARIO_NOME, ACAO, DETALHES, IP, ENTIDADE_TIPO, ENTIDADE_ID)
            VALUES
                (:data_hora, :usuario_id, :usuario_nome, :acao, :detalhes, :ip, :entidade_tipo, :entidade_id)
            """,
            data_hora=quando, usuario_id=usuario_id, usuario_nome=usuario_nome,
            acao=acao, detalhes=detalhes, ip=ip,
            entidade_tipo=entidade_tipo, entidade_id=entidade_id,
        )


def contar_desde(acao: str, ip: str, desde: datetime) -> int:
    with get_cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM LOGS_AUDITORIA WHERE ACAO = :acao AND IP = :ip AND DATA_HORA > :desde",
            acao=acao, ip=ip, desde=desde,
        )
        return cursor.fetchone()[0]


def listar(acao: str = '', usuario: str = '', busca: str = '', limit: int = 200) -> list:
    condicoes = []
    binds = {'limit': limit}

    if acao:
        condicoes.append('ACAO = :acao')
        binds['acao'] = acao
    if usuario:
        condicoes.append('LOWER(USUARIO_NOME) LIKE :usuario')
        binds['usuario'] = f'%{usuario.lower()}%'
    if busca:
        condicoes.append('LOWER(DETALHES) LIKE :busca')
        binds['busca'] = f'%{busca.lower()}%'

    where = f"WHERE {' AND '.join(condicoes)}" if condicoes else ''

    with get_cursor() as cursor:
        cursor.execute(
            f"""
            SELECT ID, DATA_HORA, USUARIO_ID, USUARIO_NOME, ACAO, DETALHES, IP, ENTIDADE_TIPO, ENTIDADE_ID
            FROM LOGS_AUDITORIA
            {where}
            ORDER BY DATA_HORA DESC
            FETCH FIRST :limit ROWS ONLY
            """,
            binds,
        )
        rows = rows_to_dicts(cursor)

    for row in rows:
        row['data_formatada'] = row['data_hora'].strftime(_DATA_FMT)
    return rows


def listar_acoes_distintas() -> list:
    with get_cursor() as cursor:
        cursor.execute("SELECT DISTINCT ACAO FROM LOGS_AUDITORIA ORDER BY ACAO")
        return [r[0] for r in cursor.fetchall()]
