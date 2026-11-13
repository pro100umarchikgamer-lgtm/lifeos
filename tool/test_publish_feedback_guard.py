"""Exact-file acceptance/rejection contract for the feedback deployment guard."""
import ast
import hashlib
from pathlib import Path
import unittest


class FeedbackGuardTest(unittest.TestCase):
    def setUp(self):
        script=(Path(__file__).resolve().parents[1]/'deploy/hostinger/publish-focus-ui.sh').read_text()
        body=script.split('python3 - "$source_dir" <<\'PY\'\n',1)[1].split('\nPY\n',1)[0]
        tree=ast.parse(body)
        selected=[node for node in tree.body if isinstance(node,(ast.Import,ast.ImportFrom,ast.FunctionDef)) or isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='REVIEWED_BACKEND_CHANGES' for t in node.targets)]
        self.namespace={}
        exec(compile(ast.Module(body=selected,type_ignores=[]),'feedback-publish-guard','exec'),self.namespace)
        original=self.namespace['REVIEWED_BACKEND_CHANGES']
        self.assertEqual(set(original),{'backend/control.py','backend/service.py','backend/schema.sql','backend/migrations/012_transaction_categories.sql','backend/tests/test_control.py','backend/tests/test_postgres.py','backend/tests/test_transaction_categories.py'})
        self.reviewed={name:(before,hashlib.sha256(('reviewed:'+name).encode()).hexdigest()) for name,(before,_) in original.items()}
        self.namespace['REVIEWED_BACKEND_CHANGES']=self.reviewed
        self.check=self.namespace['reviewed_backend_changes']
        self.live={name:before for name,(before,after) in self.reviewed.items() if before is not None}
        self.source={name:after for name,(before,after) in self.reviewed.items()}
        for inventory in (self.live,self.source):inventory['backend/production.py']='1'*64

    def test_accepts_only_exact_reviewed_baseline_to_candidate_deltas(self):
        remaining,reviewed=self.check(self.live,self.source)
        self.assertEqual(remaining,set())
        self.assertEqual(set(reviewed),set(self.reviewed))
        self.assertIsNone(self.reviewed['backend/migrations/012_transaction_categories.sql'][0])

    def test_unrelated_backend_path_is_not_exempted(self):
        self.source['backend/production.py']='2'*64
        remaining,_=self.check(self.live,self.source)
        self.assertEqual(remaining,{'backend/production.py'})

    def test_tampered_approved_candidate_content_is_rejected(self):
        self.source['backend/service.py']='2'*64
        with self.assertRaisesRegex(SystemExit,'candidate differs'):
            self.check(self.live,self.source)

    def test_unknown_running_backend_revision_is_not_exempted(self):
        self.live['backend/control.py']='2'*64
        remaining,_=self.check(self.live,self.source)
        self.assertEqual(remaining,{'backend/control.py'})

    def test_new_migration_cannot_replace_unrecognized_existing_sql(self):
        self.live['backend/migrations/012_transaction_categories.sql']='2'*64
        remaining,_=self.check(self.live,self.source)
        self.assertEqual(remaining,{'backend/migrations/012_transaction_categories.sql'})

    def test_missing_candidate_migration_is_rejected(self):
        self.source.pop('backend/migrations/012_transaction_categories.sql')
        with self.assertRaisesRegex(SystemExit,'candidate differs'):
            self.check(self.live,self.source)

    def test_unfinalized_digest_fails_closed(self):
        old,_=self.reviewed['backend/control.py']
        self.reviewed['backend/control.py']=(old,'REVIEW_REQUIRED')
        with self.assertRaisesRegex(SystemExit,'not finalized'):
            self.check(self.live,self.source)

    def test_same_already_applied_reviewed_schema_is_accepted(self):
        remaining,reviewed=self.check(dict(self.source),self.source)
        self.assertEqual(remaining,set())
        self.assertEqual(reviewed,[])


if __name__=='__main__':unittest.main()
