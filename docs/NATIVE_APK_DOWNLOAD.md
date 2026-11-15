# Accepted APK download on the site origin

The source now supports `GET` and `HEAD` at:

`https://getuladim.space/download/android/<full-40-character-source>/ULADIM.apk`

This serves bytes from one accepted local APK. It never fetches a request URL,
redirects to GitHub, opens a request-selected file, or exposes a private artifact
directory. Source support is not evidence that the production endpoint is active.
An empty `NATIVE_DOWNLOAD_DIR` disables the endpoint with 404.

The existing seven-field `/download/release.json` contract remains unchanged.
Its GitHub `apk_url` records the original approved artifact location. The download
cache contains that exact accepted JSON as `release.json` and the corresponding
bytes as `ULADIM.apk`. No APK is added to Git or the backend image.

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
4. The checked-in `deploy/hostinger/Caddyfile.control-platform` already routes
   `/download/android/*` through its existing catch-all API reverse proxy. The
   exact `/download/release.json` edge response remains separate and unchanged.
   The currently installed older API does not gain the route from a source edit.
   Update the backend and cache/mount only through the next reviewed release;
   previously pinned deployment/recovery helpers are left unchanged.
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

The first read verifies the complete file before returning any APK bytes. An
identity/size/timestamp/digest cache avoids hashing the same immutable file for
every request. Transfers use at most 64 KiB per read and retain the verified file
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
