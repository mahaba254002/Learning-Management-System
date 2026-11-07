# Design system

Skynet's look comes from its login page and logo. The tokens live in [frontend/src/styles/tokens.css](../frontend/src/styles/tokens.css). Use them instead of new colour codes.

| Role | Token | Value |
|---|---|---|
| Accent (primary buttons, selection, links) | `--color-accent` | `#026aa7` Skynet blue |
| Accent hover / pressed | `--color-accent-hover` | `#075c8d` deep blue |
| Selected row or menu item | `--color-selected` | `#e8f1f8` |
| Primary text | `--color-ink` | `#172c3e` |
| Secondary text | `--color-ink-soft` | `#46596b` |
| Meta and captions | `--color-ink-muted` | `#5b6d7e` |
| Page background | `--color-page` | `#f5f7fa` paper |
| Cards and panels | `--color-paper` | `#ffffff` |
| Inputs, notices, table heads | `--color-canvas` | `#eef2f6` |
| Hairlines / input borders | `--color-line` / `--color-line-strong` | `#dde4ea` / `#c3cfd9` |
| Success / warning / error | `--color-positive` / `--color-warning` / `--color-negative` | `#1d6b3d` / `#8a5300` / `#b3261e` |

**Rules:**
- **Accent:** one, Skynet blue. The logo red (`#aa251e`) stays in the logo and the thin margin line on course cards; inside the app, red means an error.
- **Type:** Inter only, weights 400, 500 and 600, sentence case everywhere. Panel headings are 18px; page titles are larger. Figures use tabular digits.
- **Spacing:** on a 4px grid. Corners are 4px for tags, 6px for buttons and inputs (as on the login page), 8px for panels.
- **Buttons:** `.btn` is the quiet default (white, hairline border); `.btn--primary` is the one main action on a screen.
- **Charts:** Skynet blue for the series that matters, neutral greys for the rest.
- **Signature:** the term or semester in session (e.g. *Term 3 · 2026*) sits in the top bar on every workspace page.
- **Course cards:** they look like exercise-book covers, in Skynet blues with ruled lines and a red margin.

The design pass used the unslop method by Damir Sokolovsky (@heydamir), CC BY 4.0.
