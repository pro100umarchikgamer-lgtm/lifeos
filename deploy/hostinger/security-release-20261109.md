# Security checkpoint — 9 November 2026

Deployed backend: `c2309d6612ad60eda124622a031f443dcc5c0f3b`, whose full
backend/Flutter/Android validation had passed before deployment. Clarity changes
from later branch commits are not part of this installed release.

Verified on the existing VPS:

- PostgreSQL migrations 001–009; no schema change in this release.
- Fresh AES-GCM backup authenticated and restored into isolated PostgreSQL with
  no network, ports or persistent volume. Counts in 56 stable tables and all
  migration digests matched. The temporary container was removed.
- Actual rollback to the previous `69ebda9` image, HTTPS asset verification, and
  reactivation of `c2309d6` succeeded. The existing pgdata volume, encryption key,
  production environment and Caddy configuration were preserved.
- API, mail and PostgreSQL became healthy. Database and edge monitor oneshots
  returned success after the final activation.
- The first attempt rolled back because the monitor could not traverse private
  extracted asset directories. The fix grants the existing monitor group read
  access to public reference assets; checks were retained. The deployment helper
  now also verifies this access before building another image.
- 33 direct DNS/TLS/edge checks passed on the VPS. A separate GitHub Codespace
  passed all 49 HTTPS assertions, including source hashes, HEAD, closed signup,
  unauthorized customer operations, forged session cookie, CORS and closed
  Control/API domains. A workstation proxy probe was incomplete; it is not
  counted as a full successful independent run. Zero-downtime deployment is not
  claimed.

Accounts/staff/owner were absent at the read-only inventory. Owner email,
verified registration and personal MFA enrollment are required before exposing
Control. Public registration and real payments remain closed.

A persistent tested rollback wrapper is installed at:
`/etc/uladim/checkpoints/c2309d6612ad60eda124622a031f443dcc5c0f3b/rollback-verified-release.sh`.
It restores the previous image and the previous monitoring working directory.

Remaining gates include owner setup, SSH hardening approval and provider
emergency access, independent off-server backup storage, fresh SMTP delivery,
authenticated production acceptance, physical iPhone/iPad and Android testing.
Detailed infrastructure findings are retained in the owner's private report.
The newer Android CI runs failed at emulator/test-launch transport, so later
branch changes are not presented as fully validated or deployed.
