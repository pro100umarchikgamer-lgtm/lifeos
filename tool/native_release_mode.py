"""Select publication only when the application tree is the retained source tree."""
import json
import os
from pathlib import Path
import re
import subprocess

REPOSITORY = 'pro100umarchikgamer-lgtm/lifeos'
BRANCH = 'work/uladim-web-platform'
DECLARATION = 'deploy/native-releases/312001.json'
# Deliberately exact: neither a directory prefix nor rename detection is safe here.
RELEASE_FILES = frozenset({
    '.github/workflows/stage1.yml', DECLARATION,
    'tool/native_release_mode.py', 'tool/publish_retained_apk.py',
    'tool/tests/test_retained_native_release.py',
})


def git(*args):
    return subprocess.check_output(['git', *args])


def publication_requested(env):
    return (env.get('GITHUB_REPOSITORY') == REPOSITORY
            and env.get('GITHUB_REF') == 'refs/heads/' + BRANCH
            and env.get('GITHUB_EVENT_NAME') == 'workflow_dispatch'
            and env.get('BUILD_APK') == 'true'
            and env.get('UPGRADE_PROBE') != 'true'
            and env.get('FOCUSED') != 'true'
            and env.get('REUSE_SIGNED_APK') != 'true'
            and env.get('FORCE_FULL_VALIDATION') != 'true')


def choose_mode(declaration, env, command=git):
    if not publication_requested(env):
        return 'validate'
    source = declaration['source']
    if not re.fullmatch('[0-9a-f]{40}', source):
        raise ValueError('Retained source must be a full commit SHA')
    try:
        command('merge-base', '--is-ancestor', source, 'HEAD')
    except subprocess.CalledProcessError:
        return 'validate'
    # NUL separation preserves filenames containing newlines/non-ASCII characters.
    changed = command('diff', '--no-renames', '--name-only', '-z', source, 'HEAD').split(b'\0')
    paths = {path.decode('utf-8', errors='surrogateescape') for path in changed if path}
    if not paths or not paths <= RELEASE_FILES:
        return 'validate'
    # Reject deletions and type changes, including symlinks replacing scripts.
    for path in paths:
        entry = command('ls-tree', 'HEAD', '--', path)
        if not entry.startswith(b'100644 blob '):
            return 'validate'
    return 'publish-retained'


def main():
    # Ordinary PR/push validation does not depend on a release declaration.
    mode = 'validate'
    if publication_requested(os.environ):
        mode = choose_mode(json.loads(Path(DECLARATION).read_text()), os.environ)
    with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
        stream.write('mode=' + mode + '\n')
    print('Native release mode: ' + mode)


if __name__ == '__main__':
    main()
