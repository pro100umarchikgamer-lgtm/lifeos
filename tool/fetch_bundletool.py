"""Fetch the pinned official standalone AAB validator; never execute unchecked bytes."""
import hashlib
import os
from pathlib import Path
import urllib.request
VERSION = '1.18.3'
SHA256 = 'a099cfa1543f55593bc2ed16a70a7c67fe54b1747bb7301f37fdfd6d91028e29'
URL = f'https://github.com/google/bundletool/releases/download/{VERSION}/bundletool-all-{VERSION}.jar'

def main():
    target=Path(os.environ['RUNNER_TEMP'])/'uladim-bundletool.jar'
    if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest()!=SHA256:
        with urllib.request.urlopen(URL,timeout=60) as response:
            value=response.read(64*1024*1024+1)
        if len(value)>64*1024*1024 or hashlib.sha256(value).hexdigest()!=SHA256:
            raise RuntimeError('Official bundletool checksum mismatch')
        target.write_bytes(value)
    print(target)

if __name__=='__main__':main()
