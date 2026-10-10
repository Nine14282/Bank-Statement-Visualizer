# DESIGN.md

UI/UX reference for the Statement Visualizer dashboard (`web/`). Everything here comes from `web/src`. If the code
changes, update this file to match. Read it before you add or restyle a screen.

## Style

- **Feel:** a calm personal-banking app. The default is dark ("Midnight": near-black with a faint magenta tint),
  with one violet accent and soft glows. Big geometric figures, small mono labels, rounded pills everywhere.
- **Colour goes to money.** Violet/coral mark income/expense data, green/red mark good/bad. Decoration stays
  neutral: payee avatars are `bg-muted`, and icons are `text-muted-foreground`.
- **Reference images:** copy their layout, scale, spacing and type treatment, but **never their colours**. Build every
  screen from theme tokens.
- **One page, many sections.** The dashboard scrolls through `SECTIONS` (`lib/nav.ts`: overview, categories,
  spend-rate, predict, transactions). Each is an element with an `id` and `scroll-mt-20`, and a scroll-spy lights
  the nav. Top-level pages (Dashboard / Expected Spending / Custom) are tabs kept in the URL hash (`#plan`,
  `#custom`).
- **Explain every number.** Put an `InfoTip` ("?") beside any metric that isn't obvious, and a one-sentence
  plain-English summary above each chart ("You spend ฿X a month on average…"). Offer a table view as the alternative
  to a chart.
- **Copy voice:** plain English, second person, sentence case. Money is `฿1,234.56` via `baht()`, which drops the
  sign. Signed amounts use `signed()`, which writes `+` or a real minus `−` (U+2212). Dates are ISO `yyyy-mm-dd`, and
  a missing value is `—`.
- **Empty and error states are designed.** Use `EmptyState` (`App.tsx`) when there is no data, a dashed box with a
  CTA when a feature isn't set up (`MonthSpend`), a `ring-neg` card for data gaps (`Coverage`), and
  `border-neg/40 bg-neg/10 text-neg` for alerts.

### Layout

- `main`: `max-w-[90rem] px-4 sm:px-6 md:pl-24 lg:pr-8 space-y-10`. `md:pl-24` clears the floating nav rail, and
  `pb-28` clears the phone bottom bar.
- Card rows are CSS grids with explicit tracks, such as `lg:grid-cols-[minmax(0,27rem)_minmax(0,1fr)]` and
  `[minmax(0,1.3fr)_minmax(0,1fr)]`, with `items-stretch` + `[&>*]:h-full` so cards in a row match height. Put
  `min-w-0` on grid children that hold charts or truncated text.
- Breakpoints:

  | Breakpoint | What changes |
  |---|---|
  | `md` (768px) | Side nav rail, otherwise the bottom bar |
  | `lg` (1024px) | Two-column rows; `TxTable` shows the table, otherwise cards |
  | `xl` | Three-column categories |

- Touch targets are 44px: `size-11`, `pointer-coarse:min-h-11`, or an enlarged hit area (`after:-inset-2.5`) on
  small icons.
- The setup wizard is one screen per step and the page itself never scrolls (`h-dvh`). Long content scrolls inside
  the step's `Frame` card. Later `./run.sh` runs open the same wizard in add mode (`/?setup&add`): Statements →
  Passwords → Finish only, listing just the new files.

### Motion

The library is Motion (`motion/react`), wrapped in `<MotionConfig reducedMotion="user">` (`main.tsx`).

- **Easing:** `EASE = [0.16, 1, 0.3, 1]` (`lib/utils.ts`), a fast start with a long settle. Use it for every tween.
- **Entrances:** `Reveal` (`components/ledger/motion.tsx`) fades and lifts content 18px over 0.45s the first time it
  scrolls into view. Use `now` for above-the-fold content. Stagger siblings with `delay` 0.06–0.18.
