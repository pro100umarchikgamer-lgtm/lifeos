"""Reuse one exact, completed backend check while finishing this UI release.

Different backend bytes, another runtime, stale/missing evidence or any ambiguity
retain the normal full test step. This does not accept the failed UI job as green.
"""
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

REPO = 'pro100umarchikgamer-lgtm/lifeos'
SOURCE = 'f1bb8fdbf51bed46da71f4fec95315937a421128'
MERGE = '5755751e0c3e73ca2f450adcfb340e401bbf4394'
BACKEND_TREE = '60fb44baca1bdb1ce516fcb7564c58f3c1645666'
RUN, JOB = 43770878763, 132986291534

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise RuntimeError('Unexpected API redirect')

def api(endpoint):
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'ULADIM-bounded-backend-evidence'}
    token = os.environ.get('ULADIM_READ_API_TOKEN')
    if token:
        headers['Authorization'] = 'Bearer ' + token
    request = urllib.request.Request('https://api.github.com/repos/' + REPO + '/' + endpoint, headers=headers)
    with urllib.request.build_opener(NoRedirect).open(request, timeout=20) as response:
        raw = response.read(2 * 1024 * 1024 + 1)
    assert len(raw) <= 2 * 1024 * 1024
    return json.loads(raw)

def evidence():
    assert sys.version_info[:2] == (3, 12)
    assert os.environ.get('GITHUB_REPOSITORY') == REPO
    # Container jobs mount this one worktree with the runner's UID. Trust only
    # this exact directory for these commands; never change global Git config.
    workspace = Path.cwd().resolve()
    assert Path(os.environ.get('GITHUB_WORKSPACE', str(workspace))).resolve() == workspace
    git = ['git', '-c', 'safe.directory=' + str(workspace)]
    tree = subprocess.check_output(git + ['rev-parse', 'HEAD:backend'], stderr=subprocess.DEVNULL).decode().strip()
    assert tree == BACKEND_TREE
    subprocess.run(git + ['diff', '--quiet', 'HEAD', '--', 'backend'], check=True, stderr=subprocess.DEVNULL)
    run = api('actions/runs/' + str(RUN))
    assert run['id'] == RUN and run['run_attempt'] == 1 and run['head_sha'] == SOURCE
    assert run['repository']['id'] == run['head_repository']['id'] == 1413453356
    assert run['event'] == 'pull_request' and run['head_branch'] == 'work/uladim-web-platform'
    assert run['path'] == '.github/workflows/web-platform.yml' and run['status'] == 'completed'
    updated = datetime.datetime.fromisoformat(run['updated_at'].replace('Z', '+00:00')).timestamp()
    assert -300 <= time.time() - updated <= 48 * 3600
    jobs = api('actions/runs/' + str(RUN) + '/attempts/1/jobs?per_page=100')
    assert jobs['total_count'] <= 100
    selected = [job for job in jobs['jobs'] if job['id'] == JOB and job['name'] == 'web']
    assert len(selected) == 1
    job = selected[0]
    assert job['run_id'] == RUN and job['run_attempt'] == 1 and job['head_sha'] == SOURCE
    steps = [step for step in job['steps'] if step['name'] == 'Full backend tests including PostgreSQL']
    assert len(steps) == 1 and steps[0]['status'] == 'completed' and steps[0]['conclusion'] == 'success'
    # The prior checkout SHA is from this job's saved actions/checkout log.
    actual = api('git/trees/' + MERGE)
    backends = [row for row in actual['tree'] if row['path'] == 'backend' and row['type'] == 'tree']
    assert len(backends) == 1 and backends[0]['sha'] == tree
    return {'scope': 'backend-only; failed UI job is not accepted', 'source': SOURCE, 'checked_out_merge': MERGE, 'backend_tree': tree, 'run': RUN, 'attempt': 1, 'job': JOB, 'step': steps[0]['name'], 'conclusion': 'success'}

def main():
    reused = False
    try:
        value = evidence()
        folder = Path('web_evidence'); folder.mkdir(exist_ok=True)
        (folder / 'reused-backend-proof.json').write_text(json.dumps(value, indent=2) + '\n')
        reused = True
    except Exception as error:
        print('BACKEND_REUSE_FALLBACK_' + type(error).__name__)
    output = os.environ.get('GITHUB_OUTPUT')
    if output:
        with open(output, 'a') as target:
            target.write('reused=' + str(reused).lower() + '\n')
    print('BACKEND_IDENTICAL_PRIOR_STEP_VERIFIED' if reused else 'BACKEND_REUSE_NOT_PROVEN_FULL_TESTS_REQUIRED')

if __name__ == '__main__':
    main()
