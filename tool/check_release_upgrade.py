"""Install the retained release, create real SQLCipher data through its UI,
then update in place. Never uninstall or clear app data. CI emulator only.
"""
import argparse,hashlib,json,os,re,subprocess,time,zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
APP='app.lifeos.lifeos'
OLD_ZIP='97d151438db0ef3515096c9df30755a075d85993a4fea270bf07518703ca4d0f'
PROBE='ULADIM_upgrade_probe_112001'
OUT=Path('upgrade_evidence')

def run(*args,timeout=30):
    return subprocess.check_output(args,timeout=timeout)
def adb(*args,timeout=30):return run('adb','-s','emulator-5554',*args,timeout=timeout)
def previous():
    source='f8632cdd5cf4dad40f0163a44183016d23121abd'
    target=Path(os.environ['RUNNER_TEMP'])/'uladim-baseline-112001'
    target.mkdir(exist_ok=True)
    subprocess.run(['gh','run','download','38883235405','--repo','pro100umarchikgamer-lgtm/lifeos','--name','lifeos-release-test-apk-'+source,'--dir',str(target)],check=True,timeout=90)
    original=target/'build/app/outputs/flutter-apk/app-release.apk'
    if hashlib.sha256(original.read_bytes()).hexdigest()!='0594d97502523901e9d8b7d6b0ceb5ec995f7379b66faabd886f8f75ea58908e':raise RuntimeError('Retained APK112001 checksum mismatch')
    identity=dict(line.split('=',1) for line in (target/'apk-identity.txt').read_text().splitlines())
    assert identity['versionCode']=='112001' and identity['commit']==source
    assert identity['applicationId']==APP and identity['certificateSHA256']==Path('docs/ANDROID_TEST_CERT.sha256').read_text().strip()
    path=Path(os.environ['RUNNER_TEMP'])/'uladim-112001.apk'
    import shutil
    shutil.copyfile(original,path)
    return path

def xml():
    adb('shell','uiautomator','dump','/sdcard/uladim-window.xml',timeout=15)
    data=adb('exec-out','cat','/sdcard/uladim-window.xml')
    return ET.fromstring(data)
def bounds(node):
    nums=list(map(int,re.findall(r'\d+',node.get('bounds',''))))
    return nums if len(nums)==4 and nums[2]>nums[0] and nums[3]>nums[1] else None

def find(label=None,editable=False,reveal=False):
    root=ET.Element('hierarchy')
    deadline=time.monotonic()+60
    swipes=0
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
        if reveal and swipes<8:
            scroll();swipes+=1
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
    # Baseline112001 labels its Add action; use its actual accessibility semantics.
    find('Today')
    tap('Add');tap(kind)
def enter_text(value):
    # Autofocus/IME can move the field while its old bounds are being tapped.
    # Replace any existing input and require the exact value before saving.
    tap(editable=True)
    adb('shell','input','keyevent','KEYCODE_MOVE_END')
    adb('shell','input','keyevent',*(['KEYCODE_DEL']*64))
    adb('shell','input','text',value)
    actual=find(editable=True).get('text','')
    assert actual==value, f'Fixture text mismatch: {actual!r} != {value!r}'
    adb('shell','input','keyevent','4')
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
def device_timezone(zone):
    adb('shell','settings','put','global','auto_time_zone','0')
    adb('shell','cmd','alarm','set-timezone',zone)
    actual=adb('shell','getprop','persist.sys.timezone').decode().strip()
    assert actual==zone, f'Emulator timezone mismatch: {actual} != {zone}'
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--download',action='store_true');parser.add_argument('--probe',action='store_true');parser.add_argument('--candidate',type=Path);args=parser.parse_args()
    if args.download:print('Retained signed 112001 verified:',previous());return
    assert args.candidate and args.candidate.is_file()
    old=Path(os.environ['RUNNER_TEMP'])/'uladim-112001.apk';assert old.is_file()
    device_timezone('Europe/Moscow')
    adb('install','-r',str(old),timeout=90);owner=uid();start()
    legacy_editor('Task');enter_text(PROBE);tap('Save');tap('Plans');find(PROBE,reveal=True)
    screenshot('112001-control-task')
    for kind,amount in [('Expense','12.50'),('Income','100.00')]:
        tap('Today');legacy_editor(kind);enter_text(amount);tap('Save')
    adb('install','-r',str(args.candidate),timeout=90)
    assert uid()==owner,'Package identity changed'
    installed=adb('shell','dumpsys','package',APP).decode();version=int(re.search(r'versionCode=(\d+)',installed)[1])
    assert version==112001 if args.probe else version>112001
    if not args.probe:device_timezone('Etc/UTC')
    start();tap('Plans');find(PROBE,reveal=True);screenshot('upgraded-control-task')
    start();tap('Plans');find(PROBE,reveal=True)
    evidence={'previousVersionCode':112001,'installedVersionCode':version,'samePackageUid':True,'syntheticTaskSurvivesUpdateAndRestart':True,'uninstallOrDataClearUsed':False,'baselineDeviceTimezone':'Europe/Moscow','candidateDeviceTimezone':'Europe/Moscow' if args.probe else 'Etc/UTC'}
    if not args.probe:
        for theme in ['light','dark']:
            adb('shell','cmd','uimode','night','no' if theme=='light' else 'yes');time.sleep(.7)
            tap('Today');screenshot('today-'+theme)
            tap('Finances');find('Finances');screenshot('finances-'+theme);
            amounts=ET.tostring(xml(),encoding='unicode')
            assert '12.50' in amounts and '100.00' in amounts, 'Synthetic financial amounts did not survive the update'
            scroll();screenshot('categories-'+theme);scroll(False)
            tap('Today');tap('Profile');tap('Account and family');tap('Create account');screenshot('registration-'+theme)
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
