"""Require actual rendered account screens; no fallback images or missing locales."""
from pathlib import Path
import json
import struct

root=Path('test/control_goldens')
expected={}
for tag in json.loads(Path('tool/launch_locales.json').read_text()):
    for mode in ('light','dark'):
        for width in ((320,390,430) if tag in ('en','ru') else (320,)):
            screens=('hub','account_access','account_devices','account_support','account_privacy') if tag in ('en','ru') else ('hub',)
            for screen in screens:expected[f'{tag}_{mode}_{width}_{screen}.png']=(width,844)
for name,dimensions in expected.items():
    data=(root/name).read_bytes()
    assert data.startswith(b'\x89PNG\r\n\x1a\n') and len(data)>1024,name
    assert struct.unpack('>II',data[16:24])==dimensions,name
assert {p.name for p in root.glob('*.png')}==set(expected)
print(f'Validated {len(expected)} account screenshots across all 16 locales.')