- **Figures:** headline numbers count up with `CountUp` (1.1s). Its `format` must be a module-level function.
- **Selection:** a lit pill slides between options via a shared `layoutId` on a spring (stiffness 380–420, damping
  30–32). Used in Nav, page tabs, `Segmented`, wizard steps and the payee ring.
- **Swaps:** use `AnimatePresence mode="wait"`. Chart views use a 0.15s fade; wizard steps slide x ±24px over 0.25s.
- **Micro-interactions:** `hover:-translate-y-0.5` on round links, `active:scale-95` on buttons, and brighten on hover
  (`hover:brightness-110`).
- **CSS keyframes** (in `index.css`): `.tick` (segmented bar fill), `.tx-new` (new-row highlight), `.hero-glow`
  (18s drift).
- **Reduced motion:** every CSS animation has a `prefers-reduced-motion` off-switch, and every chart has
  `isAnimationActive={!still}`. Animate transforms and opacity only.
- **Desktop app window:** no animation. `workspace/app.py` opens the page with `?app` (`main.tsx` then sets
  `MotionGlobalConfig.skipAnimations`) and asks WebKitGTK for reduced motion (CSS keyframes and charts). WebKitGTK
  stutters on the entrances; the browser keeps everything. Hover colour transitions stay. Add statements opens the add
  page over the dashboard in the same page (`App.tsx`, no page load, no transition); Dashboard closes it the same way.
  Settings (gear, top bar) opens the full setup the same way, minus its Welcome screen. With no data yet the window
  shows the full setup itself (the browser shows the No data yet page instead).
  Exceptions, all around an update:
  - **Loader** (`wizard.tsx`): ring filling per statement read, stage icon, one- or two-word label (Starting, Reading
    statements, Merging, Building dashboard, Done).
  - **Finale** (`wizard.tsx`, Web Animations API): on Done the add page's content fades to its bare background (400ms)
    and the page reloads with `?app&updated`.
  - **Entrance** (`ARRIVE`, `lib/utils.ts`): that load plays the full entrance for `ARRIVE_MS` (3s from when the dashboard mounts): Motion on with
    reduced motion ignored (`main.tsx`), charts and count-ups via `useStill()` (`lib/utils.ts`), CSS
    via `.arriving` (`.tick`, and `appear` on the top bar and nav rail). Then the window is still again.

## Color

Tokens live in `web/src/index.css`. Use them as Tailwind classes (`bg-card`, `text-muted-foreground`, `bg-brand`,
`text-pos`, `bg-expense/15`) or as `var(--token)` in `style`/`sx`/SVG. All colours are OKLCH. The light values sit on
`:root, .light`, the dark values on `.dark`.

| Token | Role | Midnight (dark) | Daylight (light) |
|---|---|---|---|
| `--background` | page | `oklch(0.14 0.006 320)` | `oklch(0.962 0.006 285)` |
| `--card` | card surface | `oklch(0.185 0.007 320)` | `oklch(1 0 0)` |
| `--popover` | menus, tooltips | `oklch(0.2 0.008 320)` | `oklch(1 0 0)` |
| `--muted` | inner panels, tracks, hover | `oklch(0.22 0.007 320)` | `oklch(0.95 0.006 285)` |
| `--foreground` | text | `oklch(0.94 0.004 320)` | `oklch(0.17 0.01 285)` |
| `--muted-foreground` | secondary text, labels | `oklch(0.7 0.01 320)` | `oklch(0.52 0.012 285)` |
| `--border` | hairlines | `oklch(1 0 0 / 9%)` | `oklch(0.91 0.006 285)` |
| `--brand` | **interactive accent**: selected pill, primary button, nav, avatar | `oklch(0.5 0.22 295)` | `oklch(0.5 0.24 295)` |
| `--income` | income series/data (violet) | `oklch(0.64 0.24 295)` | `oklch(0.5 0.24 295)` |
| `--expense` | expense series/data (coral) | `oklch(0.73 0.17 40)` | `oklch(0.65 0.19 40)` |
| `--pos` | positive amount, good status (green) | `oklch(0.76 0.16 155)` | `oklch(0.46 0.14 150)` |
| `--neg` | negative amount, bad status, warnings (red) | `oklch(0.72 0.16 25)` | `oklch(0.55 0.2 27)` |
| `--ring` | focus ring | `oklch(0.6 0.2 295)` | `oklch(0.708 0 0)` |

