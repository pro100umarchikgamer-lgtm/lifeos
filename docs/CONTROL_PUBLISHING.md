# Control publishing

In the signed-in ULADIM app, open **Profile** and choose **ULADIM Control**.
Complete the staff sign-in and MFA. The section selector shows **Public pages**
and **Android releases** according to the account’s effective permissions.

## Staff access

| Role | Publishing capabilities |
| --- | --- |
| `owner` | `pages.edit`, `pages.publish`, `android.read`, `android.upload`, `android.publish` |
| `content_editor` | `pages.edit` |
| `content_publisher` | `pages.edit`, `pages.publish` |
| `release_manager` | `android.read`, `android.upload`, `android.publish` |

Assign these roles through existing staff enrollment and delegation. Staff
permission restrictions remove specific capabilities. Existing roles outside
this table gain publishing access only when an eligible role is also assigned.
Existing Control admission, MFA and CSRF protections apply to each operation.

The chained Control audit records page draft saves, publications, restores to
draft and media uploads. It also records Android candidate creation, upload,
validation, publication and cancellation. Each publication commits its audit
event and public selection in the same database transaction.

## Publish a page

1. Open **Public pages** and select a route and content language. The selection
   applies to that page in that language. The Control interface keeps its own
   language.
2. Edit the editorial fields and ordered content blocks. Links and uploaded
   raster images use the typed controls. The page’s forms, account operations
   and download verification use the existing application behavior.
3. Select **Save draft**. Open **Preview draft** and review the saved revision.
   The public page continues to show its published revision or source content.
4. With `pages.publish`, enter a reason and select **Publish** from the saved
   draft preview. Check the public page in the selected locale. Other locales
   and routes retain their own published selections.
5. To recover earlier content, open **Revision history**, preview a revision and
   select **Restore as draft**. Enter an audit reason and save the restored
   draft. Revision zero is the original translated source. Review and publish
   the restored draft when it is ready. If a colleague has updated the same
   page and locale, reload its current state before retrying.

The editor covers `/`, `/account`, `/plans`, `/privacy`, `/terms`, `/support`,
`/delete-account`, `/status`, `/download`, `/faq`, `/early-access` and `/docs`
across the sixteen existing locales.

## Publish an Android release

1. Open **Android releases**, select **New candidate**, choose or drop the
   finished signed APK, then select **Upload APK**. The limit is 512 MiB. The
   server computes the checksum and measures the actual bytes as it streams the
   upload.
2. Select **Validate APK**. The server verifies the signature and reads the
   package and version from the APK itself. Review the package, versionCode,
   file size, signing certificate and SHA-256 shown on the candidate. The
   versionCode must exceed both the retained legacy build and the current
   Control publication.
3. Open **Review publication** and select **Publish APK**. This switches the
   download page to the validated build. Verify its public manifest, download
   and checksum from the site origin. Prior releases keep their original URLs.
4. Use **Cancel candidate** to discard an unpublished upload. A permanently
   rejected APK needs a fresh candidate containing corrected bytes. Retry a
   temporary storage or verifier failure on the existing candidate.

The accepted package is `app.lifeos.lifeos`. The retained direct-release signing
certificate SHA-256 is
`5fa37e4abf1ec90d5787bd0d7dc4cf0b3f49022172f9d25e91f4d8a76702a96e`.
Signing happens before upload. For the manifest, response headers and download
contracts, see [Native APK download](NATIVE_APK_DOWNLOAD.md).

## Prepare and verify the runtime cutover

1. Back up the database and preserve the active edge configuration. Run the
   published-page and Android-release migrations (`026` and `027`) through
   the normal reviewed migration service. Use the backend image with the
   official `apksigner` and `aapt` tools and headless Java installed.
2. Preserve the existing root-owned `NATIVE_DOWNLOAD_DIR` read-only API mount
   permanently. It serves the legacy immutable
   `/download/android/<source40>/ULADIM.apk` URL and retains the original GitHub
   fallback. Before routing the manifest through the backend, provision this
   cache with the exact accepted seven-field `release.json` and its APK. Verify
   the actual signed bytes, package, signer, version, size and full SHA-256
   against the accepted release. See the cache ownership and mode requirements
   in [Native APK download](NATIVE_APK_DOWNLOAD.md).
3. Provision a separate private persistent host directory owned by `10001:10001`
   with mode `0700`. Use a real path with symlink-free components. Set
   `ULADIM_ANDROID_PUBLICATIONS_DIR` to that host path and append the
   [Control publishing Compose override](../deploy/hostinger/compose.control-publishing.yaml)
   to the reviewed runtime overrides. It binds that directory read-write to API
   workers as `NATIVE_PUBLISH_DIR=/run/uladim/android-publications`. Preserve
   the read-only legacy mount and the API container’s read-only root. Budget
   for the full published history and active candidates. Back up the private
   volume in coordination with the database.
4. Before an edge reload, check the candidate backend directly on the private
   network using the site host and HTTPS forwarding. Its `/download/release.json`
   must match the already published tuple field-for-field. Check the legacy
   `HEAD`, a single-byte `Range` request and the SHA-256 of a complete GET. A
   missing or mismatching legacy manifest blocks the cutover.
5. Review the active edge config with the two source routing changes in
   [Caddyfile.control-platform](../deploy/hostinger/Caddyfile.control-platform).
   Only `POST /control/api/android-releases/upload` on the Control host gets
   the 512 MiB body limit. The ordinary 2 MB edge limit stays on other routes.
   On the public site host, the exact `/download/release.json` location must
   proxy to the backend with `Cache-Control: no-store`. Replace the old static
   manifest handler as part of a single validated Caddy configuration reload
   after the backend and both mounts are ready. The historical edge installer
   pins and renders the old static handler. Use a separately reviewed cutover
   for this resolver.
6. Confirm that the site-origin manifest still returns the accepted legacy
   tuple, the legacy APK passes HEAD/Range/full GET checks, and the Control host
   retains staff admission and route isolation. Exercise genuinely signed test
   APK publishing on disposable staging storage and data. Use only a separately
   accepted real APK for any later production publication.

Before the first managed APK publication, a failing edge cutover can restore the
saved configuration while keeping both mounts and the migrated database. After
publication, retain a compatible resolver, database and blobs for the manifest
and published digest URLs during any application rollback. Keep published bytes,
page history and audit records. Restore unwanted page content as a new draft and
publish it. Replace an unwanted Android build with a newly signed build with a
higher versionCode so installed clients can update normally.
