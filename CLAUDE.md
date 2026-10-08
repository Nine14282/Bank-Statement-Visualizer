# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Personal pipeline: Krungthai (KTB) bank-statement PDFs → merged `workspace/ledger.csv` → the dashboard `web/dist/index.html` (React app built to one self-contained file; opens offline, nothing uploaded). Pipeline is plain Python scripts (no tests, no linter); `web/` is a Vite app with `tsc` + `oxlint` only (no tests). Statement text is Thai; dates in PDFs are Buddhist-era `DD/MM/YY`.

## Commands

Run from anywhere (scripts anchor paths to their own folder). Use the project venv: `.venv/bin/python`.

```bash
./setup.sh                                         # once: venv + requirements.txt + web npm install + settings file from the template
./run.sh                                           # use case 1 (manual): Statement/*.pdf -> dashboard (password: env settings or typed)
./gmail.sh                                         # use case 2 (auto): Gmail -> Statement/ -> dashboard; cron-friendly
.venv/bin/python workspace/update_statement.py     # main entry: Statement/*.pdf -> ledger.csv -> web/dist/index.html
STATEMENT_PW=xxxx .venv/bin/python workspace/update_statement.py   # unattended (else prompts; also --password=)
.venv/bin/python workspace/fetch_gmail.py          # pull new statement PDFs from Gmail, then run update (--no-build to skip)
.venv/bin/python workspace/watch_statements.py     # poll Statement/ every 5s, rebuild on change
.venv/bin/python workspace/build_dashboard.py      # rebuild dashboard only: ledger.csv -> web/src/data/ledger.json -> npm run build
.venv/bin/python workspace/extract_ledger.py IN.pdf OUT.csv   # parse a single unlocked PDF
cd web && npm run build                            # UI-only rebuild from the existing ledger.json (tsc -b + vite build)
cd web && npm run lint                             # oxlint; ~9 warnings in generated src/components/ui/* are known
```

## Architecture

Pipeline, in order:

1. `fetch_gmail.py` — Gmail API (read-only scope), query `GMAIL_QUERY`; saves PDFs as `Statement/<msgid8>_<name>.pdf`; processed message ids tracked in `workspace/.gmail_seen.json`. OAuth: `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` (and `GOOGLE_PROJECT_ID`, optional `GMAIL_QUERY`) come from the project-root settings file via `workspace/config.py` (shared tiny loader, imported first by every script; real env vars win, blank values count as unset; no python-dotenv; all settings documented in `.env.example`); cached `token.json` in `workspace/`. `.env` and `token.json` are secrets — never print/commit (both git-excluded).
2. `extract_ledger.py` — `pdfplumber` word-position parser. Debit vs credit is decided by the amount's **x-centre** (`WD_MAX=400`, `DEP_MAX=470`), not by text; branch column is `x0 > 540`. A row starts at a date token; following lines (time, wrapped detail) attach to it. `categorize()` maps reference numbers (`REF_CASH`/`REF_PEER`/`REF_STOCK`, from `LEDGER_CASH_REF`/`LEDGER_PEER_REF`/`LEDGER_STOCK_REF` in the settings; blank = off; categories are baked into `ledger.csv` at extraction, so a missing ref only shows after the next re-extract) + money direction to categories, falling back to `TYPE_EN` (Thai type prefix → English). `build_rows` checks balance continuity per row.
3. `update_statement.py` — merges all PDFs (tries no password, then retries with password for encrypted ones), dedupes by transaction ID (`txid.py`), appends `workspace/manual_entries.csv` (hand-entered spends with no bank record; blank Balance; skipped if a statement already has the same ID), sorts, writes `ledger.csv`, then calls `build_dashboard.build()`. Two copies of one ID that disagree on balance or description are printed as `CONFLICT` (earlier copy kept). Refuses to overwrite `ledger.csv` if zero rows were read.
4. `build_dashboard.py` — prints the ledger.csv summary and `find_gaps()` warnings, writes `web/src/data/ledger.json` (`{meta: {account,name,from,to,n,gaps}, tx: [...]}`), then runs `npm run build` in `web/` (runs `npm install` first if `node_modules` is missing; needs Node). `find_gaps()` flags empty months and balance jumps (rows chained by balance within the same minute; offsetting nearby jumps are dropped as out-of-order posting); the React app only displays `meta.gaps`. Manual rows (`bal is None`) are skipped for balance chaining.