### Rules

- `--brand` and `--income` are the same violet family but **separate jobs**. Controls use `brand`; data uses
  `income`. Don't put `income` on a button or `brand` on a chart series.
- `--brand` is dark enough for **white text** (at least 4.5:1) in both themes. Brand buttons and pills use
  `text-white`, not a foreground token.
- `--primary` is neutral ink (near-black in light, near-white in dark), as in shadcn. So shadcn `<Button>` (default
  variant) is **not** violet. A violet button needs `bg-brand text-white`.
- **Signed amounts:** `text-pos` / `text-neg`.
- **Status pills:** `bg-pos/15 text-pos` / `bg-neg/15 text-neg`.
- **Direction bubbles:** `bg-income/15 text-income` / `bg-expense/15 text-expense`.
- **Ratios:** `Index` turns red above 1.15× and green below 0.85×.
- **Hex is allowed in three places only:**
  - bank card skins and badges in `lib/banks.ts` (gradients deep enough for white text);
  - MUI palette seeds in `lib/mui-theme.ts`, which feed only MUI internals;
  - `#fff` text on brand.
- When a bank has no entry in `lib/banks.ts`, it falls back to `SKINS` (OKLCH gradients in `widgets.tsx`).
- **Glows:** `.glow` blobs (`bg-brand`, `bg-expense`, blur 80px, opacity 0.16–0.22) sit behind the dashboard
  greeting and the wizard. `.hero-glow` is the moving radial version on the setup welcome screen.
- **Emphasis:** the two lead cards get the `HERO` treatment (`ring-2 ring-brand/20 shadow-[0_28px_64px_-30px_var(--brand)]`,
  in `widgets.tsx`). Brand buttons get a brand-tinted drop shadow (`shadow-[0_8px_20px_-8px_var(--brand)]`).
- **Themes** come from a registry: `THEMES` in `lib/themes.ts` (id, label, `light`/`dark` base, note). The `<html>`
  element gets `data-theme="<id>"`, and MUI's colour scheme sets the `.dark`/`.light` class.
  - To add a theme: add one entry to `THEMES`, plus an optional `[data-theme="<id>"]` block in `index.css` that
    overrides tokens.
  - The wizard's theme picker draws a mini dashboard with each theme's own tokens, so a new theme previews itself.
  - Both shipped themes must keep working. Dark is the default.

## Font

All fonts are local files loaded via `@font-face` in `index.css` (Geist and Geist Mono from `src/assets/fonts/`, Outfit
from `@fontsource-variable/outfit`), so they are inlined into the offline
single file. **No CDN or Google Fonts links**: the page must open offline from `file://`.

| Family | Token / helper | Used for |
|---|---|---|
| **Geist** (variable) | `--font-sans`, `font-sans` | body, UI text, MUI typography |
| **Geist Mono** (variable) | `--font-mono`, `.num`, `.eyebrow`, `.pill` | every number, date and count (`.num` = tabular nums); labels |
| **Outfit** (variable, latin) | `--font-display` = `--font-heading`, `.display`, `h1`, `h2`, `CardTitle` | headings and headline figures |

