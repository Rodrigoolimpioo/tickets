from datetime import datetime

import pytz
from flask import request


def get_brasilia_time():
    return datetime.now(pytz.timezone('America/Sao_Paulo'))


def get_client_ip():
    # Não confiar em X-Forwarded-For — pode ser falsificado para burlar controle de IP
    return request.remote_addr or '127.0.0.1'


def classificar_data_prevista(data_str: str, dias_alerta: int) -> str | None:
    """'vencida' | 'proxima' | 'ok' — usado no alerta de manutenção preventiva
    (PROXIMA_MANUTENCAO). data_str é 'YYYY-MM-DD' ou None/vazio."""
    if not data_str:
        return None
    hoje = get_brasilia_time().date()
    data = datetime.strptime(data_str, '%Y-%m-%d').date()
    dias = (data - hoje).days
    if dias < 0:
        return 'vencida'
    if dias <= dias_alerta:
        return 'proxima'
    return 'ok'
