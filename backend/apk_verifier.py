"""Read identity from one signed, already-open Android package."""
import os
import re
import selectors
import subprocess
import time

from .native_download import CERTIFICATE
from .service import Failure, require


class ApkVerifier:
    def __init__(self, *, apksigner='/usr/bin/apksigner', aapt='/usr/bin/aapt', certificate=CERTIFICATE):
        self.apksigner = apksigner
        self.aapt = aapt
        self.certificate = certificate

    @staticmethod
    def _run(args, fd, invalid):
        # The descriptor remains pinned even if a racing cancellation unlinks
        # the file. No paths or options come from the owner/browser.
        try:
            process = subprocess.Popen(args,
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, pass_fds=(fd,),
                env={'PATH': '/usr/bin:/bin', 'LANG': 'C'})
        except OSError:
            raise Failure('apk_verifier_unavailable', 503) from None
        deadline = time.monotonic() + 90
        output = bytearray()
        with process.stdout as pipe, selectors.DefaultSelector() as selector:
            selector.register(pipe, selectors.EVENT_READ)
            try:
                while True:
                    left = deadline - time.monotonic()
                    if left <= 0 or not selector.select(left):
                        raise Failure('apk_verifier_timeout', 503)
                    chunk = os.read(pipe.fileno(), 16384)
                    if not chunk:
                        break
                    output.extend(chunk)
                    require(len(output) <= 1024 * 1024, invalid)
                try:
                    code = process.wait(timeout=max(0, deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    raise Failure('apk_verifier_timeout', 503) from None
                if code in (126, 127) or code < 0:
                    raise Failure('apk_verifier_unavailable', 503)
                require(code == 0, invalid)
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait()
        return output.decode('utf-8', errors='replace')

    def verify(self, fd):
        path = '/proc/self/fd/' + str(fd)
        signature = self._run([self.apksigner, '-JXmx128M', 'verify', '--verbose', '--print-certs', path], fd, 'apk_signature')
        counts = re.findall(r'^Number of signers: ([0-9]+)$', signature, re.M)
        digests = re.findall(r'^(?:Signer #[0-9]+|V[0-9.]+ Signer):? certificate SHA-256 digest: ([A-Fa-f0-9]{64})$', signature, re.M)
        require(counts == ['1'] and {s.lower() for s in digests} == {self.certificate}, 'apk_signer')
        # The native tool may map the APK for random reads. Bound its heap
        # separately, allowing those file-backed mappings for a large APK.
        manifest = self._run(['/usr/bin/prlimit', '--data=134217728', '--', self.aapt,
                              'dump', 'xmltree', path, 'AndroidManifest.xml'], fd, 'apk_manifest')
        # Only attributes belonging to the document's manifest element count.
        root = re.search(r'^([ ]*)E: manifest \(line=\d+\)\n((?:[ ]+A: [^\n]*\n)+)', manifest + '\n', re.M)
        require(root is not None, 'apk_manifest')
        attrs = root[2]
        packages = re.findall(r'^ +A: package="([^"]+)"(?: \(Raw: "[^"]*"\))?$', attrs, re.M)
        require(packages == ['app.lifeos.lifeos'], 'apk_package')
        require(not re.search(r'^ +A: (?:split=|[^ ]*:versionCodeMajor\(|[^ ]*:isFeatureSplit\()', attrs, re.M), 'apk_manifest')
        codes = re.findall(r'^ +A: [^ :]+:versionCode\(0x0101021b\)=\(type 0x1[01]\)0x([0-9a-fA-F]{1,8})$', attrs, re.M)
        names = re.findall(r'^ +A: [^ :]+:versionName\(0x0101021c\)="([A-Za-z0-9._+\-]{1,64})"(?: \(Raw: "[^"]*"\))?$', attrs, re.M)
        require(len(codes) == 1 and 0 < int(codes[0], 16) <= 2100000000 and len(names) == 1, 'apk_manifest')
        return {'package_name': packages[0], 'version_code': int(codes[0], 16),
                'version_name': names[0], 'certificate_sha256': self.certificate}
