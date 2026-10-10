# Statement Visualizer

Turns your **Krungthai (KTB) and Kasikorn (KBank) statement PDFs** into one merged ledger and an offline dashboard,
shown in its own app window (or any browser): income vs expense, balance over time, categories, monthly spend rate,
a searchable transaction table, and a warning if a statement month looks missing.

Everything runs on your machine. Nothing is uploaded. Apart from the one-time package install, the only network use
is the optional read-only Gmail download.

**In short:** `git clone` the project, run `./run.sh`, drop in your statement PDFs. See [Install](#install) and
[Get started](#get-started).

> Supports Krungthai's and KBank's Thai statement PDFs (the parsers read those layouts; the bank is
> detected per file). Both accounts go into one ledger; each row shows which bank it came from, and
> transfers between the two accounts are marked "Own transfer" and left out of income and spending.
> Developed and tested on Linux. macOS support is written but **untested**. Windows is not supported natively (try WSL, also untested).

## What you need

| | |
|---|---|
| **OS** | **Linux** (tested). **macOS**: written for but untested, so expect rough edges (a fresh Mac's system Python is often 3.9, so install Python 3.10+ from Homebrew or python.org first). **Windows**: not supported; WSL is untested and the app window may not open there. |
| **Python** | 3.10 or newer, with `venv`. Debian/Ubuntu: `sudo apt install python3 python3-venv`. |
| **Internet** | for the first install (pip downloads 3 packages and their dependencies) and for the optional Gmail download. Nothing else is ever sent anywhere. |
| **App window** (Linux, optional) | `sudo apt install python3-gi gir1.2-webkit2-4.1`. Already there on Ubuntu desktops. Without them everything works in your browser instead. macOS needs nothing extra. |
| **Node.js** | not needed. Only if you edit the dashboard's source (see the end). |

## Install

```bash
git clone https://github.com/Nine14282/Income-and-Expenses-Dashboard.git
cd Income-and-Expenses-Dashboard
./run.sh
```

That is the whole install. The first `./run.sh` sees that nothing is set up yet and runs `./setup.sh` for you
(about a minute, needs the internet). It:

1. checks Python 3.10+;
2. creates a private Python environment in `.venv/` and installs `requirements.txt` into it (on Linux the environment
   can also see the system's `python3-gi`, which the app window needs);
3. creates `Statement/` (put your PDFs here) and a private `.env` settings file from `.env.example` (readable by you
   only);
4. builds an empty dashboard page;
5. **Linux**: asks *Add Statement Visualizer to your app menu? [Y/n]* (the default is yes; it only writes a
   `.desktop` file under `~/.local/share/applications/`). **macOS**: writes `Statement Visualizer.command` in the
   project folder, to double-click.

Then it opens the app. Re-running `./setup.sh` is safe: it keeps your `.env` values and your data.

Downloaded the project as a zip and `./run.sh` says *Permission denied*? The zip lost the "executable" mark: run
`chmod +x *.sh` once, then `./run.sh` again (`bash run.sh` alone is not enough, the scripts call each other).

## Get started

Your first run has no data yet, so the app opens a short setup, one screen per step, **Next** to go on
(**Skip** on the optional Spending step, about 2 minutes in all):

1. **Welcome**: press **Get started**.
2. **Statements** (required): drop in one or more statement PDFs, or click to choose. They are copied into
   `Statement/`. Krungthai and KBank statements are recognised on their own (by the file name, or by the PDF's
   own text); if neither tells, you pick the bank.
3. **Passwords**: bank PDFs are usually encrypted, with a different password per bank. Enter each one and it is
   checked by opening and reading your files. Tick *Remember on this computer* to save it in `.env` (plain text, file
   readable by you only; needed for unattended runs), otherwise it is used for this run only. If no file needs a
   password, the screen just says so; press **Next**.
4. **Theme**: Midnight (dark) or Daylight (light). Switch later with the sun / moon button.
5. **Spending** (optional, "What do you spend regularly?"): what you spend every day or every month. It becomes
   the full bar of "Spent this month" (edit it later in the dashboard's Expected Spending tab).
6. **Finish** ("Last thing: statements by email"): a note about the optional Gmail download (Option 2 below), then
   **Build my dashboard**. The ledger is built and your dashboard appears.

You now have **income vs expense, balance over time, categories, a monthly spend rate and a searchable
transaction table**, plus a warning if a month of statements looks missing.

### Opening it again

- **Linux**: if you said yes to the app-menu question during install, search for **Statement Visualizer** in your
  app menu (in GNOME, right-click → *Add to Favourites* pins it to the dock). Otherwise run `./run.sh` in the project
  folder, or re-run `./setup.sh` and answer Y. Moved the project folder? Re-run `./setup.sh` to refresh the menu entry.
- **macOS** (untested): double-click `Statement Visualizer.command` in the project folder, or run `./run.sh`.
- **Any system**: double-click `Dashboard.html` in the project folder to view your last build in a browser (setup
  creates it empty; it shows your data after the first build). Keep it in the project folder: it just forwards to
  `web/dist/index.html`.

Inside the app: **Add statements** (top bar) for new PDFs, and the gear for settings (the same steps again: theme,
expected spending, passwords). No terminal needed. On Linux the window keeps its own labels, expected spending and
theme (in `workspace/.app/`), apart from any browser's; on macOS it uses the system web view's own store.

**No app window?** Without the system web view, `./run.sh` opens the same setup and add-statements pages in your
browser instead. If the tab doesn't open on its own, go to the one-time link `./run.sh` printed
(`http://127.0.0.1:…/?setup=…`) and leave that terminal open while you use the page. `./run.sh --setup` opens the full
setup in the browser again.

### Updating, resetting, removing

- **Update the project**: `git pull`, then `./run.sh`. It reinstalls the packages by itself if `requirements.txt`
  changed, and always rebuilds the dashboard page first.
- **Start over with your data**: `./clear.sh` deletes the ledger, the statement cache, `workspace/manual_entries.csv`
  (hand-typed rows are lost) and the Gmail "seen" list, then rebuilds a blank dashboard. It asks first (`-y` skips the
  question). Add `--all` to also delete the PDFs in `Statement/`. It never touches `.env` or your Gmail login.
- **Remove it**: delete the project folder (it holds the `.venv`, your PDFs, ledger and `.env`), and on Linux
  `rm ~/.local/share/applications/statement-visualizer.desktop`.

## Option 1: add statements yourself

1. In the app, press **Add statements** (top bar). (No app window: `./run.sh` opens the same page in your browser.)
   - **Statements**: drop in the new PDFs your bank sent (they are copied into `Statement/`).
   - **Passwords**: only if a file needs one you haven't saved; tick *Remember* to never be asked again.
   - **Update my dashboard**: new statements are read (ones read before come from `workspace/.cache/`) and the
     dashboard comes back with them.
2. That's it. An open dashboard tab reloads by itself after the rebuild.

Forgot the command? In a browser tab (not the app window), the dashboard's **Add statements** button shows it, with
your project folder filled in and a copy button.

No browser (a server over SSH, or you just copied files into `Statement/` by hand)? `./run.sh --rebuild`
rebuilds in the terminal (it needs at least one PDF in `Statement/` and an existing ledger, so do the first run
through the app or `./run.sh` first). Runs with nobody at the terminal (cron) do that automatically.

**PDF password** (bank PDFs are usually encrypted). KTB and KBank use different passwords:
`KTB_PW` and `KBANK_PW`. The bank of each file is read from the PDF's own text when it can be opened, else from the
file name (KBank: starts with `STM`; Krungthai: contains `Statement`, capital S; a Gmail download's leading
`<8 characters>_` is ignored); each file tries its own bank's password
first. Pick one:

| How | When |
|---|---|
| Do nothing | the page (or `./run.sh --rebuild`, typed and hidden) asks the first time a file needs it |
| Tick *Remember* on the page | saved in `.env` for you, never asked again |
| `KTB_PW=...` and `KBANK_PW=...` in `.env` | never asked again |
| `./run.sh --password=yourpassword` | one-off terminal rebuild, but it stays in shell history and shows in `ps` to other users of the machine |

Run it again whenever you get a new PDF. Duplicates are dropped automatically, so overlapping
statements are fine.

## Option 2: fetch from Gmail automatically

`./gmail.sh` finds statement emails, downloads new PDFs into `Statement/`, then builds the
dashboard. It only asks Gmail for **read-only** access and never changes your mailbox. By default it looks for
Krungthai's statement emails only: for KBank (or to restrict the sender, see below) set `GMAIL_QUERY` in `.env` to
your bank's real address, for example `from:<bank sender address> has:attachment filename:pdf`.

It also reads Krungthai NEXT "payment done" emails (from `noreply@krungthai.com`, containing `แจ้งผลการ…`: bill,
transfer, PromptPay). These have no PDF and no balance, so each becomes a row
in `workspace/manual_entries.csv` and shows up before the monthly statement does. When the statement
arrives, the matching Krungthai statement row (same amount within 4 hours, 6 for payments made after the bank's
nightly cut-off) wins and the email row is dropped.
Outgoing payments only: incoming money has no email, so it appears with the next statement.

One-time Google setup (about 5 minutes):

1. Go to <https://console.cloud.google.com/>, create a project.
2. **APIs & Services → Library**: enable **Gmail API**.
3. **APIs & Services → OAuth consent screen**: choose *External*, fill the app name and your
   email, and add **your own Gmail address as a test user**.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID → Desktop app**.
5. Copy the client ID and secret into `.env` as `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`
   (and `GOOGLE_PROJECT_ID` if you like).
6. Run `./gmail.sh`. A browser opens once so you can approve read-only access. The login is
   cached in `workspace/token.json`.

Notes:
- While the consent screen is in *Testing*, Google expires the login after **7 days**; run `./gmail.sh` by hand
  and it opens the browser again (a scheduled run with nobody there stops with "Gmail login missing or expired"
  instead of hanging). Switching the consent screen to *In production* avoids
  that for your own account; Google then shows an "unverified app" warning that you can click
  through, because Gmail read access is a restricted scope and you are not submitting the app
  for verification.
- **Restrict the sender (recommended).** The default search matches Krungthai's statement email
  *subject* from any sender, so anyone could email you a fake statement PDF with that subject and it
  would be merged into your ledger. Set `GMAIL_QUERY` in `.env` to your bank's real address (look at
  an old statement email), for example `from:<bank sender address> has:attachment filename:pdf`.
  `./gmail.sh` prints the sender of every PDF it downloads so you can check.
- Work or university Google accounts may block third-party apps. Use a personal Gmail if so.
- **Unattended**: set `KTB_PW` and `KBANK_PW` in `.env` (nobody can type it), run `./gmail.sh` once by
  hand so the login exists, then schedule it, for example hourly with `crontab -e`:
  `0 * * * * cd /path/to/this/folder && ./gmail.sh >> ~/statement-gmail.log 2>&1` (keep the log outside the project
  folder: it lists the senders and amounts it found)

## Optional personalisation (all in `.env`)

| Setting | Effect |
|---|---|
| `ACCOUNT_HOLDER`, `ACCOUNT_LABEL` | your name: the initials in the top-bar avatar and the greeting; the label is added to the avatar's tooltip (the avatar shows only when `ACCOUNT_HOLDER` is set) |
| `THEME` | the dashboard's default theme (`midnight` or `daylight`); the setup page sets it |
| `LEDGER_CASH_REF` | account number in the transaction detail for *your own cash channel* → "Cash withdrawal / Cash deposit" |
| `LEDGER_PEER_REF` | a person you lend to → "Lent out / Loan repaid to me" |
| `LEDGER_STOCK_REF` | your investment account → "Stock investment / Stock return" |

Blank means off. Changes apply the next time statements are processed (`./run.sh`).
Hand-entered spends with no bank record go in `workspace/manual_entries.csv` (it does not exist until you create
it, or Gmail notices do): header line `Date,Description,Category,Amount,Balance`, then one row per spend, for example
`2026-01-31 14:05,Lunch,Food,-120,` (Date as `YYYY-MM-DD` or `YYYY-MM-DD HH:MM`, Balance blank, Amount negative for
spending). A bad row is skipped with a message.

## Where things are

```
Statement/                  your PDFs            (git-ignored)
workspace/ledger.csv        the merged ledger    (git-ignored)
workspace/expected.json     expected spending from the setup page (git-ignored)
workspace/manual_entries.csv  hand-typed spends + Gmail payment notices (git-ignored)
workspace/token.json        cached Gmail login   (git-ignored, secret)
workspace/.cache/           statements already read, so updates only read new ones (git-ignored, private)
workspace/.app/             the app window's saved labels, theme and expected spending (Linux; git-ignored)
.env                        your settings        (git-ignored, secret)
.venv/                      the Python environment ./setup.sh makes (git-ignored)
Dashboard.html              opens the dashboard  (generated, git-ignored)
web/dist/index.html         the dashboard        (generated, git-ignored)
```

Your data files, secrets and the generated dashboard are all git-ignored, so it is safe to
commit the code. The dashboard file contains your transactions: share it only on purpose.

## Troubleshooting

- **Setup stops at `python3 -m venv`, with a message about `ensurepip`** (Debian/Ubuntu) → `sudo apt install
  python3-venv`, then `./run.sh` again.
- **`./run.sh` or `./setup.sh`: Permission denied** → `bash run.sh` / `bash setup.sh`, or `chmod +x *.sh`.
- **"Not set up yet"** (from `./gmail.sh`) → run `./run.sh` or `./setup.sh` first.
- **The install failed halfway (no internet)** → run `./run.sh` again; it retries the install by itself.
- **"No PDFs in Statement/"** → add them on the page `./run.sh` opens, or copy them there first.
- **The app opens in the browser, not its own window** → the system web view is missing (see *What you need*).
  Everything works the same, in a tab. If you installed it in an environment other than the system's `python3`
  (pyenv, conda), it can't see those Linux packages: delete `.venv` and run `PATH=/usr/bin:$PATH ./setup.sh`.
- **The page didn't open** → open the `http://127.0.0.1:…/?setup=…` link that `./run.sh` printed.
  It only works once, and only while `./run.sh` is running (Ctrl+C there stops it; run `./run.sh` again for a fresh
  link). No browser on this machine: put the PDFs in `Statement/` and run
  `.venv/bin/python workspace/update_statement.py` once to create the ledger (it asks for passwords in the terminal, or
  reads `KTB_PW` / `KBANK_PW` from `.env`); after that `./run.sh --rebuild` works.
- **"Data may be missing" on the dashboard** → a statement for that period isn't in `Statement/`
  (or the balance doesn't add up across a gap). Add it and run again.
- **Wrong password** → you are asked for that file's password; unattended runs stop without touching
  the ledger. Check `KTB_PW` / `KBANK_PW`.
- **A PDF isn't read / amounts look wrong** → only Krungthai's and KBank's layouts are supported. Every
  row is still imported; a row that doesn't agree with the statement's own balances or totals is printed as
  `CHECK <file>: …` (the statement is right, so that row was misread). Send that line along when reporting it.
- **"Missing web/prebuilt/index.html"** → that file ships with the project; restore it with
  `git checkout web/prebuilt` (or download the project again).

## Security notes

- Everything stays on your machine. The only network use is the one-time `pip install` and the optional Gmail
  download (read-only; it talks only to Google). Nothing from your statements is ever uploaded.
- `.env`, `workspace/token.json`, your PDFs, `ledger.csv` and the dashboard are created readable by
  you only and are git-ignored. The dashboard file contains all your transactions: don't share it.
- Statement PDFs are parsed locally. Only run this on statements from your own bank.
- Building the dashboard runs no third-party JavaScript tooling: Python copies the prebuilt page and writes
  your data into it.
- In the app window the setup and Add statements pages talk to the app directly and no server runs. Only when
  `./run.sh` falls back to your browser does it start a small server for them, while the page is in use: it listens on
  127.0.0.1 (this computer only) on a random port, accepts the printed link's one-time token once (swapping it for a
  private cookie), and stops when you finish. Passwords stay in memory unless you tick *Remember*.

## Adding a bank

Reading statements: one `Bank(...)` entry in `BANKS` in `workspace/extract_ledger.py` (id, name, password
setting, file-name pattern, text that identifies its PDFs, parser). The setup page, password lookup and
build all read that list. Showing it: one entry in `web/src/lib/banks.ts` (name, card colour, logo).
Themes work the same way: one entry in `web/src/lib/themes.ts`, plus a `[data-theme="…"]` block in
`web/src/index.css` for colours beyond the light/dark base.

## Changing the dashboard (developers)

Only needed if you edit `web/src/`. Needs Node.js 22.12+ (or 20.19+).

```bash
cd web && npm install
npm run dev      # live preview with your own data (from the last ./run.sh)
npm run build    # rebuilds web/prebuilt/index.html: the page without data that everyone's build uses
```

Commit `web/prebuilt/index.html` with your source change, or users keep the old page. The build never
contains data (the ledger is written into the page by `workspace/build_dashboard.py`), so it is safe to commit.

There is no test suite; the Python scripts carry quick self-checks (each prints `selfcheck ok`, or `txid self-check passed` for `txid.py`), and the web app has a
linter (3 known warnings in generated `components/ui` files):

```bash
for f in extract_ledger update_statement build_dashboard welcome fetch_gmail; do .venv/bin/python workspace/$f.py --selfcheck; done
.venv/bin/python workspace/txid.py
cd web && npm run lint
```
