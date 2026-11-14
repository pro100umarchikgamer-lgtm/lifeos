"""Install the retained release, create real SQLCipher data through its UI,
then update in place. Never uninstall or clear app data. CI emulator only.
"""
import argparse,hashlib,json,os,re,subprocess,time,zipfile
from decimal import Decimal
from pathlib import Path
import xml.etree.ElementTree as ET
APP='app.lifeos.lifeos'
OLD_ZIP='97d151438db0ef3515096c9df30755a075d85993a4fea270bf07518703ca4d0f'
PROBE='ULADIM_upgrade_probe_112001'
ACCEPTED_PROBE='ULADIM_direct_312001_upgrade'
ACCEPTED_VERSION=312001
ACCEPTED_SHA256='66d123cef79f85b7b2665bdcad0e6309db4a694e9a5076ed871450154c762872'
OUT=Path('upgrade_evidence')

def run(*args,timeout=30):
    return subprocess.check_output(args,timeout=timeout)
def adb(*args,timeout=30):return run('adb','-s','emulator-5554',*args,timeout=timeout)
RETAINED_RELEASES={
    112001:('f8632cdd5cf4dad40f0163a44183016d23121abd','38883235405','0594d97502523901e9d8b7d6b0ceb5ec995f7379b66faabd886f8f75ea58908e'),
    134001:('6acbde34f499d7c740322687416abc3aa542f9ac','38984254821','a7f93159a138e464227fa2259d9c54c67063a280708e8dafbd95c27ec3ab8356'),
    303001:('dd2912af8b53d284494afa55c1cf39047bbe07fe','43329676603','e53e35e7c36e5ee9622af668f8db6073effcfeb774635fa0aeca90ce9c875142'),
    ACCEPTED_VERSION:('84b0bdf2c6d54132691d22323553496f6b3b1d43','43367262708',ACCEPTED_SHA256),
}
def previous(baseline=112001,supplied=None):
    source,run_id,digest=RETAINED_RELEASES[baseline]
    target=Path(os.environ['RUNNER_TEMP'])/f'uladim-baseline-{baseline}'
    target.mkdir(exist_ok=True)
    if supplied is None:
        subprocess.run(['gh','run','download',run_id,'--repo','pro100umarchikgamer-lgtm/lifeos','--name','lifeos-release-test-apk-'+source,'--dir',str(target)],check=True,timeout=90)
        original=target/'build/app/outputs/flutter-apk/app-release.apk'
        identity=dict(line.split('=',1) for line in (target/'apk-identity.txt').read_text().splitlines())
        assert identity['versionCode']==str(baseline) and identity['commit']==source
        assert identity['applicationId']==APP and identity['certificateSHA256']==Path('docs/ANDROID_TEST_CERT.sha256').read_text().strip()
    else:original=Path(supplied)
    # A local file must match the same independently verified signed bytes.
    assert hashlib.sha256(original.read_bytes()).hexdigest()==digest,f'Retained APK{baseline} bytes changed'
    path=Path(os.environ['RUNNER_TEMP'])/f'uladim-{baseline}.apk'
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
def tap(label=None,editable=False,reveal=False):tap_node(find(label,editable,reveal))
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

def verify_financial_summary(root):
    # The UI deliberately renders whole amounts as $100, not $100.00.
    # Compare exact currency values, never unanchored numeric substrings.
    amounts=set()
    for node in root.iter('node'):
        for attribute in ('text','content-desc'):
            for value in re.findall(r'(?<![\w$])\$(-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?)(?![\d.,])',node.get(attribute,'')):
                amounts.add(Decimal(value.replace(',','')))
    expected={Decimal('12.50'),Decimal('100.00'),Decimal('87.50')}
    assert expected <= amounts, f'Synthetic financial values missing after update: {expected-amounts}'

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
    deadline=time.monotonic()+10
    actual=adb('shell','getprop','persist.sys.timezone').decode().strip()
    # AlarmManager acknowledges the request before the timezone property settles.
    while actual!=zone and time.monotonic()<deadline:
        time.sleep(0.25)
        actual=adb('shell','getprop','persist.sys.timezone').decode().strip()
    assert actual==zone, f'Emulator timezone mismatch: {actual} != {zone}'

def verify_active_test_notification(report):
    """Require a posted app notification in the active OS list, not history."""
    match=re.search(r'^\s*Notification List:\s*$',report,re.M)
    assert match, 'Android active notification list not found'
    active=report[match.end():]
    active=re.split(r'^\s*(?:Enqueued Notification List|Snoozed notifications|Historical notifications|Ranking Config):',active,1,flags=re.M)[0]
    for block in re.split(r'(?=^[ \t]*NotificationRecord\()',active,flags=re.M):
        header=block.splitlines()[0] if block.splitlines() else ''
        if not re.search(r'\bpkg='+re.escape(APP)+r'(?:\s|$)',header):continue
        if not re.search(r'\bid=1(?:\s|$)',header) or not re.search(r'\btag=test(?:\s|$)',header):continue
        if not re.search(r"(?:channel=lifeos\.important(?:\s|\)|$)|mId='lifeos\.important')",block):continue
        importance=re.search(r'\bimportance=(\d+)',header) or re.search(r'\bmImportance=(\d+)',block)
        if importance and int(importance[1])>=4:return
    raise AssertionError('Fresh app test notification missing from the active high-priority OS channel')

