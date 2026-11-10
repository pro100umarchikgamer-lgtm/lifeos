"""Check the signed AAB's actual manifest and APK's actual target SDK."""
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

def main():
    expected=int(sys.argv[1])
    android='{http://schemas.android.com/apk/res/android}'
    manifest=ET.fromstring(Path('aab-manifest.xml').read_bytes())
    assert manifest.get('package')=='app.lifeos.lifeos', 'AAB applicationId changed'
    assert int(manifest.get(android+'versionCode','0'))==expected>134001
    sdk=manifest.find('uses-sdk')
    assert sdk is not None and int(sdk.get(android+'targetSdkVersion','0'))>=36, 'AAB target API must be >=36'
    assert int(sdk.get(android+'minSdkVersion','0'))==23, 'Retain API23 device compatibility'
    app=manifest.find('application')
    assert app is not None and app.get(android+'debuggable','false')=='false', 'AAB is debuggable'
    assert app.get(android+'allowBackup')=='false', 'AAB must preserve local database backup exclusion'
    badging=Path('apk-manifest.txt').read_text()
    target=re.search(r"targetSdkVersion:'(\d+)'",badging)
    assert target and int(target[1])>=36, 'APK target API must be >=36'
    Path('aab-identity.txt').write_text(f'applicationId=app.lifeos.lifeos\nversionCode={expected}\ntargetSdk={sdk.get(android+"targetSdkVersion")}\ncertificateSHA256={Path("docs/ANDROID_TEST_CERT.sha256").read_text().strip()}\n')
    print('AAB identity, target SDK, non-debuggable and backup privacy verified')

if __name__=='__main__':main()
