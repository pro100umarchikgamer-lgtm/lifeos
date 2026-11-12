"""Bundle the visual layers into the existing allowlisted stylesheet."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'backend/webassets'
marker='/* FOCUS_VISUAL_LAYERS */'
base=(root/'design.css').read_text().split(marker)[0].rstrip()
files=['app/focus.css','app/workspace-sections.css','public-focus.css','app/import-presentation.css']
layers=[(name,(root/name).read_text()) for name in files if (root/name).exists()]
(root/'design.css').write_text(base+'\n\n'+marker+'\n'+'\n'.join('/* '+name+' */\n'+css for name,css in layers))
print('Bundled',len(layers),'visual layers')
