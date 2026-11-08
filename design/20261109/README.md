# ULADIM · design study 01

These are interactive design proposals with synthetic data, not a second account
system or a production application. No form transmits data. They do not replace
the live interface until the owner selects a direction.

Open index.html using a local static server. Query parameters select a proposal:
`?direction=clarity&screen=today`, `signal`, or `bloom`. Screens: home, today,
finance, account, tasks, notes, family, plans, apply, login, support and control.

| Direction | Structure and visual language | Tradeoff |
| --- | --- | --- |
| Clarity — preferred starting point | Neutral workspace, slim navigation, restrained violet accent, rows rather than nested cards, spacious financial analysis | Precise and quiet; relies on typography rather than decoration |
| Signal | Dark command workspace, mint signals, denser metric strip, straight panels, operational emphasis | Strong focus and contrast; needs an equally considered daylight counterpart |
| Bloom | Warm surfaces, softer corners, lavender accents, relaxed agenda and personal planning | Friendlier, less dense; fewer simultaneous controls on small screens |

All three use one coherent set of SVG strokes, explicit labels, keyboard focus,
44px form controls, phone bottom navigation, tablet rail and desktop sidebar.
Custom palettes are shown in account settings. Financial income and expenditure
use distinct series with text labels; currencies are not mixed into a total.

Run `python -m tool.capture_design_concepts` with Playwright Chromium and Pillow.
It renders all 12 screens in three concepts at 390×844, 820×1180 and 1440×1000,
checks horizontal overflow and actual task interaction, and creates overview sheets.
This is viewport simulation, not physical iPhone/iPad or Safari acceptance.

The proposals show Russian sample copy. Production localization stays on the
existing 16 catalogs. After selection, implement the approved system using those
catalogs and the existing API/cookies, including a full locale/accessibility pass.
Plan distinctions in these mockups are proposals; the deployed closed-test server
catalog currently enables all feature flags for Free/Plus/Premium with no sales.

Selection is an owner decision. Security, session lifecycle, login labels and
automated regression work proceed independently. Do not expose Control as a
side effect of choosing or implementing a design.