def notification_evidence():
    # The UI action invokes the real Kotlin bridge. Its posted result checks a
    # fresh active notification, then dumpsys independently confirms OS state.
    copy=json.loads(Path('assets/locales/en.json').read_text())['strings']
    adb('shell','pm','grant',APP,'android.permission.POST_NOTIFICATIONS')
    installed=adb('shell','dumpsys','package',APP).decode()
    assert re.search(r'android\.permission\.POST_NOTIFICATIONS:\s*granted=true',installed), 'Notification runtime permission not granted'
    start();tap('Profile');tap(copy['notifications'],reveal=True)
    tap(copy['test_notification'],reveal=True)
    find(copy['test_notification_posted'])
    screenshot('notification-posted-result')
    report=adb('shell','dumpsys','notification','--noredact').decode()
    OUT.mkdir(exist_ok=True);(OUT/'notification-dumpsys.txt').write_text(report)
    verify_active_test_notification(report)
    adb('shell','cmd','statusbar','expand-notifications');time.sleep(.7)
    screenshot('notification-shade');(OUT/'notification-shade.xml').write_bytes(ET.tostring(xml()))
    adb('shell','cmd','statusbar','collapse')
    return {'runtimePermissionGranted':True,'freshBridgeResult':'posted','activeOsNotification':True,'channel':'lifeos.important','importance':'high','physicalSoundOrBannerVerified':False}

def capture_candidate_pages(theme):
    # Populated Today/Tasks/Finances and empty Calendar/Notes are all real app
    # screens over the retained SQLCipher records, not generated mockups.
    for label in ['Today','Tasks','Calendar','Notes','Finances','Profile']:
        start();tap(label);screenshot(label.lower()+'-'+theme)
        tree=xml();(OUT/(label.lower()+'-'+theme+'.xml')).write_bytes(ET.tostring(tree))
        if label=='Tasks':find(PROBE,reveal=True)
        if label=='Finances':
            verify_financial_summary(tree)
            scroll();screenshot('categories-'+theme);scroll(False)