`unlock_pdf.py` is a standalone helper to strip a PDF password via `pikepdf` (not used by the pipeline).

## Gotchas

- `web/dist/index.html` is generated and holds all the data inline; never edit it. Edit `web/src/`, then rebuild.
- Personal data is gitignored (`workspace/*.csv`, `web/src/data/`, `Statement/`, `token.json`, the env secrets file; `web/dist` via `web/.gitignore`). No personal values live in code: account refs and sidebar label (`ACCOUNT_LABEL`/`ACCOUNT_HOLDER`) come from the settings file; keep it that way. Unattended runs (watcher, cron) cannot prompt: `get_password()` exits with a message unless `STATEMENT_PW` is set. README.md is the user-facing guide (two use cases); keep it in sync with the scripts. A global hook blocks Claude from touching env files.
- Ledger CSVs are `utf-8-sig`; columns `Date, Description, Category, Amount, Balance, ID`; Amount signed (income +, expense −). `manual_entries.csv` keeps the first five (ID is computed on merge).
- Transaction ID (`workspace/txid.py`, `python txid.py` is its self-check): sha256 (16 hex) of `yyyymmdd hhmm <satang>#<n>`; money out has a leading 0 (`0100` = out 1.00, `100` = in 1.00); `n` = occurrence of the same (minute, signed amount) within ONE statement. The `n` matters: real data has repeated same-minute same-amount transactions (e.g. four 30 baht deposits in one minute), which a plain date+time+amount key would silently drop. Overlapping statements number the same rows the same way, so their copies share IDs. A hash collision raises.
- Directories `Statement/`, `workspace/`, `web/` and `.venv/` are the whole project (`web/node_modules` and `web/dist` are build output); this dir lives inside a git repo rooted at `~` with a single commit and mostly untracked files.

## web/ (React dashboard)

Vite 8 + React 19 + TypeScript 6 + Tailwind v4 + shadcn/ui (style `base-nova`, Base UI primitives) + Recharts, plus a few MUI 9 pieces (Drawer, LinearProgress, Tooltip, Snackbar). `vite-plugin-singlefile` inlines everything into one offline `dist/index.html`.

- All aggregation is in `src/lib/ledger.ts` (`summarize`, `rateTable`, formatters); it imports `src/data/ledger.json`. Components live in `src/components/ledger/`, entry `src/App.tsx`. Sidebar items scroll to sections of one page (no view switching).
- Styling: `src/index.css` holds theme tokens (dark default, violet income / coral expense, green/red signed amounts) and helpers `.display` (serif figures), `.eyebrow` (mono caps), `.pill`, `.num`. Fonts: Geist, Geist Mono (`geist` pkg via `@font-face`), Source Serif 4. First line of `index.css` sets `@layer ... mui ...` so MUI sits below Tailwind utilities; MUI colour mode drives the Tailwind `.dark` class (`src/lib/mui-theme.ts`, `main.tsx`).
- `src/components/ui/*` is shadcn-generated; `@/lib/utils` is `cn` (clsx + tailwind-merge). Do not add the npm package `cn`; the shadcn CLI emitted `from "cn"` imports once and they had to be rewritten.
- `TxTable` mounts either the table or the card list by media query (rows are capped at 1500); rendering both froze the browser.
- Keep `data-od-id` tags on main regions. Dark mode is the default, light must keep working.
- Empty ledger is a supported state: `ledger.json` is git-ignored and absent on a fresh clone, so `lib/ledger.ts` loads it with `import.meta.glob` (missing = empty dataset) and `App` renders `EmptyState` when `TX` is empty. `build_dashboard.py` and `setup.sh` build that blank page without any CSV. Never import `@/data/ledger.json` directly, and keep anything that reads `TX[0]`/`META.from` inside `Dashboard`.
