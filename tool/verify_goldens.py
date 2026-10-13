"""Check the completeness and dimensions of Flutter's UI review artifact."""

from pathlib import Path
import struct

root = Path('test/goldens')
expected = {
    f'home_{state}_{theme}_{width}.png': (width, 844)
    for state in ('populated', 'empty')
    for theme in ('light', 'dark')
    for width in (390, 320)
}
expected.update({f'page_{page}.png': (390, 844)
                 for page in ('finances', 'plans', 'notes', 'profile', 'quick_expense')})
expected.update({f'finances_{theme}_{width}.png': (width, 844)
                 for theme, width in [('light', 320), ('dark', 320), ('dark', 390)]})
expected.update({f'premium_{screen}.png': (320, 844) for screen in ('pistachio','sky_dark','appearance','note_editor','task_entry','event_entry')})
expected['home_populated_light_tablet.png'] = (900, 900)
expected.update({f'polish_{screen}_{theme}.png': (430 if screen == 'home_430' else 390 if screen == 'home_scrolled_390' else 320, 844)
                 for theme in ('light', 'dark')
                 for screen in ('home_430','home_scrolled_320','home_scrolled_390','language','repeat','undo','undo_keyboard')})

expected.update({f'offline_{screen}_{theme}_{width}_scaled.png': (width,844) for screen in ('finance','projects','habit','import','permissions','repeat') for theme in ('light','dark') for width in (320,390,430)})

expected.update({f'recovery_{screen}_{state}_{theme}_{width}.png': (width,844) for screen in ('projects','habits','subjects','checklists','wellness','profile','finance') for state in ('empty','active') for theme in ('light','dark') for width in (320,390,430)})

expected.update({f'completion_{screen}_{theme}_{width}.png': (width,844) for screen in ('today','modules','search','import','family','child','money','child_money','account') for theme in ('light','dark') for width in (320,430)})

for name, dimensions in expected.items():
    path = root / name
    data = path.read_bytes()
    if not data.startswith(b'\x89PNG\r\n\x1a\n') or len(data) < 1024:
        raise ValueError(f'Invalid or empty screenshot: {name}')
    actual = struct.unpack('>II', data[16:24])
    if actual != dimensions:
        raise ValueError(f'{name}: expected {dimensions}, got {actual}')

actual_names = {p.name for p in root.glob('*.png')}
if actual_names != set(expected):
    raise ValueError(f'Unexpected screenshot set: {sorted(actual_names ^ set(expected))}')
print(f'Validated {len(expected)} UI screenshots')
