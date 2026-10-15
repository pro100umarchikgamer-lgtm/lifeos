"""Explicit configuration; no cloud SDK, metadata lookup or implicit credentials."""
from dataclasses import dataclass
import ipaddress
import os
import re
from cryptography.fernet import Fernet

@dataclass(frozen=True)
class Settings:
    database_url: str
    email_queue_key: str
    rate_limit_key: str
    smtp_host: str
    smtp_port: int
    smtp_tls: str
    smtp_username: str
    smtp_password: str
    email_from: str
    trusted_proxy_cidrs: str = '172.30.30.0/24'
    require_https: bool = True
    pool_size: int = 4
    registration_mode: str = 'closed'
    registration_allowlist: tuple[str, ...] = ()

    @classmethod
    def load(cls, env=None):
        e = os.environ if env is None else env
        if e.get('REQUIRE_HTTPS','true') not in ('true','false'):raise ValueError('Invalid REQUIRE_HTTPS')
        def required(name):
            value = e.get(name, '')
            if not value.strip(): raise ValueError('Missing configuration: '+name)
            return value
        value = cls(database_url=required('DATABASE_URL'), email_queue_key=required('EMAIL_QUEUE_KEY'),
            rate_limit_key=required('RATE_LIMIT_KEY'), smtp_host=required('SMTP_HOST'),
            smtp_port=int(e.get('SMTP_PORT','587')), smtp_tls=e.get('SMTP_TLS','starttls'),
            smtp_username=e.get('SMTP_USERNAME',''), smtp_password=e.get('SMTP_PASSWORD',''),
            email_from=required('EMAIL_FROM'), trusted_proxy_cidrs=e.get('TRUSTED_PROXY_CIDRS','172.30.30.0/24'),
            require_https=e.get('REQUIRE_HTTPS','true')=='true', pool_size=int(e.get('DB_POOL_SIZE','4')),
            registration_mode=e.get('REGISTRATION_MODE','closed'),
            registration_allowlist=tuple(v.strip().casefold() for v in e.get('REGISTRATION_ALLOWLIST','').split(',') if v.strip()))
        if value.registration_mode not in ('closed','open'): raise ValueError('Invalid REGISTRATION_MODE')
        if any(len(v)>254 or not re.fullmatch(r'[^\s@,]+@[^\s@,]+\.[^\s@,]+',v) or '*' in v for v in value.registration_allowlist):
            raise ValueError('REGISTRATION_ALLOWLIST requires exact email addresses')
        if not value.database_url.startswith(('postgresql://','postgres://')): raise ValueError('PostgreSQL DATABASE_URL required')
        Fernet(value.email_queue_key.encode())
        if len(value.rate_limit_key)<32: raise ValueError('RATE_LIMIT_KEY must contain at least 32 characters')
        if not 1<=value.pool_size<=8 or not 1<=value.smtp_port<=65535: raise ValueError('Invalid resource limits')
        if value.smtp_tls not in ('starttls','ssl','none'): raise ValueError('SMTP_TLS must be starttls or ssl')
        if value.smtp_tls=='none' and value.smtp_host not in ('localhost','127.0.0.1','mailpit'): raise ValueError('Unencrypted SMTP is restricted to isolated local development')
        if '\r' in value.email_from or '\n' in value.email_from or '@' not in value.email_from: raise ValueError('Invalid EMAIL_FROM')
        for cidr in value.trusted_proxy_cidrs.split(','): ipaddress.ip_network(cidr.strip())
        return value
