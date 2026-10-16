"""Install the retained release, create real SQLCipher data through its UI,
then update in place. Never uninstall or clear app data. CI emulator only.
"""
import argparse,hashlib,json,os,re,subprocess,time,zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
APP='app.lifeos.lifeos'
OLD_ZIP='97d151438db0ef3515096c9df30755a075d85993a4fea270bf07518703ca4d0f'
PROBE='ULADIM_upgrade_probe_85001'
OUT=Path('upgrade_evidence')

def run(*args,timeout=30):
    return subprocess.check_output(args,timeout=timeout)
def adb(*args,timeout=30):return run('adb','-s','emulator-5554',*args,timeout=timeout)
def previous():
    archive=Path(os.environ['RUNNER_TEMP'])/'uladim-85001.zip'
    with archive.open('wb') as stream:
        subprocess.run(['gh','api','--allow-escape-sequences','repos/pro100umarchikgamer-lgtm/lifeos/actions/artifacts/12005525126/zip'],stdout=stream,check=True,timeout=60)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=OLD_ZIP:raise RuntimeError('Retained release artifact checksum mismatch')
    with zipfile.ZipFile(archive) as z:data=z.read('build/app/outputs/flutter-apk/app-release.apk')
    if hashlib.sha256(data).hexdigest()!='11ac369ea24ee89969a71755798e2143e411b9c8d02f6ffb24fbe72971e10758':raise RuntimeError('Retained APK checksum mismatch')
    target=Path(os.environ['RUNNER_TEMP'])/'uladim-85001.apk';target.write_bytes(data);return target

def xml():
    adb('shell','uiautomator','dump','/sdcard/uladim-window.xml',timeout=15)
    data=adb('exec-out','cat','/sdcard/uladim-window.xml')
    return ET.fromstring(data)
def bounds(node):
    nums=list(map(int,re.findall(r'\d+',node.get('bounds',''))))
    return nums if len(nums)==4 and nums[2]>nums[0] and nums[3]>nums[1] else None

def find(label=None,editable=False):
    root=ET.Element('hierarchy')
    deadline=time.monotonic()+60
    while time.monotonic()<deadline:
        try:root=xml()
        except (ET.ParseError,subprocess.SubprocessError):
            time.sleep(.5)
            continue
        nodes=[]
        for node in root.iter('node'):
            text=(node.get('text','')+'\n'+node.get('content-desc','')).strip()
            match=(node.get('class')=='android.widget.EditText') if editable else any(part.strip()==label for part in text.splitlines())
            if match and node.get('enabled')!='false' and bounds(node):nodes.append(node)
        if nodes:
            nodes.sort(key=lambda n:n.get('clickable')!='true');return nodes[0]
        time.sleep(.5)
    OUT.mkdir(exist_ok=True);(OUT/'missing-control.xml').write_bytes(ET.tostring(root))
    raise RuntimeError('Release UI control not found: '+str(label or 'editable field'))
