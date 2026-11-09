# Clarity: implementation review

This is an opt-in implementation in the existing PWA, not another account or API.
After a verified deployment, `/app?design=clarity` selects its interface. `/app`
keeps the current default until the owner chooses a visual direction. This route
has not yet been deployed to production.

The implementation introduces shared SVG icons, accessible names for record
menus and dialog close controls, named native dialogs, password-manager and OTP
hints, semantic financial colors, phone bottom navigation, tablet rail and desktop
sidebar. Today uses a task-first split layout on desktop and sequential sections
on phones. Existing API authorization, cookies, sync protocol and all 16 PWA
locale packs are reused unchanged.

Review screenshots contain disposable fixture records only. They are automated
Chromium renders at the stated viewports, not screenshots from physical Apple
hardware or production. The design is an implementation checkpoint, not the
completed redesign of every public, account and administrative screen.

Browser acceptance runs against both variants:

```
python -m tool.check_pwa_browser
ULADIM_DESIGN=clarity python -m tool.check_pwa_browser
```

It checks real record writes/retries, accessible navigation and dialogs, financial
text contrast across themes/palettes/system schemes, responsive viewports, all 16
locales, private-history clearing, logout and interface-only caching.

WebKit on the current HTTP loopback fixture did not retain the Secure session
cookie: login returned success but the next session request returned 401 and the
cookie list was empty. HTTPS WebKit/Safari acceptance remains a release gate;
production cookie protections were not weakened to make this test pass.
