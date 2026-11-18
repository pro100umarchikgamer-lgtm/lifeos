# Accepted APK download on the site origin

The source now supports `GET` and `HEAD` at:

`https://getuladim.space/download/android/<full-40-character-source>/ULADIM.apk`

This serves bytes from one accepted local APK. It never fetches a request URL,
redirects to GitHub, opens a request-selected file, or exposes a private artifact
directory. Source support is not evidence that the production endpoint is active.
An empty `NATIVE_DOWNLOAD_DIR` disables the source-based legacy route with 404.

A GitHub-backed release keeps the existing seven-field manifest and its exact
GitHub `apk_url`. The read-only legacy cache contains the accepted `release.json`
and corresponding `ULADIM.apk`. The candidate API also supports the distinct
Control upload manifest described below. The retained public APK is provisioned
outside the repository and API image.

## Runtime preparation for the next reviewed release

1. Complete the existing native acceptance first: exact source, package,
   versionCode, actual file size and SHA-256, and the retained signing certificate
   `5fa37e4abf1ec90d5787bd0d7dc4cf0b3f49022172f9d25e91f4d8a76702a96e`.
   The backend checks the accepted tuple and file hash; it does not replace APK
   signature verification by the release installer.
2. Create a fresh source-specific host directory, for example
   `/var/lib/uladim/native-download/<full-source>`, owned by `root:10001`, mode
   `0750`. Copy the already accepted APK and exact public tuple into exclusive
   temporary files. Check their bytes/hashes and read them back, then fsync and
   rename into a complete directory. Both final files must be regular, owned by
   `root:10001`, mode `0640`, with one link each. Copy files; do not hardlink them.
   Do not overwrite an accepted directory or modify either file in place.
3. Append this read-only bind mount to the next reviewed API runtime override,
   keeping its other mounts and protected environment intact:

   ```json
   {
     "services": {
       "api": {
         "environment": {"NATIVE_DOWNLOAD_DIR": "/run/uladim/native-download"},
         "volumes": [{
           "type": "bind",
           "source": "/var/lib/uladim/native-download/<full-source>",
           "target": "/run/uladim/native-download",
           "read_only": true
         }]
       }
     }
   }
   ```

   The container retains user `10001:10001`. The cache directory and all path
   components must be real directories, with no symlinks. Only root may write the
   cache. The backend always opens the two fixed filenames and rejects symlinks,
   extra hardlinks, nonregular files and group/world write permissions.
4. The candidate `deploy/hostinger/Caddyfile.control-platform` routes both
   `/download/android/*` and `/download/release.json` to the API. An already
   installed edge can still serve its own legacy manifest. Compare that exact
   tuple to the candidate API's verified legacy manifest before switching the
   installed edge. Activate the API and mounts through the reviewed release
   procedure.
5. Verify the real site-origin `HEAD`, full download and a Range response after
   deployment. Check the complete downloaded bytes and retained signer against
   the same accepted tuple. Confirm there is no redirect or cookie issuance.
   Until these checks pass, first-party APK delivery remains unverified.

## UI readiness contract

After accepting the existing public release JSON, compute the site-relative URL
from its full source and request `HEAD` without query parameters, credentials or
redirects. Activate the first-party link only for 200 with all of:

| Response header | Required value |
| --- | --- |
| `Content-Type` | `application/vnd.android.package-archive` |
| `Content-Length` | Exact accepted `bytes` |
| `ETag` | `"sha256-<accepted apk_sha256>"` |
| `X-ULADIM-Source` | Full accepted source |
| `X-ULADIM-Version-Code` | Accepted versionCode in decimal |
| `X-ULADIM-APK-SHA256` | Exact accepted APK SHA-256 |
| `X-ULADIM-Certificate-SHA256` | Exact retained certificate SHA-256 |
| `Content-Disposition` | `attachment; filename="ULADIM-<versionCode>.apk"` |

A missing cache, mismatch, network error or stale response must retain the
explicit GitHub fallback. A fallback is not evidence of first-party delivery.
The UI must ignore responses after navigation or selection of another release.

## Streaming and failure behavior

The first read verifies the complete file before returning any APK bytes.
Each worker caches up to 32 verified file identities and digests. Concurrent
requests for the same object share its verification, while different objects
can verify independently. Transfers use at most 64 KiB per read and retain the verified file
descriptor; atomic replacement cannot substitute bytes in an active transfer.
In-place changes or truncation abort a transfer. All responses are `no-store`.

`HEAD` reports the full accepted size and emits no body. `GET` supports a single
`bytes=start-end`, open-ended or suffix range, returning 206 with exact
`Content-Range` and length. Invalid/multiple/unsatisfiable ranges return 416 with
`bytes */<size>`. A matching strong `If-Range` permits a range; a mismatch returns
the complete 200 representation. Downloads never issue or require an account
cookie. The existing HTTPS, exact host and IP rate limits still apply.

Only site-origin requests can reach the stream. Unknown source, any query,
unconfigured/unsafe/missing cache or inconsistent tuple/file returns 404 without
filesystem or artifact details. Control admission and API-host boundaries remain
unchanged.

