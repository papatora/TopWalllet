# TopWallet Explorer — DESIGN.md

> Master brand guideline for the local wallet-tracking explorer. Every page, view
> and component is built FROM this file (`assets/css/tokens.css` is its code form,
> `design/styleguide.html` is its visual test). Change the system here first,
> never inline in a view.

## 1. Direction

**Target look: Arkham Intelligence (arkm.com).** A web3 on-chain intelligence
terminal, not a consumer web2 product. Near-black navy canvas, hairline panels,
monospace for anything that is chain data, one electric blue for action,
green/red reserved strictly for money direction.

Scope: **Robinhood Chain (4663) only.** No chain switcher — the chain pill is a
locked status indicator.

### Lessons applied (styles.refero.design — Linear, Factory)
- Elevation = contrast + hairline borders, **not shadows** (shadows only on floating menus).
- **One chromatic accent** (blue) for actions/active state. Semantic colors (green/red/amber) are data, never decoration.
- Weight cap **600**. No 700+ headings.
- Mono is for data: addresses, tx hashes, numbers, eyebrow labels. Sans is for UI and prose.
- Tight radius vocabulary: 4 / 6 / 10 / pill.
- 4px base grid; dense rows, generous section gaps.

### Lessons applied (greenlight AI workflow — anti-slop)
- Design system first → styleguide test page → views built from components only.
- Icons live as discrete assets (`assets/icons/sprite.svg`), never ad-hoc inline paths in views.
- No purple gradients, no generic rounded cards everywhere, no emoji markers.
- Motion only where it carries meaning: graph flow dots, skeleton loading, menu fade.

## 2. Color tokens

| Token | Hex | Role |
|---|---|---|
| `--bg` | `#0A0C11` | Page canvas |
| `--bg-sunk` | `#07080C` | Graph canvas, inset wells |
| `--panel` | `#10131A` | Panels, tables, nav menus |
| `--panel-2` | `#151922` | Raised rows, segmented track, inputs |
| `--panel-3` | `#1B202A` | Hover fills |
| `--line` | `#222834` | Panel borders, table header rule |
| `--line-soft` | `#191D26` | Row dividers |
| `--line-strong` | `#2E3544` | Hover/focus borders |
| `--text` | `#EDF0F5` | Primary text, addresses |
| `--text-2` | `#A0A8B7` | Secondary text, nav links |
| `--text-3` | `#667085` | Labels, captions, placeholders |
| `--blue` | `#1E6FF1` | Primary action, active tab, focus |
| `--blue-hi` | `#4C8DFF` | Links, active sort arrow |
| `--green` | `#35C48A` | Money in / positive / buy |
| `--red` | `#EF5B63` | Money out / negative / sell |
| `--amber` | `#E7AE4B` | Warnings, bundles |

**Classification palette** (chips, graph nodes, facet swatches only):
DEV `#EF5B63` · SNIPER `#35C48A` · BUNDLER `#E7AE4B` · INSIDER `#A386FF` ·
AIRDROP_FARMER `#58B4D1` · CT_ATTRIBUTED `#4C8DFF` · MEV_BOT `#FF8A4C` ·
SMART_TRACKER `#F2C94C` · CLUSTER `#E36CB3` · GENERALIST `#7D8698`.

Podium metals: gold `#F2C94C`, silver `#B8C1D1`, bronze `#D38B4F` — rank 1–3 only.

## 3. Typography

| Role | Family | Size / weight / tracking |
|---|---|---|
| Page title | Inter | 28px / 600 / -0.02em |
| Section title | Inter | 15px / 600 / -0.01em |
| UI body | Inter | 13–14px / 400–500 |
| Big number | IBM Plex Mono | 24px / 500 / -0.02em, tabular |
| Table data | IBM Plex Mono | 12.5px / 400, tabular |
| Eyebrow / header | IBM Plex Mono | 11px / 500 / +0.08em UPPERCASE |
| Micro caption | IBM Plex Mono | 10px / 500 / +0.12em UPPERCASE |

Inter with `cv11, ss01` on. All numbers `font-variant-numeric: tabular-nums`.

## 4. Space, shape, elevation

- Base 4px. Scale: 4 8 12 16 20 24 32 40 56.
- Nav 56px. Table rows 56px (Arkham leaderboard density), mini rows 40px.
- Radius: `--r-sm 4px` chips/badges · `--r-md 6px` inputs/buttons · `--r-lg 10px` panels · pill for filter chips & segmented.
- Panels: `--panel` fill + 1px `--line`. No shadow.
- Floating (menus, search results, toasts): `--panel-2` + `--line-strong` + `0 16px 40px rgba(0,0,0,.5)`.

## 5. Components

| Component | Rule |
|---|---|
| **Nav** | Logo mark + wordmark (600, +0.06em). Links Inter 14/500 `--text-2`, active `--text` with 2px blue underline. Right: search (400px, `/` hint), chain status pill, rebuild icon button. |
| **Segmented (primary)** | Pill track `--panel-2`; active = white fill, black text (Arkham "Leaderboard" toggle). |
| **Tabs (panel)** | Mono 11.5 uppercase; inactive `--text-3`; active `--text` + 2px blue bottom rule. |
| **Dropdown** | 36px boxed button, icon + label + chevron; menu floating. |
| **Button primary** | `--blue` fill, white mono 11.5 uppercase +0.06em, 6px radius (Arkham "CREATE NEW ENTITY"). |
| **Button ghost** | transparent, 1px `--line`, `--text-2` → hover `--text`. |
| **Filter chip** | Pill, 1px colored border at 55% alpha, colored text, `×` to clear (Arkham Visualizer "× USD ≥ $0.1"). |
| **Label chip** | 4px radius, 10% tinted fill, colored text, 6px dot. |
| **Rank badge** | 22px circle, metal tint for 1–3. Podium uses hexagon badge. |
| **Token avatar** | Circle, hue derived from contract address, 2 letters mono. Stacks overlap -7px. |
| **Table** | Header mono 11 uppercase `--text-2` with sort glyph; numeric columns right-aligned; zebra at 1.2% white; hover `--panel-3`. |
| **Stat strip** | One bordered row divided by hairlines — not separate cards. Eyebrow + big mono value + caption. |
| **Charts** | Hairline grid `--line-soft`, axis text mono 10 `--text-3`, area fill gradient 22%→0% of series color, emphasized last point, crosshair tooltip. |
| **Graph (Visualizer)** | Dot-grid sunk canvas, faint hex watermark, curved edges with flowing dots, nodes ringed by classification color, green status dot = has swaps. Timeline histogram docked at bottom. |

## 6. Voice

- Name things by what the analyst recognizes: *Net flow*, *Bundle*, *Funding cluster*, *Sniped +2 blocks*.
- Estimated money is always marked **est.**; verified PnL is always marked **verified**.
- Empty states say what to change: "No swaps in this window. Try 30D or All."
