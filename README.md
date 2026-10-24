# Statement Visualizer

[![CI](https://github.com/Nine14282/Bank-Statement-Visualizer/actions/workflows/ci.yml/badge.svg)](https://github.com/Nine14282/Bank-Statement-Visualizer/actions/workflows/ci.yml)

Turns your **Krungthai (KTB) and Kasikorn (KBank) statement PDFs** into one ledger and a dashboard: income vs
expense, balance over time, categories, monthly spend rate, a searchable transaction table, and a warning when a
statement month looks missing. Transfers between your two accounts are marked "Own transfer" and left out of income
and spending.

Everything runs on your computer. Nothing is uploaded. The only network use is the install and the optional,
read-only Gmail download.

> **Status:** tested on Linux. macOS and Windows are written for but not yet tested on a real machine: expect rough
> edges, and please report them.

## Install

Pick your system, copy the one command, paste it, press Enter. It takes about a minute and opens nothing yet.

### Windows 10 / 11

In **PowerShell** (Start Menu → type *PowerShell*):

```powershell
iwr https://github.com/Nine14282/Bank-Statement-Visualizer/releases/latest/download/StatementVisualizer-Setup.exe -OutFile "$env:TEMP\StatementVisualizer-Setup.exe"; & "$env:TEMP\StatementVisualizer-Setup.exe"
```

Or [download `StatementVisualizer-Setup.exe`](https://github.com/Nine14282/Bank-Statement-Visualizer/releases/latest/download/StatementVisualizer-Setup.exe)
and double-click it.

- No Python, no admin. It installs for your account into `%LOCALAPPDATA%\Programs\Statement Visualizer`.
- *Windows protected your PC*? Click **More info → Run anyway** (releases aren't code-signed yet). To check the file,
  compare `Get-FileHash StatementVisualizer-Setup.exe` with the release's `SHA256SUMS.txt`.
- The app window uses Microsoft WebView2: part of Windows 11, and Setup adds it on Windows 10.

**Open it:** Start Menu → **Statement Visualizer**.

### Linux (Debian / Ubuntu)

```bash
sudo apt install -y git python3 python3-venv libxcb-cursor0 && git clone https://github.com/Nine14282/Bank-Statement-Visualizer.git && cd Bank-Statement-Visualizer && ./install.sh
```

- Other distros: install git and Python 3.10+, then run the part from `git clone` on.
- Answer **Y** to *Add Statement Visualizer to your app menu?*
- The app window downloads Qt (~200 MB). To skip it and use your browser instead, end with `./install.sh --web`.

**Open it:** app menu → **Statement Visualizer**.

### macOS

```bash
git clone https://github.com/Nine14282/Bank-Statement-Visualizer.git && cd Bank-Statement-Visualizer && ./install.sh
```

- Needs Python 3.10+. A fresh Mac's own Python is often 3.9: run `brew install python` first.

**Open it:** double-click `Statement Visualizer.command` in the `Bank-Statement-Visualizer` folder.

## First run

The app opens a short setup (about 2 minutes):

1. **Statements**: drop in your statement PDFs. The bank is detected for you.
2. **Passwords**: bank PDFs are locked, one password per bank. Tick *Remember* to save it on this computer.
3. **Spending** (what you spend each day or month; optional).
4. **Gmail** (optional, [below](#gmail-optional)), then **Build my dashboard**.

## Everyday use

- **Add statements** (top bar): drop the new PDFs, press **Update**. Duplicates are dropped, so overlapping statements
  are fine.
- **Settings** (the gear): statements (remove any you don't want), expected spending, passwords, Gmail, **Open data
  folder**, **Delete all my data**. Gmail keys and the data folder stay hidden until you press **Show** and confirm.
- **Theme**: the sun / moon button in the top bar. Light is the default.
- **Export CSV** (top bar) saves the ledger for Excel.
- Opening the app while it is open brings its window to the front.
- No app window possible here (or installed with `--web`)? The same app opens in your browser. Nothing to keep open:
  it stops a few minutes after you close the tab.

## Gmail (optional)

The app can download your statements from Gmail, **read-only**: **Fetch from Gmail** on Add statements, and by itself
each time the app opens. It only reads the banks' own emails (fixed senders, so nobody can mail a fake statement in):

| Email | From | Becomes |
|---|---|---|
| Krungthai statement ("ส่งรายการเดินบัญชีเงินฝาก") | `noreply@krungthai.com` | PDF in `Statement/` |
| KBank statement ("E-statement for saving account") | `K-ElectronicDocument@kasikornbank.com` | PDF in `Statement/` |
| Krungthai NEXT payment (`แจ้งผลการ…`) | `noreply@krungthai.com` | a ledger row until the statement arrives |
| K PLUS payment ("Result of … (Success)") | `KPLUS@kasikornbank.com` | a ledger row until the statement arrives |

Payment emails are outgoing only and have no balance. When the statement arrives, its matching row (same amount within
4 hours, 6 after the bank's nightly cut-off) replaces the email row. Emails older than your first statement are kept
aside until you add that statement.

**One-time setup (about 5 minutes)** at <https://console.cloud.google.com/>:

1. Create a project. **APIs & Services → Library**: enable **Gmail API**.
2. **OAuth consent screen**: *External*, and add your own Gmail as a **test user**.
3. **Credentials → Create credentials → OAuth client ID → Desktop app**.
4. In the app: **Settings → last step**, paste the client ID and secret, **Save Gmail settings**.
5. Press **Fetch from Gmail** and approve read-only access in the browser (once).

Good to know:

- In *Testing* mode Google signs you out after **7 days**: press **Fetch from Gmail** to sign in again. Switching the
  consent screen to *In production* avoids that (Google then shows an "unverified app" warning you can click through).
- Downloads with nobody there need saved passwords: tick *Remember* for each bank.
- Work or university Google accounts may block this. Use a personal Gmail.

### Real time (optional)

New mail arrives in the open app within seconds, through Google Cloud Pub/Sub (free at this volume). On top of the
setup above:

1. **APIs & Services → Library**: enable **Cloud Pub/Sub API** (Google may ask for a billing account; usage stays free).
2. **Pub/Sub → Topics → Create topic** (e.g. `gmail-push`), without a default subscription.
3. Topic → **Permissions → Add principal** `gmail-api-push@system.gserviceaccount.com`, role **Pub/Sub Publisher**.
4. **Pub/Sub → Subscriptions → Create**: that topic, **Pull**, retention **1 day**.
5. **Google Auth Platform → Data Access → Add scope** `https://www.googleapis.com/auth/pubsub`.
6. In the app: **Settings → last step → Real time**: project ID, topic, subscription, then save.
7. Press **Fetch from Gmail** and sign in again (the login now includes Pub/Sub).

The listener then runs while the app window is open (log: `workspace/.app/gmail-listen.log`). It only searches the
last 7 days; older mail comes with the next **Fetch from Gmail**.

**Cost:** Pub/Sub bills by data moved; the first 10 GiB a month are free and ten emails a day is well under 100 MB.
Keep the 1-day retention, and add a $1 budget alert (**Billing → Budgets & alerts**) to be sure.

**Listening with the app closed (Linux):** save as `~/.config/systemd/user/statement-gmail.service` (your folder's real
path), then `systemctl --user enable --now statement-gmail`:

```ini
[Unit]
Description=Statement Visualizer Gmail listener

[Service]
ExecStart=/path/to/Bank-Statement-Visualizer/gmail.sh --listen
Environment=PYTHONUNBUFFERED=1
Restart=always
RestartSec=60

[Install]
WantedBy=default.target
```

While it runs, the app's own listener steps aside (reopen the window to see new rows). With real time on,
`workspace/token.json` also grants Pub/Sub access: keep it private.

## Update

- **Windows:** run a newer `StatementVisualizer-Setup.exe` (the same command as Install). Your data stays.
- **Linux / macOS:** in the project folder, `git pull`, then open the app (it updates its packages by itself).

The first run after an update may read every PDF once more.

## Start over or uninstall

- **Start over** (keep the app, delete your data): Settings → **Delete all my data** (type DELETE).
- **Windows:** Settings → Apps → Statement Visualizer → **Uninstall**. It asks whether to delete your data too.
- **Linux / macOS:** in the project folder:

  ```bash
  ./uninstall.sh          # removes the app, keeps your PDFs, ledger and settings
  ./uninstall.sh --all    # also deletes the whole folder, data included (asks you to type its name)
  ```

Also, if you used them: remove the Gmail access at <https://myaccount.google.com/permissions>, stop the service with
`systemctl --user disable --now statement-gmail`, and clear the dashboard's site data in any browser you opened
`Dashboard.html` in.

## Personal settings

Optional, in the settings file `.env` in the project folder (on Windows, in the program's folder). Blank means off; changes apply at the
next update.

| Setting | Effect |
|---|---|
| `ACCOUNT_HOLDER`, `ACCOUNT_LABEL` | your name: the avatar's initials and the greeting; the label goes in the avatar's tooltip |
| `THEME` | default theme, `daylight` (the default when blank) or `midnight` |
| `LEDGER_CASH_REF` | the account number of your own cash channel → "Cash withdrawal / Cash deposit" |
| `LEDGER_PEER_REF` | someone you lend to → "Lent out / Loan repaid to me" |
| `LEDGER_STOCK_REF` | your investment account → "Stock investment / Stock return" |
| `KTB_PW`, `KBANK_PW` | the PDF passwords (what *Remember* saves) |

Spending with no bank record: `workspace/manual_entries.csv`, header `Date,Description,Category,Amount,Balance`, rows
like `2026-01-31 14:05,Lunch,Food,-120,` (Balance blank, spending negative).

## Terminal commands (optional)

You never need these to use the app.

| Linux / macOS | Windows (in the program's folder) | What it does |
|---|---|---|
| `./run.sh` | `.\StatementVisualizer.exe run` | opens the app (installs first on a fresh clone) |
| `./run.sh --web` | `… run --web` | the app in your browser instead of its window |
| `./run.sh --setup` | `… run --setup` | only the full setup, in your browser |
| `./run.sh --rebuild` | `… run --rebuild` | rebuild from `Statement/` in the terminal (asks for passwords there) |
| `./gmail.sh` | `… gmail` | fetch from Gmail, then rebuild (`--listen`: real time, `--no-build`: download only) |
| `./clear.sh` | `… clear` | delete all your data (same as Delete all my data) |
| `./install.sh [--web]` | | install or repair; safe to re-run, keeps your data |
| `./uninstall.sh [--all] [-n]` | `… uninstall` | uninstall (`-n`: only list) |

`./run.sh --password=...` rebuilds with that password, but it stays in your shell history.

## Where things are

```
Statement/                    your PDFs
workspace/ledger.csv          the merged ledger
workspace/manual_entries.csv  hand-typed spends + Gmail payment rows
workspace/expected.json       expected spending
workspace/token.json          Gmail login (secret)
workspace/.cache/             statements already read
workspace/.app/               the app window's labels, theme, size, Gmail log
.env                          your settings and saved passwords (secret)
Dashboard.html                the last dashboard, for any browser
web/dist/index.html           the dashboard itself (holds your transactions)
```

All of these are private to your user account and git-ignored. The dashboard holds all your transactions: share it
only on purpose.

## Troubleshooting

- **`python3 -m venv` fails, mentions `ensurepip`** (Debian/Ubuntu) → `sudo apt install python3-venv`, then
  `./install.sh` again.
- **Permission denied** on `./install.sh` (zip download) → `chmod +x *.sh`, then again.
- **Install failed halfway** (no internet) → run `./install.sh` again; opening the app also retries.
- **Opens in the browser, not its own window** (Linux) → on X11 `sudo apt install libxcb-cursor0`, else
  `./install.sh` again. `.venv/bin/python workspace/app.py` prints the reason.
- **The browser tab didn't open** → open the `http://127.0.0.1:47613/?setup=…` link the terminal printed (once per
  link; opening the app again makes a new one).
- **Can't update `ledger.csv`** (Windows) → close it in Excel first.
- **"Data may be missing"** → a statement for that period isn't added yet (or balances don't join up). Add it.
- **Wrong password** → you're asked again; unattended runs stop without touching the ledger.
- **A PDF isn't read / amounts look wrong** → only Krungthai and KBank layouts are supported. Every row is imported; a
  row that disagrees with the statement's totals prints `CHECK <file>: …`. Send that line when reporting it.
- **"Missing web/prebuilt/index.html"** → `git checkout web/prebuilt`.

## Security

- Statements are parsed locally; nothing from them is uploaded. Gmail access is read-only and talks only to Google.
- `.env`, `token.json`, your PDFs, the ledger and the dashboard are readable by you only.
- In the app window, Add statements and Settings talk to the app directly; no server runs. The browser fallback
  runs a small server on 127.0.0.1 (this computer only, port 47613): its printed link works once and becomes a
  private cookie, and it stops a few minutes after its tab is closed.
- Passwords stay in memory unless you tick *Remember* (then they are saved, as plain text, in `.env`).

## Adding a bank

One module per bank in `workspace/banks/` (copy `ktb.py` or `kbank.py`): its parser and a `BANK = Bank(...)` record
(id, name, password setting, file-name pattern, page-1 text). Add it to `BANKS` in `workspace/banks/__init__.py`, its
tests as `tests/test_<bank>.py`, and its name, card colour and logo in `web/src/lib/banks.ts`. A theme: one entry in
`web/src/lib/themes.ts`, plus an optional `[data-theme="…"]` block in `web/src/index.css`.

## Developing

End users install with plain pip (`./install.sh`, `requirements.txt`). Developers use
[uv](https://docs.astral.sh/uv/), ruff, pytest and pre-commit, all configured in `pyproject.toml`:

```bash
uv sync --extra app                  # dev tools + the app's packages (plain `uv sync` removes PyQt6/pywebview)
uv run pytest                        # tests use a temporary data folder, never your data
uv run ruff check                    # lint (--fix to apply)
uv run ruff format workspace tests   # format
uv run pre-commit install            # once: the checks run before each commit
uv run pre-commit run --all-files    # what CI runs
```

`requirements.txt` and `requirements-app.txt` are generated from `uv.lock` (the pre-commit hooks do it). After editing
dependencies: `uv lock`, then

```bash
uv export --frozen --no-dev --no-emit-project --quiet --output-file=requirements.txt
uv export --frozen --no-dev --no-emit-project --quiet --extra=app --output-file=requirements-app.txt
```

Keep the ruff version in `pyproject.toml` equal to the `ruff-pre-commit` rev. CI
([`ci.yml`](.github/workflows/ci.yml)) runs pre-commit, pytest on Ubuntu and Windows (Python 3.10 and 3.12), and the
web lint, tests, build and a check that `web/prebuilt/index.html` is current. Reformatting `extract_ledger.py` or
`banks/*.py` makes the next update re-read every PDF.

### The dashboard (`web/`)

Node.js 22.12+, only if you edit `web/src/`:

```bash
cd web && npm install
npm run dev      # live preview with your data (from the last build)
npm run build    # rebuilds web/prebuilt/index.html (no data in it): commit it with your change
npm test         # Vitest (the ledger maths); `npx vitest run` runs once
npm run lint     # oxlint: 3 known warnings in generated components/ui files
```

### The Windows program

Built on Windows with PyInstaller and [Inno Setup 6](https://jrsoftware.org/isinfo.php):

```bat
set UV_PROJECT_ENVIRONMENT=build-venv
uv sync --locked --no-dev --group build
uv run --no-sync pyinstaller --clean --noconfirm statement-visualizer.spec
"%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" statement-visualizer.iss
```

That makes `dist\StatementVisualizer\` (don't run it inside `dist\`: it keeps its data next to itself) and
`dist\StatementVisualizer-Setup.exe`. From source without building: `py workspace\launcher.py run`.
A portable `StatementVisualizer-windows.zip` is on each release: extract it into a folder of its own (not Desktop,
Downloads, Documents or `Program Files`) and run the `.exe` there.

**Releasing:** pushing a `v*` tag (e.g. `v1.0.0`) builds, smoke-tests (`StatementVisualizer.exe --smoke`), installs and
uninstalls silently, then publishes Setup, the zip and `SHA256SUMS.txt`
([`windows-build.yml`](.github/workflows/windows-build.yml)). Optional:

- **Code signing** (free for open source): join the [SignPath Foundation](https://signpath.org/), set up the
  configurations in `.signpath/artifact-configurations/` and a `release-signing` policy, then add the variables
  `SIGNPATH_ORGANIZATION_ID`, `SIGNPATH_PROJECT_SLUG` and the secret `SIGNPATH_API_TOKEN`.
- **VirusTotal**: the secret `VT_API_KEY` scans each release and links the results in its notes.
- **False positive**: report it at [Microsoft's submission page](https://www.microsoft.com/wdsi/filesubmission).
- **Clean test machine**: put Setup (and test PDFs) in `%USERPROFILE%\StatementVisualizer-test` and double-click
  `windows-sandbox.wsb` (Windows Sandbox, Pro editions).
