"""Exact-file acceptance/rejection contract for the feedback deployment guard."""
import ast
import hashlib
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

REVIEWED_PATHS={
    'backend/control.py','backend/service.py','backend/schema.sql',
    'backend/migrations/012_transaction_categories.sql',
    'backend/tests/test_control.py','backend/tests/test_postgres.py',
    'backend/tests/test_transaction_categories.py',
} | {
    'backend/web_push.py','backend/migrations/013_web_push.sql',
    'backend/schema.sql','backend/web.py','backend/mail.py',
    'backend/account_lifecycle.py','backend/import_sqlite.py',
    'backend/tests/test_web_push.py','backend/tests/test_web_push_postgres.py',
}


class FeedbackGuardTest(unittest.TestCase):
    def setUp(self):
        self.root=Path(__file__).resolve().parents[1]
        script=(self.root/'deploy/hostinger/publish-focus-ui.sh').read_text()
        self.body=script.split('python3 - "$source_dir" <<\'PY\'\n',1)[1].split('\nPY\n',1)[0]
        tree=ast.parse(self.body)
        selected=[node for node in tree.body if isinstance(node,(ast.Import,ast.ImportFrom,ast.FunctionDef)) or isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='REVIEWED_BACKEND_CHANGES' for t in node.targets)]
        self.namespace={}
        exec(compile(ast.Module(body=selected,type_ignores=[]),'feedback-publish-guard','exec'),self.namespace)
        original=self.namespace['REVIEWED_BACKEND_CHANGES']
        self.assertEqual(set(original),REVIEWED_PATHS)
        self.original=dict(original)
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

    def test_tampered_new_web_push_module_and_migration_are_rejected(self):
        for name in ('backend/web_push.py','backend/migrations/013_web_push.sql'):
            with self.subTest(name=name):
                altered={**self.source,name:'2'*64}
                self.assertIsNone(self.reviewed[name][0])
                with self.assertRaisesRegex(SystemExit,'candidate differs'):
                    self.check(self.live,altered)

    def test_unknown_running_backend_revision_is_not_exempted(self):
        self.live['backend/control.py']='2'*64
        remaining,_=self.check(self.live,self.source)
        self.assertEqual(remaining,{'backend/control.py'})

    def test_web_routes_require_exact_running_baseline_or_candidate(self):
        self.live['backend/web.py']='2'*64
        remaining,_=self.check(self.live,self.source)
        self.assertEqual(remaining,{'backend/web.py'})

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

    def inventory_fixture(self,folder):
        root=Path(folder)
        live={name:before for name,(before,_) in self.reviewed.items() if before is not None}
        for name in self.reviewed:
            destination=root/name
            destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_text('reviewed:'+name)
        extra=root/'backend/production.py'
        extra.write_text('# unchanged unreviewed backend module\n')
        live['backend/production.py']=hashlib.sha256(extra.read_bytes()).hexdigest()
        return root,live

    def run_inventory_guard(self,root,live,synthetic=True):
        tree=ast.parse(self.body)
        if synthetic:
            for node in tree.body:
                if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='REVIEWED_BACKEND_CHANGES' for t in node.targets):
                    node.value=ast.parse(repr(self.reviewed),mode='eval').body
            ast.fix_missing_locations(tree)
        with patch('sys.argv',['guard',str(root)]),patch('subprocess.check_output',return_value=json.dumps(live).encode()),contextlib.redirect_stdout(io.StringIO()) as output:
            exec(compile(tree,'feedback-inventory-guard','exec'),{})
        return output.getvalue()

    def test_full_inventory_accepts_exact_reviewed_fixture_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root,live=self.inventory_fixture(folder)
            self.assertIn('BACKEND_REVIEWED_DELTAS_ONLY',self.run_inventory_guard(root,live))

    def test_frozen_legacy_guard_rejects_expanded_product_backend(self):
        # New releases use a separately reviewed full-backend policy. The old
        # privileged UI publisher must keep rejecting these additional changes.
        live={name:before for name,(before,_) in self.original.items() if before is not None}
        with self.assertRaises(SystemExit):
            self.run_inventory_guard(self.root,live,synthetic=False)

    def test_full_inventory_rejects_nested_unreviewed_python_and_sql_additions(self):
        for suffix in ('.py','.sql'):
            with self.subTest(suffix=suffix),tempfile.TemporaryDirectory() as folder:
                root,live=self.inventory_fixture(folder)
                unexpected=root/('backend/unreviewed/nested'+suffix)
                unexpected.parent.mkdir(parents=True)
                unexpected.write_text('# outside the fixed reviewed scope\n')
                with self.assertRaisesRegex(SystemExit,'backend/unreviewed/nested'):
                    self.run_inventory_guard(root,live)

    def test_full_inventory_rejects_unrecognized_running_web_routes(self):
        with tempfile.TemporaryDirectory() as folder:
            root,live=self.inventory_fixture(folder)
            live['backend/web.py']='2'*64
            with self.assertRaisesRegex(SystemExit,'backend/web.py'):
                self.run_inventory_guard(root,live)


if __name__=='__main__':unittest.main()
