"""Serve an isolated browser fixture over HTTPS for Secure session cookies."""
from datetime import datetime, timedelta, timezone
import os
import base64
import hashlib
from pathlib import Path
from ssl import PROTOCOL_TLS_SERVER, SSLContext

from cryptography import x509
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID


def enable_test_tls(server, directory, hostnames=('localhost',)):
    """Install an ephemeral cert for loopback-mapped fixture names; return its SPKI pin."""
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostnames[0])])
    key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(hours=1))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(host) for host in hostnames]), critical=False)
            .sign(key, SHA256()))
    cert_file, key_file = Path(directory) / 'localhost-cert.pem', Path(directory) / 'localhost-key.pem'
    cert_file.write_bytes(cert.public_bytes(Encoding.PEM))
    with open(key_file, 'xb', opener=_private_file) as handle:
        handle.write(key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
    context = SSLContext(PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_file, key_file)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    public_key = key.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    return base64.b64encode(hashlib.sha256(public_key).digest()).decode()


def _private_file(path, flags):
    return os.open(path, flags, 0o600)
