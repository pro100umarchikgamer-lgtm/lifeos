"""Supplemental DOM + real server acceptance; does not replace Playwright."""
import subprocess
from tool.check_web_platform import fixture

def main():
    with fixture() as (origin,*_):
        result=subprocess.run(['node','tool/check_web_dom.mjs',origin],check=False)
        if result.returncode:raise SystemExit(result.returncode)
if __name__=='__main__':main()
