# Interface languages

ULADIM ships the same 16 interface languages on Android, the web app, public
pages and Control: Azerbaijani, German, English, Spanish, French, Armenian,
Italian, Georgian, Kazakh, Kyrgyz, Portuguese, Russian, Tajik, Ukrainian,
Uzbek Cyrillic and Uzbek Latin.

Native source packs are `assets/locales/<tag>.json`. Pack version 17 contains
895 strings per language, including the complete in-app help section. Shared
native controls read the selected `LanguagePackScope`; legal/help links pass
the selected language to the public site without changing their fragment.

Web packs reuse the native strings and retain 21 web-specific keys. Additional
web/public/Control copy uses 1490 explicit source IDs in
`tool/web_i18n_source.json`; reviewed translations live in
`assets/web-locales/<tag>.json`. Empty Russian overrides are intentional: the
manifest itself contains the Russian source. English and Uzbek overrides fill
only the entries absent from their authored source dictionaries. Other language
files may contain excluded audit candidates; the compiler reports these as
unused and never inserts technical enums into the interface catalog.

Build and verify the shipped catalog:

```sh
python3 tool/validate_packs.py --release
python3 tool/build_web_translations.py --translations-dir assets/web-locales --require-complete
python3 tool/build_web_translations.py --translations-dir assets/web-locales --require-complete --check
npm test
```

The completeness check requires actual selected-language values for every
source ID. English fallback does not count as a translated entry. Adding source
copy requires registering its static ID and supplying every supported language;
preserve template placeholders and check the rendered state that uses it.

`i18n.js` translates explicit UI source values and known system-notification
templates. It never scans arbitrary DOM text or translates saved records,
personal names, support messages or administrator announcements. Source and
template parameters render as text. API fields, authority checks, currencies,
URLs, hashes, store names and server confirmation commands retain their exact
values. Referrals expose only the permitted short aliases.

Web Push stores the selected language alongside existing encrypted subscription
preferences. A language-only refresh preserves opt-in and pending reminders.
Notification history uses fixed system-message keys, so the selected interface
language can change without rewriting user or announcement content.

The public `?lang=<tag>` handoff accepts one supported language only. Invalid or
duplicate values leave the saved preference unchanged and show a warning. It
does not establish an account or staff role. Operating-system permission
dialogs and native browser controls retain the device's own language settings.

Transactional verification, password-recovery, new-address and existing early-access emails use 14 translated templates in every language. The selected request language travels only inside the existing encrypted mail payload; old queued jobs retain their original Russian fallback. Context-local request state resets after each request and does not establish identity or authorization.
