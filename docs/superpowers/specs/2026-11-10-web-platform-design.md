# ULADIM Web: existing client, shared service

Execute the user's complete product brief against da2301c. Keep vanilla JavaScript,
Python-served static assets, the existing HttpOnly session/CSRF and sync protocol.
No Android, database, OAuth, Control, production or registration-policy changes.

Approaches: extend the existing client (selected: preserves deployment, CSP and contracts);
Flutter Web would share UI but requires replacing browser storage integration;
a new SPA framework would introduce a parallel build and unnecessary migration.

Deliver calendar events, recurrence and timezone-aware agenda; task filtering,
compact notes with full editor, Today quick actions/agenda/budgets; validated finance
forms; cancel-before-commit deletion (4s, no fabricated restore); cohesive adaptive
navigation and themes. Persist only interface preferences. Reuse 16 catalogs;
new copy has reviewed Russian and Uzbek, explicitly marked fallback elsewhere.
API gaps are release limitations, never simulated working features.

Verify domain calculations, browser CRUD against disposable actual WSGI service,
all four widths/both themes, existing security/finance/PWA acceptance. Add independent
web PR checks without invoking Android builds. Review via draft PR to launch branch.
A synthetic preview must be labeled and never represented as production integration.