def arguments(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--baseline',type=int,choices=RETAINED_RELEASES,default=112001)
    parser.add_argument('--baseline-file',type=Path)
    parser.add_argument('--through-version',type=int,choices=[303001])
    parser.add_argument('--through-file',type=Path)
    parser.add_argument('--accepted-version',type=int,choices=[ACCEPTED_VERSION])
    parser.add_argument('--accepted-file',type=Path)
    parser.add_argument('--download',action='store_true')
    parser.add_argument('--probe',action='store_true')
    parser.add_argument('--candidate',type=Path)
    args=parser.parse_args(argv)
    assert not args.through_file or args.through_version,'--through-file needs --through-version'
    assert not args.accepted_file or args.accepted_version,'--accepted-file needs --accepted-version'
    assert not args.through_version or (not args.probe and args.baseline<args.through_version),'Intermediate version must be newer than baseline'
    assert not args.accepted_version or (not args.probe and args.accepted_version>max(args.baseline,args.through_version or 0)),'Accepted baseline must be the final pre-candidate upgrade'
    return args

def accepted_baseline(path,owner):
    # This is the actual accepted APK, installed in place with the retained DB.
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==ACCEPTED_SHA256,'Accepted312 APK bytes changed'
    adb('install','-r',str(path),timeout=90)
    assert uid()==owner,'Package identity changed before accepted312 stage'
    installed=adb('shell','dumpsys','package',APP)
    assert int(re.search(rb'versionCode=(\d+)',installed)[1])==ACCEPTED_VERSION,'Accepted312 version not installed'
    OUT.mkdir(exist_ok=True);(OUT/'accepted-312001-package.txt').write_bytes(installed)
    start();tap('Tasks');find(PROBE,reveal=True)
    screenshot('accepted-312001-control-task');(OUT/'accepted-312001-control-task.xml').write_bytes(ET.tostring(xml()))
    start();tap('Finances');verify_financial_summary(xml())
    screenshot('accepted-312001-finances');(OUT/'accepted-312001-finances.xml').write_bytes(ET.tostring(xml()))
    # Create data using accepted312's own redesigned UI, not only the older seeder.
    start();legacy_editor('Task');enter_text(ACCEPTED_PROBE);tap('Save')
    start();tap('Tasks');find(ACCEPTED_PROBE,reveal=True)
    screenshot('accepted-312001-created-task');(OUT/'accepted-312001-created-task.xml').write_bytes(ET.tostring(xml()))
    return {'acceptedBaselineVersionCode':ACCEPTED_VERSION,'acceptedBaselineApkSha256':ACCEPTED_SHA256,
            'acceptedBaselineTaskAndFinancialDataRetained':True,'directUpgradeFromVersionCode':ACCEPTED_VERSION}

def main():
    args=arguments()
    if args.download:
        print('Retained signed baseline verified:',args.baseline,previous(args.baseline,args.baseline_file))
        if args.through_version:print('Retained signed intermediate verified:',args.through_version,previous(args.through_version,args.through_file))
        if args.accepted_version:print('Accepted signed pre-candidate baseline verified:',args.accepted_version,previous(args.accepted_version,args.accepted_file))
        return
    assert args.candidate and args.candidate.is_file()
    old=previous(args.baseline,args.baseline_file) if args.baseline_file else Path(os.environ['RUNNER_TEMP'])/f'uladim-{args.baseline}.apk';assert old.is_file()
    device_timezone('Europe/Moscow')
    adb('install','-r',str(old),timeout=90);owner=uid();start()
    legacy_editor('Task');enter_text(PROBE);tap('Save');tap('Tasks' if args.baseline>=ACCEPTED_VERSION else 'Plans');find(PROBE,reveal=True)
    screenshot(str(args.baseline)+'-control-task')
    for kind,amount in [('Expense','12.50'),('Income','100.00')]:
        tap('Today');legacy_editor(kind);enter_text(amount);tap('Save')
    if args.through_version:
        intermediate=previous(args.through_version,args.through_file) if args.through_file else Path(os.environ['RUNNER_TEMP'])/f'uladim-{args.through_version}.apk'
        assert intermediate.is_file()
        adb('install','-r',str(intermediate),timeout=90);assert uid()==owner,'Package identity changed in intermediate upgrade'
        installed=adb('shell','dumpsys','package',APP).decode();assert int(re.search(r'versionCode=(\d+)',installed)[1])==args.through_version
        start();tap('Plans');find(PROBE,reveal=True);screenshot('intermediate-'+str(args.through_version)+'-control-task')
        tap('Finances');verify_financial_summary(xml())
    accepted={}
    if args.accepted_version:
        path=previous(args.accepted_version,args.accepted_file) if args.accepted_file else Path(os.environ['RUNNER_TEMP'])/f'uladim-{args.accepted_version}.apk'
        assert path.is_file()
        accepted=accepted_baseline(path,owner)
    result=adb('install','-r',str(args.candidate),timeout=90)
    if args.accepted_version:(OUT/'direct-312001-to-candidate-install.txt').write_bytes(result)
    assert uid()==owner,'Package identity changed'
    installed=adb('shell','dumpsys','package',APP).decode();version=int(re.search(r'versionCode=(\d+)',installed)[1])
    assert version==args.baseline if args.probe else version>max(args.baseline,args.through_version or 0,args.accepted_version or 0)
    modern=not args.probe and version>303001
    tasks='Tasks' if modern else 'Plans'
    if not args.probe:device_timezone('Etc/UTC')
    start();tap(tasks);find(PROBE,reveal=True);screenshot('upgraded-control-task')
    start();tap(tasks);find(PROBE,reveal=True)
    if args.accepted_version:
        start();tap('Tasks');find(ACCEPTED_PROBE,reveal=True)
        screenshot('upgraded-312001-created-task');(OUT/'upgraded-312001-created-task.xml').write_bytes(ET.tostring(xml()))
        start();tap('Tasks');find(ACCEPTED_PROBE,reveal=True)
        (OUT/'direct-upgrade-package.txt').write_text(installed)
        accepted['acceptedBaselineCreatedTaskRetainedAfterRestart']=True
        accepted['upgradeVersionChain']=[args.baseline,*([args.through_version] if args.through_version else []),args.accepted_version,version]
    evidence={'previousVersionCode':args.baseline,'installedVersionCode':version,'samePackageUid':True,'syntheticTaskSurvivesUpdateAndRestart':True,'uninstallOrDataClearUsed':False,'baselineDeviceTimezone':'Europe/Moscow','candidateDeviceTimezone':'Europe/Moscow' if args.probe else 'Etc/UTC'}
    evidence.update(accepted)
    if args.through_version:evidence['intermediateVersionCode']=args.through_version;evidence['intermediateTaskAndFinancialDataRetained']=True
    if not args.probe:
        for theme in ['light','dark']:
            adb('shell','cmd','uimode','night','no' if theme=='light' else 'yes');time.sleep(.7)
            if modern:
                capture_candidate_pages(theme)
                continue
            tap('Today');screenshot('today-'+theme)
            tap('Finances');find('Finances');screenshot('finances-'+theme);
            tree=xml();(OUT/('finances-'+theme+'.xml')).write_bytes(ET.tostring(tree))
            verify_financial_summary(tree)
            scroll();screenshot('categories-'+theme);scroll(False)
            tap('Today');tap('Profile');tap('Account and family');tap('Create account');screenshot('registration-'+theme)
            adb('shell','input','keyevent','4')
        if modern:evidence['notificationDelivery']=notification_evidence();evidence['nativeNavigationScreenshots']=['Today','Tasks','Calendar','Notes','Finances','Profile']
        evidence['screenshots']='real Android 35 release app; synthetic data only'
        evidence['financialAmountsRetained']={'incomeMinor':10000,'expenseMinor':1250,'differenceMinor':8750,'currency':'USD'}
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
