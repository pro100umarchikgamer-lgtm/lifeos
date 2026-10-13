"""Loopback-only, disposable backend for the Android two-client integration test."""
from http.server import ThreadingHTTPServer
from pathlib import Path
import tempfile
import uuid

from backend.service import Backend
from backend.http_server import handler

with tempfile.TemporaryDirectory(prefix='lifeos-family-ci-') as folder:
    mailbox = {}
    backend = Backend(Path(folder) / 'server.db', deliver=lambda e, c: mailbox.update({e: c}))
    actors = []
    for email in ('android-one@example.test', 'android-two@example.test'):
        result = backend.register(email, 'isolated-integration-test-password')
        actor = backend.authenticate(result['token'])
        backend.verify(actor, mailbox[email])
        actors.append(backend.authenticate(result['token']))
    workspace = str(uuid.uuid4())
    backend.family(actors[0], {'id': str(uuid.uuid4()), 'workspace_id': workspace, 'action': 'workspace.create', 'name': 'Disposable integration family', 'kind': 'family'})
    invite = backend.family(actors[0], {'id': str(uuid.uuid4()), 'workspace_id': workspace, 'action': 'invite.create', 'email': actors[1]['email'], 'role': 'parent', 'profile_id': None})
    backend.accept(actors[1], {'id': str(uuid.uuid4()), 'invitation': invite['invitation']})
    ThreadingHTTPServer(('127.0.0.1', 8787), handler(backend)).serve_forever()
