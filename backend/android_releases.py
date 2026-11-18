"""Control-managed Android releases on a private, durable local volume."""
from contextlib import contextmanager
import fcntl
import hashlib
import os
import re
import uuid

from .apk_verifier import ApkVerifier
from .control import Control
from .native_download import CHUNK, MAX_BYTES, NativeDownload, fingerprint
from .service import Failure, identifier, require


DIGEST_PATH = re.compile(r'/download/android/sha256/([a-f0-9]{64})/ULADIM\.apk\Z')
ROW_FIELDS = ('id', 'state', 'revision', 'bytes', 'apk_sha256', 'package_name', 'certificate_sha256',
              'version_name', 'version_code', 'error', 'created_at', 'updated_at', 'published_at')
TERMINAL = ('published', 'cancelled')


def view(row):
    return {key: row[key] for key in ROW_FIELDS}


def manifest(row):
    return {'origin': 'control', 'version_code': row['version_code'], 'version_name': row['version_name'],
            'bytes': row['bytes'], 'apk_sha256': row['apk_sha256'], 'certificate_sha256': row['certificate_sha256'],
            'apk_url': '/download/android/sha256/' + row['apk_sha256'] + '/ULADIM.apk'}


class AndroidReleases:
    def __init__(self, backend, settings, legacy_download):
        self.backend = backend
        self.control = Control(backend)
        self.legacy = legacy_download
        self.storage = NativeDownload(getattr(settings, 'native_publish_dir', ''), trusted_uid=os.getuid())
        self.verifier = ApkVerifier()

    @contextmanager
    def _directory(self, exclusive=False):
        try:
            directory = self.storage._directory()
        except (ValueError, OSError):
            raise Failure('apk_storage_unavailable', 503) from None
        try:
            require(not os.fstat(directory).st_mode & 0o077, 'apk_storage_unavailable', 503)
            if exclusive:
                try:
                    fcntl.flock(directory, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise Failure('apk_busy', 409) from None
            yield directory
        finally:
            os.close(directory)

    @staticmethod
    def _current(db):
        return db.execute('SELECT r.* FROM android_release_current c JOIN android_releases r ON r.id=c.release_id '
                          "WHERE c.singleton=1 AND r.state='published'").fetchone()

    def public_manifest(self):
        with self.backend.connect() as db:
            current = self._current(db)
        return self._serving_manifest(current)

    def _serving_manifest(self, current):
        if current is None:
            return self.legacy.manifest()
        # Every worker follows the committed pointer, including one with a
        # missing mount. A published manifest must identify a servable object.
        try:
            with self._directory() as directory:
                fd, _ = self._checked(directory, current)
                os.close(fd)
        except Failure:
            raise Failure('apk_published_unavailable', 503) from None
        return manifest(current)

    def _list(self):
        with self.backend.connect() as db:
            current = self._current(db)
            drafts = db.execute("SELECT * FROM android_releases WHERE state NOT IN ('published','cancelled') ORDER BY updated_at DESC,id DESC").fetchall()
            history = db.execute("SELECT * FROM android_releases WHERE state IN ('published','cancelled') ORDER BY updated_at DESC,id DESC LIMIT 100").fetchall()
        try:
            selection = self._serving_manifest(current)
        except Failure as error:
            if error.code != 'apk_published_unavailable':
                raise
            selection = None
        return {'current': selection,
                'drafts': [view(r) for r in drafts], 'history': [view(r) for r in history]}

    @staticmethod
    def _row(db, release_id, revision, states):
        row = db.execute('SELECT * FROM android_releases WHERE id=?', (release_id,)).fetchone()
        require(row is not None, 'not_found', 404)
        require(row['revision'] == revision, 'revision_conflict', 409)
        require(row['state'] in states, 'apk_state_conflict', 409)
        return row

    def _audit_row(self, db, actor, release_id, event, before=None):
        row = db.execute('SELECT * FROM android_releases WHERE id=?', (release_id,)).fetchone()
        summary = {k: row[k] for k in ('state','revision','version_code','bytes')}
        self.control.audit(db, actor, release_id, 'android.' + event,
                           {'state': before['state'], 'revision': before['revision']} if before else {},
                           summary, 'Android release ' + event)
        return view(row)

    def handle(self, actor, action, method, body, query):
        require(not query, 'invalid_fields')
        if action == 'android-releases' and method == 'GET':
            self.control.require(actor, 'android.read')
            return self._list()
        actions = {'android-releases/draft', 'android-releases/validate', 'android-releases/publish', 'android-releases/cancel'}
        require(action in actions and method == 'POST', 'not_found', 404)
        self.control.require(actor, 'android.publish' if action.endswith('/publish') else 'android.upload')
        if action.endswith('/draft'):
            require(body == {}, 'invalid_fields')
            with self._directory() as directory:
                self._reconcile_if_idle(directory)
                with self.backend.transaction() as db:
                    active = db.execute("SELECT COUNT(*) AS n FROM android_releases WHERE state NOT IN ('published','cancelled')").fetchone()['n']
                    require(active < 8, 'apk_draft_limit', 409)
                    release_id = str(uuid.uuid4())
                    now = int(self.backend.clock())
                    db.execute("INSERT INTO android_releases(id,state,revision,created_at,updated_at,created_by) VALUES(?,'draft',1,?,?,?)",
                               (release_id, now, now, actor.id))
                    return self._audit_row(db, actor, release_id, 'draft')
        require(isinstance(body, dict) and set(body) == {'id', 'revision'} and type(body['revision']) is int and body['revision'] > 0, 'invalid_fields')
        release_id, revision = identifier(body['id']), body['revision']
        if action.endswith('/cancel'):
            return self._cancel(actor, release_id, revision)
        if action.endswith('/validate'):
            return self._validate(actor, release_id, revision)
        return self._publish(actor, release_id, revision)

    @staticmethod
    def _unlink(directory, name):
        try:
            os.unlink(name, dir_fd=directory)
        except FileNotFoundError:
            pass

    def _reconcile(self, directory, requested=None):
        # The caller owns the upload flock. No in-flight intake can recreate
        # either name after their cancellation marker has been acknowledged.
        with self.backend.connect() as db:
            pending = db.execute("SELECT r.id FROM android_release_cleanup c JOIN android_releases r ON r.id=c.release_id "
                                 "WHERE r.state='cancelled' ORDER BY CASE WHEN r.id=? THEN 0 ELSE 1 END,r.updated_at,r.id LIMIT 64",
                                 (requested,)).fetchall()
        if not pending:
            return
        try:
            for item in pending:
                release_id = identifier(item['id'])
                self._unlink(directory, release_id + '.part')
                self._unlink(directory, release_id + '.apk')
            os.fsync(directory)
        except OSError:
            raise Failure('apk_storage_unavailable', 503) from None
        with self.backend.transaction() as db:
            for item in pending:
                db.execute('DELETE FROM android_release_cleanup WHERE release_id=?', (item['id'],))

    def _reconcile_if_idle(self, directory, requested=None):
        try:
            fcntl.flock(directory, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        try:
            self._reconcile(directory, requested)
        finally:
            fcntl.flock(directory, fcntl.LOCK_UN)

    def _cancel(self, actor, release_id, revision):
        with self._directory() as directory:
            with self.backend.transaction() as db:
                row = db.execute('SELECT * FROM android_releases WHERE id=?', (release_id,)).fetchone()
                require(row is not None, 'not_found', 404)
                if row['state'] == 'cancelled' and revision in (row['revision'], row['revision'] - 1):
                    result = view(row)
                else:
                    require(row['revision'] == revision, 'revision_conflict', 409)
                    require(row['state'] not in TERMINAL, 'apk_state_conflict', 409)
                    db.execute("UPDATE android_releases SET state='cancelled',revision=revision+1,updated_at=? WHERE id=?",
                               (int(self.backend.clock()), release_id))
                    db.execute('INSERT INTO android_release_cleanup(release_id) VALUES(?)', (release_id,))
                    result = self._audit_row(db, actor, release_id, 'cancel', row)
            self._reconcile_if_idle(directory, release_id)
            return result

    def upload(self, actor, env):
        self.control.require(actor, 'android.upload')
        require(env.get('REQUEST_METHOD') == 'POST' and not env.get('QUERY_STRING'), 'invalid_fields')
        require(env.get('CONTENT_TYPE', '').lower() in ('application/vnd.android.package-archive', 'application/octet-stream')
                and not env.get('HTTP_CONTENT_ENCODING'), 'content_type', 415)
        length = env.get('CONTENT_LENGTH', '')
        require(re.fullmatch(r'[1-9][0-9]{0,9}', length) and int(length) <= MAX_BYTES, 'body_limit', 413)
        release_id = identifier(env.get('HTTP_X_RELEASE_ID'))
        revision = env.get('HTTP_X_RELEASE_REVISION', '')
        require(re.fullmatch(r'[1-9][0-9]{0,9}', revision), 'invalid_fields')
        revision = int(revision)
        temporary, final = release_id + '.part', release_id + '.apk'
        with self._directory(exclusive=True) as directory:
            self._reconcile(directory)
            with self.backend.connect() as db:
                self._row(db, release_id, revision, ('draft',))
            # A crashed upload cannot have committed an object for a draft. This
            # per-volume lock also excludes a second writer during recovery.
            self._unlink(directory, temporary)
            try:
                fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
                with os.fdopen(fd, 'wb') as output:
                    digest = hashlib.sha256()
                    size = 0
                    while size < int(length):
                        want = min(CHUNK, int(length) - size)
                        try:
                            chunk = env['wsgi.input'].read(want)
                        except (OSError, ValueError):
                            raise Failure('apk_upload_incomplete') from None
                        require(isinstance(chunk, bytes) and 0 < len(chunk) <= want, 'apk_upload_incomplete')
                        output.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
                    output.flush()
                    os.fchmod(output.fileno(), 0o400)
                    os.fsync(output.fileno())
                with self.backend.transaction() as db:
                    row = self._row(db, release_id, revision, ('draft',))
                    os.replace(temporary, final, src_dir_fd=directory, dst_dir_fd=directory)
                    os.fsync(directory)
                    db.execute("UPDATE android_releases SET state='uploaded',revision=revision+1,bytes=?,apk_sha256=?,updated_at=? WHERE id=?",
                               (size, digest.hexdigest(), int(self.backend.clock()), release_id))
                    return self._audit_row(db, actor, release_id, 'upload', row)
            except OSError:
                raise Failure('apk_storage_unavailable', 503) from None
            finally:
                self._unlink(directory, temporary)

    def _checked(self, directory, row, *, rehash=False):
        try:
            fd, info = self.storage._file(directory, row['id'] + '.apk', MAX_BYTES)
        except (OSError, ValueError):
            raise Failure('apk_file_changed', 409) from None
        try:
            return fd, self.storage.verify_file(fd, info, row, rehash=rehash)
        except (OSError, ValueError):
            os.close(fd)
            raise Failure('apk_file_changed', 409) from None
        except BaseException:
            os.close(fd)
            raise

    def _floor(self, db, legacy):
        current = self._current(db)
        # With no managed history, the operator's actual installed legacy
        # baseline is required. A configured but unreadable cache fails closed.
        require(legacy or current and not self.legacy.root, 'apk_baseline_unavailable', 503)
        return max(legacy['version_code'] if legacy else 0, current['version_code'] if current else 0)

    def _validate(self, actor, release_id, revision):
        with self._directory(exclusive=True) as directory:
            with self.backend.connect() as db:
                row = self._row(db, release_id, revision, ('uploaded',))
            identity, error = {}, None
            try:
                fd, before = self._checked(directory, row)
                try:
                    identity = self.verifier.verify(fd)
                    require(fingerprint(os.fstat(fd)) == before, 'apk_file_changed', 409)
                finally:
                    os.close(fd)
            except Failure as failure:
                if failure.status >= 500:
                    raise
                error = failure.code
            legacy = self.legacy.manifest()
            with self.backend.transaction() as db:
                row = self._row(db, release_id, revision, ('uploaded',))
                if not error and identity['version_code'] <= self._floor(db, legacy):
                    error = 'apk_version_not_newer'
                state = 'rejected' if error else 'validated'
                db.execute('UPDATE android_releases SET state=?,revision=revision+1,package_name=?,version_code=?,version_name=?,'
                           'certificate_sha256=?,error=?,updated_at=? WHERE id=?',
                           (state, identity.get('package_name'), identity.get('version_code'), identity.get('version_name'),
                            identity.get('certificate_sha256'), error, int(self.backend.clock()), release_id))
                return self._audit_row(db, actor, release_id, 'validate', row)

    def _publish(self, actor, release_id, revision):
        with self._directory() as directory:
            with self.backend.connect() as db:
                row = self._row(db, release_id, revision, ('validated',))
            fd, identity = self._checked(directory, row, rehash=True)
            try:
                legacy = self.legacy.manifest()
                with self.backend.transaction() as db:
                    row = self._row(db, release_id, revision, ('validated',))
                    require(row['version_code'] > self._floor(db, legacy), 'apk_version_not_newer', 409)
                    require(fingerprint(os.fstat(fd)) == identity, 'apk_file_changed', 409)
                    now = int(self.backend.clock())
                    db.execute("UPDATE android_releases SET state='published',revision=revision+1,published_at=?,updated_at=? WHERE id=?",
                               (now, now, release_id))
                    db.execute('INSERT INTO android_release_current(singleton,release_id) VALUES(1,?) '
                               'ON CONFLICT(singleton) DO UPDATE SET release_id=excluded.release_id', (release_id,))
                    return self._audit_row(db, actor, release_id, 'publish', row)
            finally:
                os.close(fd)

    def download_response(self, env):
        match = DIGEST_PATH.fullmatch(env.get('PATH_INFO', ''))
        if not match:
            return self.legacy.response(env)
        if env.get('QUERY_STRING') or not self.storage.root:
            return self.storage._empty(404)
        if env.get('REQUEST_METHOD') not in ('GET', 'HEAD'):
            return self.storage._empty(405, [('Allow', 'GET, HEAD')])
        with self.backend.connect() as db:
            row = db.execute("SELECT * FROM android_releases WHERE state='published' AND apk_sha256=?", (match[1],)).fetchone()
        if row:
            try:
                with self._directory() as directory:
                    fd, identity = self._checked(directory, row)
                return self.storage.file_response(env, fd, identity, manifest(row))
            except Failure:
                pass
        return self.storage._empty(404)
