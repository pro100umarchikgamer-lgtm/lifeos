import unittest

from tool.release_policy import permits_signed_build


class ReleasePolicyTests(unittest.TestCase):
    def test_requested_branch_requires_manual_dispatch(self):
        branch = 'refs/heads/feature/lifeos-3-ux-recovery'
        self.assertTrue(permits_signed_build(branch, 'workflow_dispatch'))
        self.assertFalse(permits_signed_build(branch, 'push'))

    def test_uladim_requires_manual_dispatch_and_rejects_prs(self):
        branch = 'refs/heads/feature/uladim-brand'
        self.assertTrue(permits_signed_build(branch, 'workflow_dispatch'))
        for event in ['push', 'pull_request', 'workflow_run']:
            self.assertFalse(permits_signed_build(branch, event))

    def test_pull_requests_and_unlisted_branches_never_sign(self):
        for branch in ['refs/heads/main', 'refs/heads/feature/lifeos-3-ux-recovery', 'refs/pull/1/merge']:
            self.assertFalse(permits_signed_build(branch, 'pull_request'))
        self.assertFalse(permits_signed_build('refs/heads/unreviewed', 'workflow_dispatch'))
        self.assertFalse(permits_signed_build('refs/heads/main', 'workflow_run'))

    def test_existing_release_routes_remain_available(self):
        self.assertTrue(permits_signed_build('refs/heads/main', 'push'))
        self.assertTrue(permits_signed_build('refs/heads/feature/lifeos-3-production', 'workflow_dispatch'))
