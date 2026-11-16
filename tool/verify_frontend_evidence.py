"""Reuse only six successful groups for byte-identical application and tests.

The failed referrals group and all subsequent groups run freshly. Any product
change, missing proof or uncertainty runs the original full frontend checks.
"""
import datetime,json,os,subprocess,sys,time
from pathlib import Path
from tool.verify_backend_evidence import api,REPO
SOURCE='a14d26bd2aac25a75074b000f52cb5d2f92567e7'
MERGE='dfed1285c7ac97f587f2aae9416d7aeebf55011e'
TREE='0f1b10b18e0a99466c5a06a84c4df4f7f3871209'
RUN,JOB=43778466930,133010053963
STEPS=('DOM integration with actual server records','Product CRUD, both themes and four viewport widths','Clarity hierarchy and selected-device revocation','Owner feedback regressions','Recorded feedback, inbox, safe Control recovery and public help','Focus settings, refresh status and delayed workspace switching')
ADDED='tool/verify_frontend_evidence.py'
MODIFIED=frozenset({'.github/workflows/web-platform.yml','tool/check_layout_referral_integration.py'})
WORKFLOW_BLOB='2d7bbdc23868571ccc138d92ee9c147622c5881c'

def verify_manifest(previous,current):
    assert set(previous)<=set(current) and set(current)-set(previous)=={ADDED}
    assert current[ADDED]['mode']=='100644' and current[ADDED]['type']=='blob'
    changed=[]
    for path,old in previous.items():
        new=current[path]
        if old!=new:
            assert path in MODIFIED and old['mode']==new['mode']=='100644' and old['type']==new['type']=='blob'
            changed.append(path)
    assert current['.github/workflows/web-platform.yml']['sha']==WORKFLOW_BLOB
    return sorted(changed)

def evidence():
    assert sys.version_info[:2]==(3,12) and os.environ.get('GITHUB_REPOSITORY')==REPO
    cwd=Path.cwd().resolve();assert Path(os.environ.get('GITHUB_WORKSPACE',str(cwd))).resolve()==cwd
    git=['git','-c','safe.directory='+str(cwd)]
    subprocess.run(git+['diff','--quiet','HEAD'],check=True,stderr=subprocess.DEVNULL)
    current={}
    for row in subprocess.check_output(git+['ls-tree','-rz','HEAD']).split(b'\0'):
        if not row:continue
        metadata,path=row.split(b'\t',1);mode,kind,oid=metadata.decode().split()
        current[path.decode()]={'mode':mode,'type':kind,'sha':oid}
    checkout=api('git/commits/'+MERGE);assert checkout['sha']==MERGE and checkout['tree']['sha']==TREE
    prior=api('git/trees/'+TREE+'?recursive=1');assert prior['sha']==TREE and prior['truncated'] is False
    previous={r['path']:{k:r[k] for k in ('mode','type','sha')} for r in prior['tree'] if r['type']!='tree'}
    changed=verify_manifest(previous,current)
    run=api('actions/runs/'+str(RUN));assert run['id']==RUN and run['head_sha']==SOURCE and run['run_attempt']==1
    assert run['repository']['id']==run['head_repository']['id']==1413453356 and run['event']=='pull_request' and run['head_branch']=='work/uladim-web-platform'
    assert run['path']=='.github/workflows/web-platform.yml' and run['status']=='completed'
    updated=datetime.datetime.fromisoformat(run['updated_at'].replace('Z','+00:00')).timestamp();assert -300<=time.time()-updated<=48*3600
    job=api('actions/jobs/'+str(JOB));assert job['id']==JOB and job['run_id']==RUN and job['run_attempt']==1 and job['head_sha']==SOURCE and job['name']=='web'
    for name in STEPS:
        matches=[s for s in job['steps'] if s['name']==name]
        assert len(matches)==1 and matches[0]['status']=='completed' and matches[0]['conclusion']=='success'
    return {'scope':'six completed UI groups only; failed referrals group and remaining checks run freshly','source':SOURCE,'checkout':MERGE,'tree':TREE,'run':RUN,'attempt':1,'job':JOB,'steps':STEPS,'modified_test_infrastructure_only':changed,'application_bytes_unchanged':True}

def main():
    reused=False
    try:
        result=evidence();p=Path('web_evidence');p.mkdir(exist_ok=True);(p/'reused-frontend-proof.json').write_text(json.dumps(result,indent=2)+'\n');reused=True
    except Exception as error:print('FRONTEND_REUSE_FALLBACK_'+type(error).__name__)
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('reused='+str(reused).lower()+'\n')
    print('FRONTEND_IDENTICAL_PRIOR_GROUPS_VERIFIED' if reused else 'FRONTEND_REUSE_NOT_PROVEN_FULL_CHECKS_REQUIRED')
if __name__=='__main__':main()