Focused local verification:

```sh
python3 -m unittest backend.tests.test_native_download -v
```

## Publishing signed Android updates from Control

The owner and release manager can open **Android releases** on the admitted
Control host. The effective permissions are `android.read` (list),
`android.upload` (draft, upload, validate, cancel) and `android.publish`
(publish). A staff restriction can remove an individual permission.

1. Create a draft and select the finished, signed APK. The server measures the
   uploaded bytes and computes their SHA-256. Uploading leaves the public
   selection on the previous release.
2. Validate the uploaded draft. The official Android signature verifier checks
   the actual signers of the pinned file. The Android resource tool reads the
   package, versionCode and versionName from its binary manifest. The accepted
   package is `app.lifeos.lifeos` and the retained signer is
   `5fa37e4abf1ec90d5787bd0d7dc4cf0b3f49022172f9d25e91f4d8a76702a96e`.
   A permanent error appears on the rejected draft. Cancel it and create a new
   draft for corrected bytes. A temporary verifier or storage failure permits
   retry.
3. Review the verified version, size, signer and SHA-256, then select **Publish**.
   The server checks the file identity and digest and requires a versionCode
   strictly greater than both the current managed release and the configured
   legacy baseline. The database commits the release, current pointer and
   audit event together. The previous release remains available at its immutable
   URL. Cancel records the private file cleanup together with its history
   entry. Interrupted cleanup resumes on a retry or the next draft/upload.
   Published bytes remain outside the cleanup queue.
4. After a successful publication, check the public download card and its
   same-origin HEAD, Range and full GET. An active transfer of an older release
   retains the originally opened file descriptor.

### Candidate runtime configuration

- Keep the existing root-owned `NATIVE_DOWNLOAD_DIR` read-only and mounted.
  Its verified manifest supplies the initial current selection and its version
  floor. Before the first managed release, the backend must be able to validate
  the actual mounted legacy tuple and its complete file hash. Provision a
  missing baseline from the previously accepted artifact and manifest.
- Create a **separate** persistent directory for `NATIVE_PUBLISH_DIR` on the
  host, owned by API UID 10001, mode 0700. Bind it read-write to the API workers
  at a normalized absolute path, such as `/var/lib/uladim/android-publications`.
  Both names must be real directories with symlink-free paths. The image has a
  read-only root filesystem and its temporary filesystem is too small for real
  release files. Keep a coordinated database and volume backup covering every
  published file. Never overwrite or prune published files manually.
- The API image needs Debian's free `apksigner`, `aapt` and headless Java
  runtime, including Debian’s standard `prlimit` utility for the native
  manifest reader. It invokes the installed binaries at `/usr/bin/apksigner` and
  `/usr/bin/aapt`. The verifier restricts its Java heap, execution time and
  diagnostic output. A per-volume lock allows one upload or verifier at a time.
  The limit is 512 MiB per binary and eight open drafts. Budget the volume for
  all historic published files and unfinished drafts.
- Permit the binary POST to the exact Control path
  `/control/api/android-releases/upload` at the edge, retaining the ordinary
  2 MiB JSON limit elsewhere. Use the backend for the site-host
  `/download/release.json` response. Before switching an existing generated
  edge configuration, compare the candidate backend's legacy tuple and HEAD
  with the exact currently exposed release. The checked-in configuration does
  not confirm a live cutover.

### Owner-uploaded public manifest

GitHub releases still use their exact seven-field tuple and source URL. A signed
file supplied through Control carries this alternative tuple:

```json
{
  "origin": "control",
  "version_code": 400002,
  "version_name": "1.2.3",
  "bytes": 123456,
  "apk_url": "/download/android/sha256/<64-lowercase-hex>/ULADIM.apk",
  "apk_sha256": "<64-lowercase-hex>",
  "certificate_sha256": "5fa37e4abf1ec90d5787bd0d7dc4cf0b3f49022172f9d25e91f4d8a76702a96e"
}
```

The numbers above illustrate the schema. The URL digest must match the
`apk_sha256` field exactly. The same-origin HEAD returns
`X-ULADIM-Origin: control`, actual size, versionCode, SHA-256, certificate,
ETag, APK MIME type and download filename. The source header belongs to legacy
Git-backed selections. Only published files resolve at the digest URL.

### Local verification

Install Android build-tools (`apksigner` and `aapt`) and run the focused suite
from the repository root:

```sh
ULADIM_REQUIRE_APK_TOOLS=1 python -m unittest backend.tests.test_apk_verifier backend.tests.test_android_releases backend.tests.test_native_download -v
```

Set `LIFEOS_TEST_DATABASE_URL` to a disposable `lifeos_test` PostgreSQL database
to run the same transition and concurrency tests against PostgreSQL. Each test
uses a fresh schema. The tiny packages in `tool/testdata/android-releases` carry
a disposable fixture signature. Their generator uses aapt, keytool, apksigner
and an Android framework resource package. Only the isolated test verifier
accepts the fixture signer. The API image uses the fixed retained certificate.
