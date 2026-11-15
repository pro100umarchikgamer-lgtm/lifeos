"""Durable, encrypted, leased transactional mail. SMTP providers are configured explicitly."""
import datetime as dt
import json
import logging
import re
import smtplib
import ssl
import time
from email.message import EmailMessage
from .notification_copy import packs
from .request_locale import normalize_locale

log = logging.getLogger('lifeos.mail')

# Exact legacy Russian copy also keeps old queued jobs readable if a pack is incomplete.
_MAIL_RU = {'mail_subject_verify': 'ULADIM: подтверждение почты',
 'mail_subject_recovery': 'ULADIM: восстановление аккаунта',
 'mail_subject_email_change': 'ULADIM: подтверждение нового адреса',
 'mail_subject_early_verify': 'ULADIM: подтвердите заявку',
 'mail_subject_early_invite': 'ULADIM: приглашение в закрытый тест',
 'mail_subject_early_rejected': 'ULADIM: решение по заявке',
 'mail_body_verify': 'Введите этот код в ULADIM для подтверждения почты:\n{code}',
 'mail_body_recovery': 'Введите этот код в ULADIM для восстановления аккаунта:\n{code}',
 'mail_body_email_change': 'Введите этот код в ULADIM для подтверждения почты:\n{code}',
 'mail_body_early_verify': 'Подтвердите заявку на https://getuladim.space/early-access, введя этот '
                           'одноразовый код (15 минут):\n'
                           '{code}\n'
                           'После подтверждения можно проверить статус и отменить заявку. Заявка не создаёт '
                           'аккаунт.',
 'mail_body_early_invite': 'Ваша заявка одобрена. Создайте аккаунт на https://getuladim.space/account с этим '
                           'приглашением (7 дней):\n'
                           '{code}',
 'mail_body_early_rejected': 'Сейчас мы не можем включить вас в закрытый тест ULADIM. Аккаунт не создан. '
                             'Статус и отмена заявки: https://getuladim.space/early-access',
 'mail_code_single_use': 'Код одноразовый.',
 'mail_unrequested': 'Если вы не запрашивали это действие, проигнорируйте письмо.'}


def _copy(key, locale):
    # Only fixed mail keys are accepted; no user content is translated.
    fallback = _MAIL_RU[key]
    value = packs().get(locale, {}).get('strings', {}).get(key, fallback)
    if not isinstance(value, str) or not value.strip():
        return fallback
    if value.count('{code}') != fallback.count('{code}') or re.findall(r'\{[^{}]+\}', value) != re.findall(r'\{[^{}]+\}', fallback):
        return fallback
    if '{' in value.replace('{code}', '') or '}' in value.replace('{code}', ''):
        return fallback
    if sorted(url.rstrip('.,;:!?)]') for url in re.findall(r'https?://[^\s]+', value)) != sorted(url.rstrip('.,;:!?)]') for url in re.findall(r'https?://[^\s]+', fallback)):
        return fallback
    if key.startswith('mail_subject_') and ('\n' in value or '\r' in value):
        return fallback
    return value


def message(settings, job_id, payload):
    value = EmailMessage()
    value['From'] = settings.email_from
    value['To'] = payload['email']
    value['Message-ID'] = '<'+job_id+'@lifeos-mail>'
    locale = normalize_locale(payload.get('locale'))
    purpose = payload['purpose']
    early = purpose.startswith('early_')
    suffix = purpose if early else 'recovery' if purpose == 'recovery' else 'email_change' if purpose == 'email_change' else 'verify'
    value['Subject'] = _copy('mail_subject_' + suffix, locale)
    content = _copy('mail_body_' + suffix, locale)
    if '{code}' in content:
        content = content.replace('{code}', payload['code'])
    footer = _copy('mail_unrequested', locale)
    if not early:
        footer = _copy('mail_code_single_use', locale) + ' ' + footer
    value.set_content(content + '\n\n' + footer)
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
        subject = row.get('user_id')
        if not subject:
            # Compatibility for jobs queued before migration 019.
            pending = json.loads(backend.cipher.decrypt(bytes(row['payload'])))
            with backend.connect() as db:
                from .account_erasure import mail_subject
                owner=mail_subject(db,pending.get('email'),pending.get('code'),pending.get('purpose'))
                subject=owner['user_id'] if owner else None
        # A lease is not permission to send after account erasure. Re-read it
        # under the same per-subject lock used by the eraser, and keep that lock
        # through SMTP. PostgreSQL does not hold the global sync lock here.
        with backend.delivery_transaction(subject) as db:
            current=db.execute('SELECT * FROM email_jobs WHERE id=? AND delivered_at IS NULL AND expires_at>? AND octet_length(payload)>0', (row['id'], int(backend.clock()))).fetchone()
            if not current: return True
            if subject:
                backend._account_available(db, subject)
            payload=json.loads(backend.cipher.decrypt(bytes(current['payload'])))
            (send or smtp_send)(settings,message(settings,row['id'],payload))
            db.execute('UPDATE email_jobs SET delivered_at=?,leased_until=0,payload=?,last_error=NULL WHERE id=?',(int(backend.clock()),b'',row['id']))
    except Exception as error:
        # Exception messages may include provider credentials or addresses: log class only.
        with backend.connect() as db:
            db.execute('UPDATE email_jobs SET leased_until=0,next_attempt=?,last_error=? WHERE id=?',(now+min(300,2**min(row['attempts']+1,8)),type(error).__name__,row['id']))
        log.warning('mail_delivery_failed class=%s',type(error).__name__)
        return True
    return True

def main():
    from cryptography.fernet import Fernet
    from .config import Settings
    from .postgres import PostgresBackend
    logging.basicConfig(level=logging.INFO)
    config=Settings.load()
    backend=PostgresBackend(config.database_url,Fernet(config.email_queue_key.encode()),pool_size=2)
    from .account_erasure import initialize
    initialize(backend, config.account_erasure_ledger, config.account_erasure_ack_socket)
    from .record_erasure import initialize as initialize_record_erasure
    initialize_record_erasure(backend,config.record_erasure_ledger,config.record_erasure_ack_socket,config.record_erasure_required)
    from .web_push import WebPush
    push=WebPush(backend,config.site_origin)
    try:
        while True:
            from .account_erasure import prune_ephemeral
            prune_ephemeral(backend)
            with backend.connect() as db:
                db.execute("INSERT INTO worker_health VALUES('mail',?) ON CONFLICT(name) DO UPDATE SET last_seen=excluded.last_seen",(int(backend.clock()),))
            from .account_lifecycle import AccountLifecycle
            AccountLifecycle(backend).process_one_deletion()
            # One bounded retry also closes a crash between committed consent
            # and the first root IPC; it never accepts a new deletion request.
            if int(backend.clock())>=getattr(backend,'_record_erasure_retry_at',0):
                try:
                    from .record_erasure import resume_pending
                    resume_pending(backend)
                except Exception as error:
                    backend._record_erasure_retry_at=int(backend.clock())+30
                    log.warning('record_erasure_retry_failed class=%s',type(error).__name__)
            from pathlib import Path
            Path('/tmp/lifeos-mail.heartbeat').touch()
            mail_work=deliver_one(backend,config)
            try:
                push_work=push.tick()
            except Exception as error:
                # Independent queues: a provider/notification problem must not
                # stop verification and recovery email. Never log payloads.
                log.warning('push_tick_failed class=%s',type(error).__name__)
                push_work=False
            if not mail_work and not push_work:time.sleep(2)
    finally:backend.close()

if __name__=='__main__':main()