def tap_node(node):
    x1,y1,x2,y2=bounds(node);adb('shell','input','tap',str((x1+x2)//2),str((y1+y2)//2));time.sleep(.4)
def tap(label=None,editable=False):tap_node(find(label,editable))
def legacy_add_node(root,width,height):
    candidates=[]
    for node in root.iter('node'):
        rect=bounds(node)
        if node.get('clickable')!='true' or node.get('enabled')=='false' or not rect:continue
        x1,y1,x2,y2=rect
        if abs((x1+x2)/2-width/2)<width*.08 and y1>height*.65 and x2-x1<width*.3 and y2-y1<height*.2:candidates.append(node)
    if len(candidates)!=1:raise RuntimeError('Cannot identify retained 85001 add button: '+str(len(candidates)))
    return candidates[0]
def legacy_editor(kind):
    # Retained 85001 has no accessibility label on its persistent + button.
    # Derive its exact hit rectangle from the actual UI tree, never a fixed coordinate.
    find('Today')
    width,height=map(int,re.findall(r'(\d+)x(\d+)',adb('shell','wm','size').decode())[-1])
    tap_node(legacy_add_node(xml(),width,height));tap(kind)
def screenshot(name):
    OUT.mkdir(exist_ok=True);(OUT/(name+'.png')).write_bytes(adb('exec-out','screencap','-p'))
def start():
    adb('shell','am','force-stop',APP);adb('shell','am','start','-n',APP+'/.MainActivity');time.sleep(2)
    OUT.mkdir(exist_ok=True);(OUT/('startup-'+str(time.time_ns())+'.txt')).write_bytes(adb('logcat','-d'))
def uid():
    listing=adb('shell','cmd','package','list','packages','-U',APP)
    found=re.search(rb'^package:app\.lifeos\.lifeos\s+uid:(\d+)\s*$',listing,re.M)
    if not found:raise RuntimeError('Cannot read installed package UID: '+listing.decode())
    return found[1].decode()
def scroll(up=True):
    raw=adb('shell','wm','size').decode();width,height=map(int,re.findall(r'(\d+)x(\d+)',raw)[-1]);x=str(width//2)
    y1,y2=(int(height*.78),int(height*.30)) if up else (int(height*.30),int(height*.78))
    adb('shell','input','swipe',x,str(y1),x,str(y2),'400');time.sleep(.4)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--download',action='store_true');parser.add_argument('--probe',action='store_true');parser.add_argument('--candidate',type=Path);args=parser.parse_args()
    if args.download:print('Retained signed 85001 verified:',previous());return
    assert args.candidate and args.candidate.is_file()
    old=Path(os.environ['RUNNER_TEMP'])/'uladim-85001.apk';assert old.is_file()
    adb('shell','cmd','alarm','set-timezone','Europe/Moscow')
    adb('install','-r',str(old),timeout=90);owner=uid();start()
    legacy_editor('Task');tap(editable=True);adb('shell','input','text',PROBE);adb('shell','input','keyevent','4');tap('Save');tap('Plans');find(PROBE)
    screenshot('85001-control-task')
    for kind,amount in [('Expense','12.50'),('Income','100.00')]:
        tap('Today');legacy_editor(kind);tap(editable=True);adb('shell','input','text',amount);adb('shell','input','keyevent','4');tap('Save')
    adb('install','-r',str(args.candidate),timeout=90)
    assert uid()==owner,'Package identity changed'
    installed=adb('shell','dumpsys','package',APP).decode();version=int(re.search(r'versionCode=(\d+)',installed)[1])
    assert version==85001 if args.probe else version>85001
    if not args.probe:adb('shell','cmd','alarm','set-timezone','Etc/UTC')
    start();tap('Plans');find(PROBE);screenshot('upgraded-control-task')
    start();tap('Plans');find(PROBE)
    evidence={'previousVersionCode':85001,'installedVersionCode':version,'samePackageUid':True,'syntheticTaskSurvivesUpdateAndRestart':True,'uninstallOrDataClearUsed':False,'baselineDeviceTimezone':'Europe/Moscow','candidateDeviceTimezone':'Europe/Moscow' if args.probe else 'Etc/UTC'}
    if not args.probe:
        for theme in ['light','dark']:
            adb('shell','cmd','uimode','night','no' if theme=='light' else 'yes');time.sleep(.7)
            tap('Today');screenshot('today-'+theme)
            tap('Finances');screenshot('finances-'+theme);scroll();screenshot('categories-'+theme);scroll(False)
            tap('Profile');tap('Account and family');tap('Create account');screenshot('registration-'+theme)
            adb('shell','input','keyevent','4')
        evidence['screenshots']='real Android 35 release app; synthetic data only'
    OUT.mkdir(exist_ok=True);(OUT/'upgrade-result.json').write_text(json.dumps(evidence,indent=2)+'\n');print(json.dumps(evidence))
if __name__=='__main__':
    try:main()
    except Exception:
        try:
            OUT.mkdir(exist_ok=True)
            (OUT/'failure-logcat.txt').write_bytes(adb('logcat','-d'))
            screenshot('failure')
        except Exception:pass
        raise
