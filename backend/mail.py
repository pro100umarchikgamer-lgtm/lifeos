"""Durable, encrypted, leased transactional mail. SMTP providers are configured explicitly."""
import datetime as dt
import json
import logging
import smtplib
import ssl
import time
from email.message import EmailMessage

log = logging.getLogger('lifeos.mail')

def message(settings, job_id, payload):
    value = EmailMessage()
    value['From'] = settings.email_from
    value['To'] = payload['email']
    value['Message-ID'] = '<'+job_id+'@lifeos-mail>'
    recovery = payload['purpose']=='recovery'
    email_change = payload['purpose']=='email_change'
    value['Subject'] = 'ULADIM: восстановление аккаунта' if recovery else 'ULADIM: подтверждение почты'
    if email_change:value.replace_header('Subject','ULADIM: подтверждение нового адреса')
    value.set_content(('Введите этот код в ULADIM для восстановления аккаунта:\n' if recovery else 'Введите этот код в ULADIM для подтверждения почты:\n')+payload['code']+'\n\nКод одноразовый. Если вы не запрашивали это действие, проигнорируйте письмо.')
    return value

def smtp_send(settings, email):
    context = ssl.create_default_context()
    connection = smtplib.SMTP_SSL(settings.smtp_host,settings.smtp_port,timeout=20,context=context) if settings.smtp_tls=='ssl' else smtplib.SMTP(settings.smtp_host,settings.smtp_port,timeout=20)
    with connection as client:
        if settings.smtp_tls=='starttls': client.starttls(context=context)
        if settings.smtp_username: client.login(settings.smtp_username,settings.smtp_password)
        client.send_message(email)

def deliver_one(backend, settings, send=None):
    now=int(backend.clock())
    with backend.connect() as db:
        # Only ephemeral mail secrets expire; account, financial and sync history never do.
        db.execute('UPDATE email_jobs SET payload=? WHERE expires_at<=? AND delivered_at IS NULL AND octet_length(payload)>0',(b'',now))
        row=db.execute('SELECT * FROM email_jobs WHERE delivered_at IS NULL AND expires_at>? AND next_attempt<=? AND leased_until<=? ORDER BY next_attempt,id LIMIT 1 FOR UPDATE SKIP LOCKED',(now,now,now)).fetchone()
        if not row:return False
        db.execute('UPDATE email_jobs SET leased_until=?,attempts=attempts+1 WHERE id=?',(now+90,row['id']))
    try:
        payload=json.loads(backend.cipher.decrypt(bytes(row['payload'])))
        (send or smtp_send)(settings,message(settings,row['id'],payload))
    except Exception as error:
        # Exception messages may include provider credentials or addresses: log class only.
        with backend.connect() as db:
            db.execute('UPDATE email_jobs SET leased_until=0,next_attempt=?,last_error=? WHERE id=?',(now+min(300,2**min(row['attempts']+1,8)),type(error).__name__,row['id']))
        log.warning('mail_delivery_failed class=%s',type(error).__name__)
        return True
    with backend.connect() as db:
        db.execute('UPDATE email_jobs SET delivered_at=?,leased_until=0,payload=?,last_error=NULL WHERE id=?',(int(backend.clock()),b'',row['id']))
    return True

def main():
    from cryptography.fernet import Fernet
    from .config import Settings
    from .postgres import PostgresBackend
    logging.basicConfig(level=logging.INFO)
    config=Settings.load()
    backend=PostgresBackend(config.database_url,Fernet(config.email_queue_key.encode()),pool_size=2)
    try:
        while True:
            with backend.connect() as db:
                db.execute("INSERT INTO worker_health VALUES('mail',?) ON CONFLICT(name) DO UPDATE SET last_seen=excluded.last_seen",(int(backend.clock()),))
            from .account_lifecycle import AccountLifecycle
            AccountLifecycle(backend).process_one_deletion()
            from pathlib import Path
            Path('/tmp/lifeos-mail.heartbeat').touch()
            if not deliver_one(backend,config):time.sleep(2)
    finally:backend.close()

if __name__=='__main__':main()
