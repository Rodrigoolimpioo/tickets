from datetime import datetime

import pytz
from flask import request


def get_brasilia_time():
    return datetime.now(pytz.timezone('America/Sao_Paulo'))


def get_client_ip():
    # Não confiar em X-Forwarded-For — pode ser falsificado para burlar controle de IP
    return request.remote_addr or '127.0.0.1'