- **Thai:** no Thai face is bundled. Geist, Geist Mono and Outfit are latin-only, so every stack names
  `'Noto Sans Thai'` right after them, before the generic family (a generic name ends the list; leaving Thai to the
  system's fallback search slowed the first paint in WebKitGTK). Without Noto Sans Thai the system's own Thai font is used.
- `.display`: weight 400, `-0.025em`, lining + tabular nums. Use it for big money figures.
- `.eyebrow`: mono 12px / 600, uppercase, `0.1em` tracking, muted. Use it for small labels above figures, in
  tooltips and in drawers.
- Table headers: `font-mono text-[11px] font-semibold uppercase tracking-[0.08em]`. Chart ticks: mono 11px.
- Type scale in use:

  | Element | Classes |
  |---|---|
  | Welcome hero | `text-[clamp(3.25rem,13vw,9.5rem)] font-semibold leading-[0.92]` |
  | Page `h1` | `text-3xl sm:text-4xl font-normal tracking-tight` |
  | Section `h2` | `text-2xl sm:text-3xl tracking-tight` |
  | `CardTitle` | 1.125rem / 450 / `-0.015em` |
  | KPI figures | `display text-5xl sm:text-6xl` (wallet total); `text-3xl` / `text-2xl` for secondary figures |
  | Body | `text-sm` |
  | Meta | `text-xs text-muted-foreground` |

## Tech stack

| Layer | Choice |
|---|---|
| Build | Vite 8 + `vite-plugin-singlefile` → one self-contained page with no data, `web/prebuilt/index.html` (committed); `workspace/build_dashboard.py` writes the ledger into its `#ledger-data` tag → `web/dist/index.html`. Users need no Node |
| UI | React 19, TypeScript 6 |
| Styling | Tailwind v4, CSS-first (`@theme inline` in `index.css`, no `tailwind.config`), `cn()` = clsx + tailwind-merge |
| Components | shadcn/ui (CLI v4 run on demand via `npx shadcn@latest`; its CSS vendored as `src/shadcn.css`), style `base-nova` on **Base UI** (`@base-ui/react`, not Radix), base colour neutral, `class-variance-authority` |
| Extra components | MUI 9 + Emotion, for pieces shadcn lacks here (below) |
| Motion | Motion 14 (`motion/react`) |
| Charts | Recharts 3 inside shadcn `ChartContainer` (`components/ui/chart.tsx`) |
| Icons | `lucide-react` only |
| Lint / types | `oxlint`, `tsc -b` (no UI tests) |

- **CSS layering:** `main.tsx` wraps the app in `<StyledEngineProvider enableCssLayer>` and renders
  `<GlobalStyles styles="@layer properties, theme, base, mui, components, utilities;" />` first. MUI's sheet lands in
  `<head>` before Tailwind's, so the order must be declared there (an order line in `index.css` is not enough). MUI
  therefore sits below Tailwind preflight and utilities, and a class beats MUI's own style without `!important`. Keep
  hand-written helper classes (`.num`, `.display`, `.eyebrow`, `.pill`) inside `@layer components`: unlayered CSS beats
  every utility.
- **Dark class:** MUI uses `colorSchemeSelector: 'class'`, so it owns the `.dark`/`.light` class on `<html>`. `ThemeProvider` has `noSsr storageManager={null}`: the class is set on the first render and `ledger-theme` (`themes.ts`) is the only saved theme (no `mui-mode` copy). Tailwind
  reads it via `@custom-variant dark (&:is(.dark *))`. The theme is applied before first paint in `main.tsx`.
- **Styling MUI:** use `sx`/`slotProps` with CSS vars (`bgcolor: 'var(--card)'`, `border: '1px solid var(--border)'`).
  Don't use MUI palette colours for surfaces.
- **Hot reload of the built file:** each build writes `dist/version.js`, and the open page polls it every 10s and
  reloads.
- **shadcn CLI:** after `npx shadcn add`, check the imports. It once emitted `from "cn"`; rewrite those to
  `@/lib/utils`.

## Components

`components/ui/*` is shadcn-generated, but `card.tsx` is customised. App components live in
`components/ledger/*`, and the setup wizard in `components/setup/wizard.tsx`. Keep `data-od-id="…"` on main regions
(they are OpenDesign region tags) and add one to any new main region.

### Shell

- **`TopBar`** (`shell.tsx`) is sticky, `bg-background/80 backdrop-blur-md`. It holds:
  - the ฿ mark (a round `bg-foreground text-background` badge);
  - page `Tabs`, a pill with a sliding brand background;
  - Add statements, the one brand pill (icon only below `sm`). It opens a `Popover` with the `./run.sh` command
    (with the project folder worked out from the page's `file://` address) and a copy button, because a page
    opened from disk can't take PDFs itself;
  - Export CSV, an outline pill;
  - a coverage bell (MUI `IconButton` + `Badge` dot + `Popover`, radius 18px);
  - a theme toggle that steps through `THEMES`;
  - an initials `Avatar` on `var(--brand)`.

  Icon buttons are 44px circles: `bg-card`, `border`, muted icon.
- **`Nav`** is a floating rounded-full rail at the left edge on `md`+ and a bottom bar on phones. It uses 44px round
  buttons, a sliding `bg-brand` pill and an MUI Tooltip for each label.

### Surfaces

- **`Card`:** `rounded-3xl bg-card ring-1 ring-foreground/[0.06]`, a soft two-layer shadow that deepens on hover, and
  20px padding (`--card-spacing`). Inside it, use `CardHeader` / `CardTitle` / `CardDescription` / `CardAction`
  (top-right control slot) and `CardContent`.
- **Inner panels:** `rounded-2xl bg-muted/60 px-4 py-3`.
- **Lists:** `divide-y`, often inside `rounded-2xl border`.
- **Setup CTA (feature not set up):** `rounded-2xl border border-dashed p-4`.
- **`WalletStack`:** bank cards stacked like a wallet that fan out on hover, over a total cut with a circular notch
  (CSS `mask`).

### Buttons and choices

- **Primary:** `rounded-full bg-brand px-4 py-2 text-sm font-medium text-white shadow-[0_8px_20px_-8px_var(--brand)]
  transition hover:brightness-110 active:scale-95 disabled:opacity-40 disabled:shadow-none`. `wizard.tsx` keeps it
  (and `ghost`) as class constants; elsewhere the string is inlined.
- **Secondary / ghost:** `rounded-full border px-4 py-2 text-sm transition hover:bg-muted active:scale-95`.
- **`RoundLink`** (`widgets.tsx`): a `size-10` round icon link that jumps to a section.
- **shadcn `Button`:** only for small utility actions (presets, the sort-direction icon, ghost "View …" links).
- **`Segmented`** (`widgets.tsx`): a `role="radiogroup"` pill with a sliding brand fill. Use it for main view and
  range switches (year filter, chart view, 7d/30d/90d). Each instance needs its own `id`, which becomes its
  `layoutId`.
- **shadcn `ToggleGroup` (`variant="outline"`):** use it for secondary sort and filter in dense card headers
  (category sort, transaction in/out filter).

### Data display

- **Figures:** `.display` + `CountUp` for headline numbers. Everything numeric gets `.num`.
- **Explanations:** `InfoTip` (`info.tsx`), an MUI Tooltip that opens on tap (`enterTouchDelay={0}`), on a "?" icon
  button.
- **Labels and badges:** outline `Badge` for categories; `.pill` for step numbers and tags; a `late-night` chip as a
  small `rounded-full border` span.
- **Progress:**
  - the tick bar in `MonthSpend`: 48 rounded ticks, today's tick outlined;
  - thin category bars (`h-1`, `scaleX`, fading opacity down the list);
  - MUI `LinearProgress` (4px, `sx` colours from tokens).
- **Tables:** shadcn `Table` in a `rounded-lg border` wrapper, mono-caps headers, right-aligned `.num` cells.
  `TxTable` mounts **either** the table (`lg`+) **or** the card list (`useSyncExternalStore` + `matchMedia`), never
  both, at 15 rows per page with MUI `Pagination` (rounded-full, brand selected item).
- **`BankLogo`:** a round logo badge with an initials fallback. Bank name, skin and logo come from `lib/banks.ts`.
- **`PayeeAvatar`:** an MUI Avatar in neutral `--muted`, with initials or a category icon.

### Charts

These live in `charts.tsx`.

- Wrap every chart in `ChartContainer`, with `ChartConfig` colours set to tokens (`var(--income)`,
  `var(--expense)`).
- Axes: no axis lines or tick lines. Use `CartesianGrid vertical={false} strokeDasharray="3 6"` and mono 11px ticks.
  Axis money is compact (`฿5.5k`).
- Series differ by more than colour: income is solid, expense dashed (`7 5`), each with a gradient fill from 0.28 to 0.
  The active dot is ringed in `var(--card)`.
- Tooltips are custom, using the `tipBox` style: `rounded-2xl border bg-popover/95 backdrop-blur shadow-xl`, with an
  `.eyebrow` title.
- Every chart gets `role="img"` and an `aria-label` that sums up the data.
- `DailyBars`: muted bars (24% `--expense`). The hovered bar, or else the peak, gets a gradient and a date pill that
  stays inside the card.

### Overlays and feedback

- **MUI `Drawer`** (right, `min(420px, 100vw)`): transaction details and the label editor.
- **MUI `Snackbar`:** toasts.
- **MUI `Tooltip`:** labels for icon-only controls.

### Installed shadcn components

Only the ones in use are kept: `badge`, `button`, `card`, `chart`, `input`, `table`, `toggle-group` (+ `toggle`,
which it imports). Tooltips are MUI's. The nav and page tabs are custom, so don't add shadcn `Sidebar` / `Tabs`. Before
adding any other shadcn component, check that `index.css` still has the tokens it uses: the `sidebar-*` and
`chart-1`…`chart-5` tokens were removed.

### Accessibility basics already in place (keep them)

- skip link;
- one global `:focus-visible` ring (`--ring`);
- `cursor: pointer` on every clickable role;
- ARIA roles on custom controls (`radiogroup`/`radio` + `aria-checked`, `tablist`/`tab`, `aria-current`);
- `aria-label` on icon buttons;
- text alternatives for charts;
- reduced-motion support;
- 4.5:1 contrast for white text on `--brand` and on bank skins.

## Skills

These are optional Claude Code skills from the maintainer's setup; they are not part of this repo. Whatever a
skill suggests, **this file's tokens and fonts win**. Ignore palettes or font pairings that skills propose.

| Skill | Use it for | Watch out |
|---|---|---|
| `ui-ux-pro-max` | planning, building or reviewing a screen or component (supports React + shadcn + Tailwind) | keep the existing palette and fonts |
| `ui-styling` | shadcn + Tailwind patterns, dark mode, accessible components | this repo is shadcn on **Base UI**, not Radix |
| `design-system` | token work (new theme, new semantic colour) | tokens go in `index.css` + `lib/themes.ts`, nowhere else |
| `design-review` | visual audit before a release | skip its commit step; the maintainer commits by hand |
| `design-md` | keeping this file in sync | |
| `review-ui-with-kombai` / `improve-ui-with-kombai` | a second opinion or a polish pass in Kombai | same palette rule |
| `detect-design-system-with-kombai` | saving this system to Kombai (`web/.kombai/design-systems/` is empty) | |
| `dashboard` | throwaway single-HTML mockups only | not for code in `web/` |

**Visual checks:** use `cd web && npm run dev` (it shows your data; `npm run preview` serves the prebuilt page, which
has none, so it shows the empty state) and the claude-in-chrome
tools. The test tabs share the real browser profile, so save and restore these localStorage keys rather than
deleting them: `ledger-label-rules`, `ledger-expected-spending`, `ledger-theme`, `ledger-seen-rows`, `mui-mode`.
Check both themes and a phone width.

## Known gaps

- No favicon: Vite's default logo (which never loaded under `file://`) was removed with `web/public/`. If one is
  added, inline it in `index.html` as a `data:` URI so it works offline. The brand mark in the UI is the ฿ circle.
