"""Explicit release branches; feature signing requires an authorized manual run."""
RELEASE_BRANCHES = frozenset({
    'refs/heads/feature/uladim-control-release',
    'refs/heads/feature/uladim-ux-recovery-launch',
    'refs/heads/feature/uladim-brand',
    'refs/heads/feature/family-sync',
    'refs/heads/feature/lifeos-3-production',
    'refs/heads/feature/lifeos-3-ux-recovery',
})


def permits_signed_build(ref, event):
    if event not in {'push', 'workflow_dispatch'}:
        return False
    return ref == 'refs/heads/main' or (
        ref in RELEASE_BRANCHES and event == 'workflow_dispatch'
    )
