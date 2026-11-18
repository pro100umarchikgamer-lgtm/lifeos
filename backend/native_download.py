"""Serve one locally accepted APK. No network, user-selected files or redirects."""
from collections import OrderedDict
import hashlib
import json
import os
from pathlib import PurePosixPath
import re
import stat
import threading

CERTIFICATE = '5fa37e4abf1ec90d5787bd0d7dc4cf0b3f49022172f9d25e91f4d8a76702a96e'
FIELDS = {'source', 'version_code', 'version_name', 'bytes', 'apk_url', 'apk_sha256', 'certificate_sha256'}
PATH = re.compile(r'/download/android/([a-f0-9]{40})/ULADIM\.apk\Z')
MAX_BYTES = 512 * 1024 * 1024
CHUNK = 64 * 1024


def safe_root(value):
    return (isinstance(value, str) and 1 < len(value) <= 512 and value.startswith('/')
            and not value.startswith('//') and not any(ord(c) < 32 or ord(c) == 127 for c in value)
            and str(PurePosixPath(value)) == value
            and '..' not in PurePosixPath(value).parts)


def fingerprint(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns,
            info.st_uid, info.st_mode, info.st_nlink)


class FileBody:
    def __init__(self, fd, start, length, identity):
        self.fd, self.start, self.length, self.identity = fd, start, length, identity

    def __iter__(self):
        offset, left = self.start, self.length
        try:
            while left:
                chunk = os.pread(self.fd, min(CHUNK, left), offset)
                if not chunk or fingerprint(os.fstat(self.fd)) != self.identity:
                    raise OSError('Accepted download changed during transfer')
                offset += len(chunk); left -= len(chunk)
                yield chunk
        finally:
            self.close()

    def close(self):
        if self.fd is not None:
            os.close(self.fd); self.fd = None


