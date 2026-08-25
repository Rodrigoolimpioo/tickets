"""Envio de mensagem via WhatsApp usando o wa-service interno
(github.com/JuanDiniz/wa-service, whatsapp-web.js), que roda na mesma VM
escutando só em 127.0.0.1.

Mesmo contrato de sempre: nunca lança para o chamador em caso de falha —
loga o erro e retorna False, porque a atualização do ticket sempre deve
seguir normalmente mesmo se a notificação falhar ou não estiver configurada.
"""
import logging
import re

import requests

from .config import WA_SERVICE_API_KEY, WA_SERVICE_URL

logger = logging.getLogger(__name__)


def enviar_whatsapp(numero: str, mensagem: str) -> bool:
    if not (WA_SERVICE_URL and WA_SERVICE_API_KEY):
        logger.warning('wa-service não configurado — WhatsApp para %s não enviado.', numero)
        return False

    telefone = re.sub(r'\D', '', numero or '')
    if not telefone:
        return False

    url = f"{WA_SERVICE_URL.rstrip('/')}/send"
    headers = {'x-api-key': WA_SERVICE_API_KEY}

    try:
        resp = requests.post(url, json={'to': telefone, 'message': mensagem},
                              headers=headers, timeout=15)
        resp.raise_for_status()
        return True
    except requests.RequestException as exc:
        logger.error('Falha ao enviar WhatsApp para %s: %s', telefone, exc)
        return False
