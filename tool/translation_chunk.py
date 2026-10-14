"""Stage reviewed UI translations without installing incomplete locale packs."""
import json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
base=json.loads((root/'assets/locales/en.json').read_text())
data=json.load(sys.stdin);start=data['start'];keys=list(base['strings'])[start:start+data['count']]
for tag,lines in data['locales'].items():
 values=lines.split('\n');assert len(values)==len(keys),(tag,len(values),len(keys))
 p=root/'tool/localization_workbench'/f'{tag}.json';previous=json.loads(p.read_text()) if p.exists() else {}
 for k,v in zip(keys,values):
  assert v.strip(),(tag,k)
  previous[k]=v
 p.write_text(json.dumps(previous,ensure_ascii=False,indent=2)+'\n')
 print(tag,len(previous),'/',len(base['strings']))
