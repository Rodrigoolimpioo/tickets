"""Envio de e-mail via SMTP (usado hoje só pelo fluxo de reset de senha).

Não lança para o chamador em caso de falha de envio — loga o erro e
retorna False, porque o fluxo de "esqueci minha senha" sempre deve
responder com a mesma mensagem genérica ao usuário (evita confirmar se
um e-mail existe ou não na base) mesmo se o SMTP estiver fora do ar.
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .config import SMTP_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER

logger = logging.getLogger(__name__)


def enviar_email(destinatario: str, assunto: str, corpo_html: str) -> bool:
    if not (SMTP_HOST and SMTP_USER and SMTP_PASSWORD):
        logger.warning('SMTP não configurado — e-mail para %s não enviado.', destinatario)
        return False

    msg = MIMEMultipart('alternative')
    msg['Subject'] = assunto
    msg['From'] = SMTP_FROM
    msg['To'] = destinatario
    msg.attach(MIMEText(corpo_html, 'html', 'utf-8'))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [destinatario], msg.as_string())
        return True
    except (smtplib.SMTPException, OSError) as exc:
        logger.error('Falha ao enviar e-mail para %s: %s', destinatario, exc)
        return False
