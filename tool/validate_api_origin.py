"""Validate an explicitly configured public app origin without resolving or contacting it."""
import ipaddress
import os
from urllib.parse import urlsplit

def validate(origin):
    value=urlsplit(origin)
    if (any(char.isspace() for char in origin) or value.scheme!='https' or not value.hostname
        or value.username or value.password or value.path not in ('','/') or value.query or value.fragment):
        raise ValueError('LIFEOS_API_ORIGIN must be a credential-free HTTPS origin')
    value.port  # Validate the port without making a network request.
    if value.hostname=='metadata.google.internal':raise ValueError('Service metadata origins are forbidden')
    try:address=ipaddress.ip_address(value.hostname)
    except ValueError:address=None
    if address and (address.is_link_local or str(address)=='fd00:ec2::254'):
        raise ValueError('Service metadata origins are forbidden')
    return origin

if __name__=='__main__':
    try:validate(os.environ['LIFEOS_API_ORIGIN'])
    except (KeyError,ValueError):raise SystemExit('Invalid LIFEOS_API_ORIGIN; build refused')
