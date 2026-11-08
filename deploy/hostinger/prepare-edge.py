#!/usr/bin/env python3
"""Derive a pre-launch proxy from the existing Compose; never starts API or mail."""
import argparse
import copy
import json
from pathlib import Path
import yaml

parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
source = yaml.safe_load((args.source / 'compose.yaml').read_text())
proxy = copy.deepcopy(source['services']['proxy'])
proxy.pop('depends_on', None)
proxy['environment'] = {
    'LIFEOS_DOMAIN': 'api.getuladim.space',
    'ULADIM_SITE_DOMAIN': 'getuladim.space',
    'ULADIM_CONTROL_DOMAIN': 'control.getuladim.space',
}
proxy['volumes'] = [
    '/etc/uladim/Caddyfile.bootstrap:/etc/caddy/Caddyfile:ro',
    '/etc/uladim/public-index.html:/srv/index.html:ro',
    str(args.source / 'backend/webassets') + ':/srv/assets:ro',
    'caddy_data:/data', 'caddy_config:/config',
]
result = {
    'name': source['name'], 'services': {'proxy': proxy},
    'volumes': {k: source['volumes'][k] for k in ('caddy_data', 'caddy_config')},
    'networks': {'edge': source['networks']['edge']},
}
args.output.write_text(json.dumps(result, indent=2) + chr(10))