class NativeDownload:
    def __init__(self, root, *, trusted_uid=0):
        self.root, self.trusted_uid = root, trusted_uid
        self.lock = threading.Condition()
        self.verified = OrderedDict()
        self.verifying = set()

    def _directory(self):
        if not safe_root(self.root): raise ValueError('Download disabled')
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        fd = os.open('/', flags)
        try:
            # Walk descriptors so a symlink in any component cannot escape the
            # configured cache. Only the final cache's permissions are authority.
            for part in PurePosixPath(self.root).parts[1:]:
                child = os.open(part, flags, dir_fd=fd)
                os.close(fd); fd = child
            info = os.fstat(fd)
            if info.st_uid != self.trusted_uid or info.st_mode & 0o022:
                raise ValueError('Unsafe download directory')
            return fd
        except BaseException:
            os.close(fd); raise

    def _file(self, directory, name, maximum):
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=directory)
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != self.trusted_uid
                    or info.st_mode & 0o022 or info.st_nlink != 1 or not 0 < info.st_size <= maximum):
                raise ValueError('Unsafe download file')
            return fd, info
        except BaseException:
            os.close(fd); raise

    def _accepted(self, source=None):
        directory = self._directory()
        apk = None
        try:
            manifest, before = self._file(directory, 'release.json', 4096)
            try:
                raw = os.read(manifest, 4097)
                if len(raw) != before.st_size or fingerprint(os.fstat(manifest)) != fingerprint(before):
                    raise ValueError('Download metadata changed')
            finally: os.close(manifest)
            def unique(pairs):
                value = {}
                for key, item in pairs:
                    if key in value: raise ValueError('Duplicate release field')
                    value[key] = item
                return value
            value = json.loads(raw, object_pairs_hook=unique)
            if (not isinstance(value, dict) or set(value) != FIELDS or not isinstance(value['source'], str)
                    or not re.fullmatch('[a-f0-9]{40}', value['source']) or source is not None and value['source'] != source
                    or type(value['version_code']) is not int or not 312001 <= value['version_code'] <= 2100000000
                    or type(value['bytes']) is not int or not 0 < value['bytes'] <= MAX_BYTES
                    or not isinstance(value['apk_sha256'], str) or not re.fullmatch('[a-f0-9]{64}', value['apk_sha256'])
                    or value['certificate_sha256'] != CERTIFICATE
                    or value['apk_url'] != 'https://github.com/pro100umarchikgamer-lgtm/lifeos/releases/download/uladim-native-' + value['source'][:12] + '/ULADIM.apk'
                    or value['version_name'] is not None and (not isinstance(value['version_name'], str) or not re.fullmatch(r'[A-Za-z0-9._+\-]{1,64}', value['version_name']))):
                raise ValueError('Unaccepted download metadata')
            apk, info = self._file(directory, 'ULADIM.apk', MAX_BYTES)
            identity = self.verify_file(apk, info, value)
            result, apk = (apk, identity, value), None
            return result
        finally:
            if apk is not None: os.close(apk)
            os.close(directory)

    def manifest(self):
        try:
            fd, _, value = self._accepted()
        except (OSError, ValueError, TypeError, KeyError):
            return None
        os.close(fd)
        return value

    def verify_file(self, apk, info, value, *, rehash=False):
        identity = fingerprint(info)
        if info.st_size != value['bytes'] or os.pread(apk, 4, 0) != b'PK\x03\x04':
            raise ValueError('Download size/type mismatch')
        key = identity + (value['apk_sha256'],)
        with self.lock:
            while key in self.verifying:
                self.lock.wait()
            needs_hash = rehash or key not in self.verified
            if needs_hash:
                self.verified.pop(key, None)
                self.verifying.add(key)
            else:
                self.verified.move_to_end(key)
        if needs_hash:
            valid = False
            try:
                digest, offset = hashlib.sha256(), 0
                while offset < info.st_size:
                    chunk = os.pread(apk, min(CHUNK, info.st_size-offset), offset)
                    if not chunk: raise ValueError('Incomplete download file')
                    digest.update(chunk); offset += len(chunk)
                if digest.hexdigest() != value['apk_sha256'] or fingerprint(os.fstat(apk)) != identity:
                    raise ValueError('Download digest mismatch')
                valid = True
            finally:
                with self.lock:
                    if valid:
                        self.verified[key] = None
                        if len(self.verified) > 32:
                            self.verified.popitem(last=False)
                    self.verifying.remove(key)
                    self.lock.notify_all()
        if fingerprint(os.fstat(apk)) != identity: raise ValueError('Download changed after verification')
        return identity

    @staticmethod
    def _empty(status, extra=()):
        return status, [('Content-Length', '0'), ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff'), *extra], []

    def response(self, env):
        match = PATH.fullmatch(env.get('PATH_INFO', ''))
        if not match or env.get('QUERY_STRING'): return self._empty(404)
        method = env.get('REQUEST_METHOD', '')
        if method not in ('GET', 'HEAD'): return self._empty(405, [('Allow', 'GET, HEAD')])
        try: fd, identity, value = self._accepted(match[1])
        except (OSError, ValueError, TypeError, KeyError): return self._empty(404)
        return self.file_response(env, fd, identity, value)

    def file_response(self, env, fd, identity, value):
        method = env.get('REQUEST_METHOD', '')
        size = value['bytes']
        etag = '"sha256-' + value['apk_sha256'] + '"'
        headers = [('Content-Type', 'application/vnd.android.package-archive'),
                   ('Content-Disposition', f'attachment; filename="ULADIM-{value["version_code"]}.apk"'),
                   ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff'),
                   ('Accept-Ranges', 'bytes'), ('ETag', etag),
                   ('X-ULADIM-Version-Code', str(value['version_code'])),
                   ('X-ULADIM-APK-SHA256', value['apk_sha256']), ('X-ULADIM-Certificate-SHA256', value['certificate_sha256'])]
        if 'source' in value:
            headers.append(('X-ULADIM-Source', value['source']))
        else:
            headers.append(('X-ULADIM-Origin', 'control'))
        start, end, status = 0, size-1, 200
        spec = env.get('HTTP_RANGE', '') if method == 'GET' else ''
        if spec and env.get('HTTP_IF_RANGE', etag) == etag:
            parsed = re.fullmatch(r'bytes=([0-9]{0,20})-([0-9]{0,20})', spec) if len(spec) <= 64 else None
            if parsed and (parsed[1] or parsed[2]):
                if parsed[1]:
                    start = int(parsed[1]); end = min(int(parsed[2]), size-1) if parsed[2] else size-1
                else:
                    suffix = int(parsed[2]); start = max(0, size-suffix)
                    if not suffix: start = size
            if not parsed or not (parsed[1] or parsed[2]) or not 0 <= start <= end < size:
                os.close(fd)
                return self._empty(416, [('Content-Range', f'bytes */{size}'), ('Accept-Ranges', 'bytes'), ('ETag', etag)])
            status = 206; headers.append(('Content-Range', f'bytes {start}-{end}/{size}'))
        headers.append(('Content-Length', str(end-start+1)))
        if method == 'HEAD':
            os.close(fd); return status, headers, []
        return status, headers, FileBody(fd, start, end-start+1, identity)
