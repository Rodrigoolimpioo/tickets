"""Envio de mensagem via WhatsApp usando o gateway Z-API.

Mesmo contrato do core/mailer.py: nunca lança para o chamador em caso de
falha — loga o erro e retorna False, porque a atualização do ticket sempre
deve seguir normalmente mesmo se a notificação falhar ou não estiver
configurada.
"""
import logging
import re

import requests

from .config import ZAPI_CLIENT_TOKEN, ZAPI_INSTANCE_ID, ZAPI_TOKEN

logger = logging.getLogger(__name__)

_ZAPI_BASE_URL = 'https://api.z-api.io'


def enviar_whatsapp(numero: str, mensagem: str) -> bool:
    if not (ZAPI_INSTANCE_ID and ZAPI_TOKEN):
        logger.warning('Z-API não configurado — WhatsApp para %s não enviado.', numero)
        return False

    telefone = re.sub(r'\D', '', numero or '')
    if not telefone:
        return False

    url = f'{_ZAPI_BASE_URL}/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_TOKEN}/send-text'
    headers = {'Client-Token': ZAPI_CLIENT_TOKEN} if ZAPI_CLIENT_TOKEN else {}

    try:
        resp = requests.post(url, json={'phone': telefone, 'message': mensagem},
                              headers=headers, timeout=10)
        resp.raise_for_status()
        return True
    except requests.RequestException as exc:
        logger.error('Falha ao enviar WhatsApp para %s: %s', telefone, exc)
        return False
