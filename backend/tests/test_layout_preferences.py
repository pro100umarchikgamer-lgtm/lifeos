"""Personal list order never grants access or mutates financial records."""
import json
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from backend.service import Backend, Failure
from backend.layout_preferences import LayoutPreferences


def uid():return str(uuid4())


class LayoutPreferenceTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        self.backend=Backend(Path(folder.name)/'layout.db')
        self.owner={'id':uid(),'email':'layout-owner@example.test','verified':1}
        self.viewer={'id':uid(),'email':'layout-viewer@example.test','verified':1}
        self.outsider={'id':uid(),'email':'layout-other@example.test','verified':1}
        self.space,self.foreign=uid(),uid()
        with self.backend.transaction() as db:
            db.executescript(Path('backend/migrations/022_layout_preferences.sql').read_text())
            for actor in (self.owner,self.viewer,self.outsider):
                db.execute('INSERT INTO users VALUES(?,?,?,?,1,0)',(actor['id'],actor['email'],'fixture-hash','fixture-salt'))
            db.execute("INSERT INTO workspaces(id,name,creator_id,kind) VALUES(?,?,?,'personal')",(self.space,'Shared view',self.owner['id']))
            db.execute("INSERT INTO workspaces(id,name,creator_id,kind) VALUES(?,?,?,'personal')",(self.foreign,'Other space',self.outsider['id']))
            for actor,space,role in ((self.owner,self.space,'owner'),(self.viewer,self.space,'adult'),(self.outsider,self.foreign,'owner')):
                db.execute('INSERT INTO memberships(workspace_id,user_id,role) VALUES(?,?,?)',(space,actor['id'],role))
        self.layout=LayoutPreferences(self.backend)
        self.first=self.record('account');self.second=self.record('account')
        self.budget=self.record('budget');self.hidden=self.record('account',grant=False)
        self.other=self.record('account',space=self.foreign,actor=self.outsider,grant=False)

    def record(self,kind,space=None,actor=None,grant=True):
        rid=uid();actor=actor or self.owner
        with self.backend.transaction() as db:
            db.execute('INSERT INTO records VALUES(?,?,?,?,?,?,1,0,1)',(rid,space or self.space,actor['id'],kind,'private','[]'))
            if kind=='account':db.execute('INSERT INTO accounts VALUES(?,?,?,?)',(rid,'Private finance name','RUB',12505))
            else:db.execute('INSERT INTO budgets VALUES(?,?,?,?,?,?,?,?,?)',(rid,'Private budget','RUB',60000,'month','2026-11-01',None,'none','[]'))
            if grant:db.execute('INSERT INTO grants(record_id,user_id,can_edit) VALUES(?,?,0)',(rid,self.viewer['id']))
        return rid

    def error(self,code,operation):
        with self.assertRaises(Failure) as caught:operation()
        self.assertEqual(caught.exception.code,code)

    def test_order_is_persistent_personal_and_allowed_for_read_only_viewer(self):
        with self.backend.connect() as db:
            space=self.backend._workspace(db,self.viewer,self.space)
            record=db.execute('SELECT * FROM records WHERE id=?',(self.first,)).fetchone()
            self.assertFalse(self.backend._editable(db,self.viewer,space,record))
        self.assertEqual(self.layout.get(self.viewer,self.space,'account')['order'],[])
        value=self.layout.put(self.viewer,self.space,'account',[self.second,self.first],revision=0)
        self.assertEqual(value['order'],[self.second,self.first]);self.assertEqual(value['revision'],1)
        self.assertEqual(LayoutPreferences(self.backend).get(self.viewer,self.space,'account'),value)
        self.assertEqual(self.layout.get(self.owner,self.space,'account')['order'],[])
        self.assertEqual(self.layout.get(self.viewer,self.space,'budget')['order'],[])
        self.assertNotIn('Private',json.dumps(value))

    def test_wrong_workspace_hidden_unknown_kind_and_duplicate_ids_are_rejected_without_partial_save(self):
        self.layout.put(self.viewer,self.space,'account',[self.first],0)
        for bad in (self.other,self.hidden,self.budget,uid()):
            self.error('layout_record_forbidden',lambda:self.layout.put(self.viewer,self.space,'account',[self.second,bad],1))
        self.error('layout_order_invalid',lambda:self.layout.put(self.viewer,self.space,'account',[self.first,self.first],1))
        self.error('workspace_forbidden',lambda:self.layout.get(self.outsider,self.space,'account'))
        self.error('workspace_forbidden',lambda:self.layout.put(self.viewer,self.foreign,'account',[self.other],0))
        self.assertEqual(self.layout.get(self.viewer,self.space,'account')['order'],[self.first])

    def test_get_filters_revoked_and_deleted_records_without_disclosing_ids(self):
        self.layout.put(self.viewer,self.space,'account',[self.first,self.second],0)
        with self.backend.transaction() as db:
            db.execute('DELETE FROM grants WHERE record_id=? AND user_id=?',(self.first,self.viewer['id']))
            db.execute('UPDATE records SET deleted=1 WHERE id=?',(self.second,))
        value=self.layout.get(self.viewer,self.space,'account')
        self.assertEqual(value['order'],[]);self.assertEqual(value['revision'],1)
        self.error('layout_record_forbidden',lambda:self.layout.put(self.viewer,self.space,'account',[self.second],1))
        with self.backend.transaction() as db:db.execute('UPDATE memberships SET active=0 WHERE user_id=?',(self.viewer['id'],))
        self.error('workspace_forbidden',lambda:self.layout.get(self.viewer,self.space,'account'))

    def test_revision_conflict_and_layout_save_leave_canonical_records_unchanged(self):
        with self.backend.connect() as db:
            before=[tuple(row) for row in db.execute('SELECT * FROM records ORDER BY id')]
            amounts=[tuple(row) for row in db.execute('SELECT * FROM accounts ORDER BY id')]
        self.layout.put(self.viewer,self.space,'account',[self.first],0)
        self.error('layout_revision_conflict',lambda:self.layout.put(self.viewer,self.space,'account',[self.second],0))
        self.assertEqual(self.layout.put(self.viewer,self.space,'account',[self.second],1)['revision'],2)
        self.assertEqual(self.layout.put(self.viewer,self.space,'budget',[self.budget])['order'],[self.budget])
        with self.backend.connect() as db:
            self.assertEqual(before,[tuple(row) for row in db.execute('SELECT * FROM records ORDER BY id')])
            self.assertEqual(amounts,[tuple(row) for row in db.execute('SELECT * FROM accounts ORDER BY id')])

    def test_budget_order_is_independent_of_account_order(self):
        extra=self.record('budget')
        self.layout.put(self.viewer,self.space,'account',[self.second,self.first],0)
        self.layout.put(self.viewer,self.space,'budget',[extra,self.budget],0)
        self.assertEqual(self.layout.get(self.viewer,self.space,'budget')['order'],[extra,self.budget])
        self.assertEqual(self.layout.get(self.viewer,self.space,'account')['order'],[self.second,self.first])

    def test_bounds_types_and_unverified_account_are_rejected(self):
        for kind in ('transaction','accounts','',None):
            self.error('layout_kind_invalid',lambda:self.layout.get(self.viewer,self.space,kind))
        for order in (None,{},'not-a-list',[self.first]*1001,[True],['not-a-uuid']):
            self.error('layout_order_invalid',lambda:self.layout.put(self.viewer,self.space,'account',order))
        for revision in (True,-1,'0',1.5):
            self.error('layout_revision_invalid',lambda:self.layout.put(self.viewer,self.space,'account',[],revision))
        self.error('verify_email',lambda:self.layout.get({**self.viewer,'verified':0},self.space,'account'))


if __name__=='__main__':unittest.main()
