# Statement Visualizer

Turns your **Krungthai (KTB) and Kasikorn (KBank) statement PDFs** into one merged ledger and an offline dashboard,
shown in its own app window (or any browser): income vs expense, balance over time, categories, monthly spend rate,
a searchable transaction table, and a warning if a statement month looks missing.

Everything runs on your machine. Nothing is uploaded. Apart from the one-time package install, the only network use
is the optional read-only Gmail download.

**In short:** `git clone` the project and run `./install.sh`. Later, open **Statement Visualizer** and drop in your
statement PDFs. See [Install](#install) and [Get started](#get-started).

> Supports Krungthai's and KBank's Thai statement PDFs (the parsers read those layouts; the bank is
> detected per file). Both accounts go into one ledger; each row shows which bank it came from, and
> transfers between the two accounts are marked "Own transfer" and left out of income and spending.
> Developed and tested on Linux. macOS support is written but **untested**. Windows works in **browser mode** as a standalone program (`StatementVisualizer.exe`, no Python needed), not yet tested on a real Windows PC; its app window comes later.

## What you need

| | |
|---|---|
| **OS** | **Linux** (tested). **macOS**: written for but untested, so expect rough edges (a fresh Mac's system Python is often 3.9, so install Python 3.10+ from Homebrew or python.org first). **Windows** 10/11: a standalone program in browser mode, no Python needed (see [Windows](#windows)), not yet tested on a real Windows PC. |
| **Python** | 3.10 or newer, with `venv`. Debian/Ubuntu: `sudo apt install python3 python3-venv`. |
| **Internet** | for the first install (pip downloads a few packages and their dependencies) and for the optional Gmail download. Nothing else is ever sent anywhere. |
| **App window** (Linux, optional) | Qt's web view (PyQt6), installed by pip into `.venv/`: a ~200 MB download, ~550 MB on disk. On an X11 desktop (not Wayland) also `sudo apt install libxcb-cursor0`. Without it everything works in your browser instead (or install with `./install.sh --web`, which skips the download). macOS needs nothing extra. |
| **Node.js** | not needed. Only if you edit the dashboard's source (see the end). |

## Install

```bash
git clone https://github.com/Nine14282/Income-and-Expenses-Dashboard.git
cd Income-and-Expenses-Dashboard
./install.sh          # the app window (default)
./install.sh --web    # or: browser only, no app window
```

On **Windows**, see [Windows](#windows) below.

Two ways to use it, pick one (you can switch later by running the other command): the **app** gets its own window
and an app-menu entry; **browser only** skips the window and the extra package for it, and `./run.sh` opens the same
pages in your browser. Re-running `./install.sh` with no flag keeps whichever you chose.

That is the whole install: it gets the app onto your computer and **does not open it**. It takes about a minute (a few
minutes for the app window on Linux) and needs the internet. It:

1. checks Python 3.10+;
2. creates a private Python environment in `.venv/` and installs `requirements.txt` into it (app mode also installs
   `requirements-app.txt`: pywebview, and on Linux PyQt6 with its web view);
3. creates `Statement/` (put your PDFs here) and a private `.env` settings file from `.env.example` (readable by you
   only);
4. builds an empty dashboard page;
5. app mode only: **Linux** asks *Add Statement Visualizer to your app menu? [Y/n]* (the default is yes; it only writes a
   `.desktop` file under `~/.local/share/applications/`). **macOS** writes `Statement Visualizer.command` in the
   project folder, to double-click.

When it finishes it tells you how to open the app (next section). Re-running `./install.sh` is safe: it keeps your
`.env` values and your data. To take it off your computer again, see [Uninstall](#uninstall).

Downloaded the project as a zip and `./install.sh` says *Permission denied*? The zip lost the "executable" mark: run
`chmod +x *.sh` once, then `./install.sh` again.

## Get started

Installing did not open anything. Open the app whenever you want to use it:

- **Linux**: **Statement Visualizer** in your app menu.
- **macOS** (untested): double-click `Statement Visualizer.command` in the project folder.
- **From a terminal (any system)**: `./run.sh` in the project folder. This is what the menu entry runs.

Everything after that happens in the app, no terminal needed. Your first time there is no data yet, so the app opens a
short setup, one screen per step, **Next** to go on (**Skip** on the optional Spending step; about 2 minutes in all):

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

### Using it later

- **Menu entry missing (Linux)?** You answered *no* to the app-menu question during install: re-run `./install.sh` and
  answer Y (it also refreshes the entry if you moved the project folder). In GNOME, right-click the entry →
  *Add to Favourites* pins it to the dock.
- **Just look at the last dashboard**: double-click `Dashboard.html` in the project folder to see it in a browser
  (install creates it empty; it shows your data after the first build). Keep it in the project folder: it just forwards
  to `web/dist/index.html`.
- **Inside the app**: **Add statements** (top bar) for new PDFs, and the gear for settings (the same steps again:
  theme, expected spending, passwords). On Linux the window keeps its own labels, expected spending and theme (in
  `workspace/.app/`), apart from any browser's; on macOS it uses the system web view's own store. It reopens at the
  size you left it (Linux), **Export CSV** asks where to save the file, **Esc** closes Add statements or Settings, and only one window opens at a time (a second
  launch just says it's already open).

**No app window?** Installed with `./install.sh --web`, or Qt's web view can't open here, `./run.sh` opens the same setup and add-statements pages in your
browser instead. If the tab doesn't open on its own, go to the one-time link `./run.sh` printed
(`http://127.0.0.1:…/?setup=…`) and leave that terminal open while you use the page. `./run.sh --web` skips the window on an
app install; `./run.sh --setup` opens the full setup in the browser again.

### Updating and resetting

- **Update the project**: `git pull`, then open the app as usual (or re-run `./install.sh`). Opening it reinstalls
  the packages by itself if `requirements.txt` changed, and always rebuilds the dashboard page first.
- **Start over with your data**: `./clear.sh` puts all your data back to how a fresh install looks, and keeps the
  installed app (the `.venv`, the app-menu entry, the code). It deletes your statement PDFs, the ledger, your hand-typed
  rows (`workspace/manual_entries.csv`), the dashboard page (it holds your transactions), the statement cache, your
  expected spending, the saved Gmail login and what the app window saved (labels, theme), and resets `.env` to the blank
  template (passwords, Google client id/secret, your name, theme). It lists everything and asks first (`-y` skips the
  question), then rebuilds a blank dashboard. It cannot clear what a *browser* saved (use its site-data settings) or the
  access you gave Google (see [Uninstall](#uninstall), step 4).
- **Remove it completely**: see [Uninstall](#uninstall).

## Uninstall

Nearly everything lives inside the project folder, so removing it is mostly deleting that folder. The script does the
local part for you:

```bash
./uninstall.sh           # removes the app-menu entry/launcher, .venv, web/node_modules and the generated dashboard;
                         # keeps your PDFs, ledger, .env and Gmail login (./install.sh sets it all up again)
./uninstall.sh --all     # also deletes this whole project folder, data included; you must type the folder name
./uninstall.sh -n        # only list what would be removed (add -y to skip the "Continue?" question)
```

It cannot remove a listener service or the access you gave Google (steps 3 and 4 below); it reminds you. To do it by
hand instead, or to see what the script does, follow these steps in order:

1. **Keep what you want first.** Deleting the folder also deletes your statement PDFs (`Statement/`), the ledger
   (`workspace/ledger.csv`), your hand-typed rows (`workspace/manual_entries.csv`), and `.env`, which holds any
   passwords you chose to *Remember* and your Gmail client secret. Copy out anything you still need. To empty the
   data but keep the install, use `./clear.sh` instead (see above).
2. **Remove the launcher** (it sits outside the folder on Linux):
   - **Linux**: `rm ~/.local/share/applications/statement-visualizer.desktop` (under `$XDG_DATA_HOME/applications/`
     if you set that).
   - **macOS** (untested): the launcher is `Statement Visualizer.command` inside the folder, so step 5 removes it.
3. **Stop the listener service**, if you made one: `systemctl --user disable --now statement-gmail`, then delete
   `~/.config/systemd/user/statement-gmail.service`. (An older install may also have a `./gmail.sh` line in
   `crontab -e`; delete it.)
4. **Revoke the Gmail access**, if you used Option 2: open <https://myaccount.google.com/permissions>, pick the app
   name you gave your Google Cloud project, and choose *Remove access*. You can also delete that project in the
   [Google Cloud console](https://console.cloud.google.com/). Deleting the folder removes the saved login
   (`workspace/token.json`) from this computer but does not revoke it at Google.
5. **Delete the project folder** (this also removes the `.venv`, so nothing was installed system-wide):
   ```bash
   cd .. && rm -rf Income-and-Expenses-Dashboard
   ```
   Use your folder's real name. Check you are deleting the right folder first: `rm -rf` has no undo.
6. **Optional leftovers**:
   - Your browser keeps the dashboard's labels, expected spending and theme in its own site data for the
     `Dashboard.html` page. Clear it in the browser's site-data settings if you opened the dashboard in a browser.
   - On macOS the app window keeps the same settings in the system web view's own store (on Linux they were in
     `workspace/.app/`, which step 5 removed).
   - Linux: the app window's small web view folders, `~/.cache/statement-visualizer` and
     `~/.local/share/statement-visualizer` (`./uninstall.sh` removes them).
   - Packages you installed with `apt` yourself (`python3-venv`, `libxcb-cursor0`) are general system packages and are
     left alone. Remove them only if nothing else uses them.

## Option 1: add statements yourself

1. In the app, press **Add statements** (top bar). (No app window: `./run.sh` opens the same page in your browser.)
   - **Statements**: drop in the new PDFs your bank sent (they are copied into `Statement/`).
   - **Passwords**: only if a file needs one you haven't saved; tick *Remember* to never be asked again.
   - **Update my dashboard**: new statements are read (ones read before come from `workspace/.cache/`) and the
     dashboard comes back with them.
2. That's it. (A dashboard already open in another browser tab doesn't change by itself: reload it.)

Forgot the command? In a browser tab (not the app window), the dashboard's **Add statements** button shows it, with
your project folder filled in and a copy button.

No browser (a server over SSH, or you just copied files into `Statement/` by hand)? `./run.sh --rebuild`
rebuilds in the terminal (it needs at least one PDF in `Statement/` and an existing ledger, so do the first run
through the app or `./run.sh` first). Run from a script, with nobody at the terminal, `./run.sh` does the same.

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
dashboard. It only asks Gmail for **read-only** access and never changes your mailbox. It imports only the
banks' own emails, matched by sender and subject (fixed per bank in `workspace/banks/`, not a setting): Krungthai
statements from `noreply@krungthai.com` ("ส่งรายการเดินบัญชีเงินฝาก") and KBank statements from
`K-ElectronicDocument@kasikornbank.com` ("E-statement for saving account").

It also reads Krungthai NEXT "payment done" emails (from `noreply@krungthai.com`, containing `แจ้งผลการ…`: bill,
transfer, PromptPay). These have no PDF and no balance, so each becomes a row
in `workspace/manual_entries.csv` and shows up before the monthly statement does. When the statement
arrives, the matching Krungthai statement row (same amount within 4 hours, 6 for payments made after the bank's
nightly cut-off) wins and the email row is dropped.
Outgoing payments only: incoming money has no email, so it appears with the next statement.
KBank's K PLUS "Result of … (Success)" emails (from `KPLUS@kasikornbank.com`: bill and shop payments, transfers,
PromptPay) are read the same way and matched against KBank statement rows. Their rows start with `K PLUS`.
A payment email older than its bank's first statement row is left out of the ledger, because there is no statement to
check it against (K PLUS keeps years of them). It stays in `manual_entries.csv` and is matched if you add that older
statement later.

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

Once the keys are in `.env`, the "add statements" page (`./run.sh`, or Add statements in the app) also shows a
**Fetch from Gmail** button: it does the same download into `Statement/`, then you press Update as usual.

Notes:
- While the consent screen is in *Testing*, Google expires the login after **7 days**; run `./gmail.sh` by hand
  and it opens the browser again (the listener, with nobody there, stops with "Gmail login missing or expired"
  instead of hanging). Switching the consent screen to *In production* avoids
  that for your own account; Google then shows an "unverified app" warning that you can click
  through, because Gmail read access is a restricted scope and you are not submitting the app
  for verification.
- Only the banks' own sender addresses are searched, so a stranger can't mail a fake statement into your ledger.
  `./gmail.sh` prints the sender of every PDF it downloads so you can check.
- Work or university Google accounts may block third-party apps. Use a personal Gmail if so.
- `./gmail.sh` is a command you run when you want. For new mail to come in **by itself**, set up the real-time
  listener below: it is the only automatic fetch (nothing runs on a schedule). It reads new PDFs with nobody there to
  type a password, so set `KTB_PW` and `KBANK_PW` in `.env` (or tick *Remember* on the setup page).

### Real time: Gmail push (optional)

`./gmail.sh --listen` keeps running and fetches within seconds of a new email, both statement
PDFs and payment notices, exactly as `./gmail.sh` does. Gmail posts every inbox change to a Google Cloud Pub/Sub
topic and the listener pulls from it, so your computer needs no public address. It only searches the last 7 days of
mail: what arrived while it was off is fetched when it starts, unless it was off longer than that (then run
`./gmail.sh` once, which searches everything). It does need the computer on, and it adds a few Google Cloud steps on top of the setup
above:

1. **APIs & Services → Library**: enable **Cloud Pub/Sub API**. Google may ask you to link a billing account; the
   usage stays inside the free tier (see *Cost* below).
2. **Pub/Sub → Topics → Create topic**, for example `gmail-push`. Untick *Add a default subscription*.
3. Open the topic → **Permissions → Add principal** `gmail-api-push@system.gserviceaccount.com` with the role
   **Pub/Sub Publisher**. (A work or university organisation may refuse this; use a project under a personal Gmail.)
4. **Pub/Sub → Subscriptions → Create**: pick that topic, delivery type **Pull**, message retention **1 day**, and
   leave *Retain acknowledged messages* off.
5. **Google Auth Platform → Data Access → Add scope** `https://www.googleapis.com/auth/pubsub`.
6. In `.env`, set `GOOGLE_PROJECT_ID`, `GMAIL_TOPIC` (the topic ID) and `GMAIL_SUBSCRIPTION` (the subscription ID).
7. Run `./gmail.sh --listen` in a terminal. The browser asks you to sign in again, because the login now includes
   Pub/Sub; then it prints `Listening for new mail`. Send yourself an email to see it react. Ctrl+C stops it.

After that, **the app starts it for you**. With `GMAIL_TOPIC` set, opening the app (the menu entry or `./run.sh`) runs
the listener in the background until you close the window. A fetch or rebuild still in progress finishes first.
When it has fetched something, the open window shows the new rows straight away (they slide in): the listener tells
the app, nothing polls. A dashboard in a browser tab is not told: reload it.
Its output goes to `workspace/.app/gmail-listen.log`. It cannot open a browser, so if the login expires it stops and
logs "Gmail login missing or expired": sign in again with `./gmail.sh` or the **Fetch from Gmail** button. Only one
listener runs at a time, so the app and the service below never both listen. While the service is running, the
app's own listener steps aside, so an open window doesn't update by itself; reopen it to see new rows.

To keep it listening while the app is closed on Linux, make it a user service. Save this as
`~/.config/systemd/user/statement-gmail.service` (use your folder's real path):

```ini
[Unit]
Description=Statement Visualizer Gmail listener

[Service]
ExecStart=/path/to/this/folder/gmail.sh --listen
Environment=PYTHONUNBUFFERED=1
Restart=always
RestartSec=60

[Install]
WantedBy=default.target
```

then run `systemctl --user enable --now statement-gmail` and watch it with `journalctl --user -u statement-gmail -f`.
On macOS (untested), leave it running in a terminal or wrap it in a launchd agent.

**Cost.** Pub/Sub bills by data moved, not by hours running: each request counts as at least 1 KB, and the first
10 GiB a month are free. Ten emails a day comes to well under 100 MB a month, so it costs $0. Keep it that way with
the 1-day retention from step 4, no message retention on the topic and no snapshots. A budget alert at $1
(**Billing → Budgets & alerts**) tells you if anything changes.

Notes:
- The 7-day *Testing* login expiry above applies here too: the listener stops with "Gmail login missing or expired",
  and you run `./gmail.sh` by hand to sign in again. Put `KTB_PW` and `KBANK_PW` in `.env` so it can rebuild alone.
- Only inbox changes are announced. A statement that one of your Gmail filters moves past the inbox is still fetched,
  but at the next inbox change or the next start, not instantly.
- With `GMAIL_TOPIC` set, `workspace/token.json` also grants Pub/Sub access to your Google Cloud projects. Keep it
  as private as before.

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
spending). A bad row is skipped with a message. Payment emails add a sixth column, `Bank`; leave it blank on rows
you type.

## Terminal commands

You never need these to use the app; they are here for reference.

| Command | What it does |
|---|---|
| `./install.sh` | installs the app window (see [Install](#install)); safe to re-run |
| `./install.sh --web` | installs for the browser only: no app window package, no menu entry |
| `./uninstall.sh` | removes it again (see [Uninstall](#uninstall)) |
| `./run.sh` | opens the app, the same as the menu entry; on a fresh clone it installs first |
| `./run.sh --web` | opens the browser pages instead of the app window |
| `./run.sh --setup` | the full first-time setup again, in your browser |
| `./run.sh --rebuild` | rebuilds from the PDFs in `Statement/` in the terminal, no window |
| `./gmail.sh` | downloads new statements from Gmail, then rebuilds (Option 2) |
| `./gmail.sh --listen` | keeps running and does the same within seconds of new mail ([Real time](#real-time-gmail-push-optional)) |
| `./clear.sh` | resets all your data and settings to a fresh-install state, keeping the app (see [Updating and resetting](#updating-and-resetting)) |
| `./setup.sh` | the install step itself, which `./install.sh` and `./run.sh` call (`--app` / `--web` like `./install.sh`); running it directly also opens the app afterwards |

Every command is a small wrapper around `workspace/launcher.py`, which does the work the same way on every system.
On Windows the same commands are `.\StatementVisualizer.exe run`, `.\StatementVisualizer.exe gmail`, and so on (see below),
with the same options.

### Windows

Windows gets a **standalone program**: `StatementVisualizer.exe` with its `_internal` folder, built with PyInstaller,
so no Python is needed. It runs in **browser mode**: the setup and add-statements pages and the dashboard open in your
browser (the app window comes later). Not yet tested on a real Windows PC, so expect rough edges and please report
them.

1. Get the program: the `StatementVisualizer-windows-<commit>` artifact of the latest
   [Windows build](https://github.com/Nine14282/Income-and-Expenses-Dashboard/actions/workflows/windows-build.yml) run
   on `main` (you must be signed in to GitHub; artifacts are kept 90 days). GitHub downloads it as a zip holding
   `StatementVisualizer-windows.zip`; extract that one too. Or build it yourself (below).
2. Put the `StatementVisualizer` folder somewhere of yours, in a folder of its own, e.g.
   `Documents\StatementVisualizer`. Your statements, ledger and settings are saved next to the `.exe` (the same
   `Statement\`, `workspace\` and `.env` layout as above), so: not `Program Files` (not writable), not loose on the
   Desktop or in Downloads (it refuses, since `clear` and `uninstall` delete there), and not a new folder at `C:\` (other
   accounts on the PC could read it; it warns outside your user folder).
3. Double-click **`StatementVisualizer.exe`**: the first time it opens the setup page, later the add-statements page.
   Keep its window open while you use the page.

The other commands, in a terminal (PowerShell or Command Prompt) in that folder: `.\StatementVisualizer.exe run
--rebuild`, `.\StatementVisualizer.exe gmail` (`--listen`), `.\StatementVisualizer.exe clear`,
`.\StatementVisualizer.exe uninstall` (it removes the files it made, and your data with `--all`, never the folder
itself; then delete the folder by hand). Windows may warn about an unrecognised app the first time: the program isn't
code-signed. More info, then Run anyway; or build it yourself.

Updating: replace `StatementVisualizer.exe` and `_internal\` with the new ones and keep `Statement\`, `workspace\` and
`.env`. The first update after a new version reads every PDF once more (its parse cache is per program version).

The dashboard is `Dashboard.html` in that folder; open it in your browser. If an update says it can't write
`ledger.csv`, close the file in Excel (Windows won't replace a file another program has open). Real-time Gmail
(`.\StatementVisualizer.exe gmail --listen`) has no service manager here: run it in a terminal you keep open.

**Building it yourself** (on Windows, with Python 3.10+; PyInstaller only builds for the system it runs on). The
packages are installed from `requirements-build.lock`, exact versions with their hashes:

```bat
py -m venv build-venv
build-venv\Scripts\pip install --require-hashes -r requirements-build.lock
build-venv\Scripts\pyinstaller --clean --noconfirm statement-visualizer.spec
```

The program is `dist\StatementVisualizer\`; copy that whole folder where you want it (don't use it inside `dist\`: it
would keep your data there). From source without building, `py workspace\launcher.py run` (and `install`, `gmail`,
...) also works.

## Where things are

```
Statement/                  your PDFs            (git-ignored)
workspace/ledger.csv        the merged ledger    (git-ignored)
workspace/expected.json     expected spending from the setup page (git-ignored)
workspace/manual_entries.csv  hand-typed spends + Gmail payment notices (git-ignored)
workspace/token.json        cached Gmail login   (git-ignored, secret)
workspace/.cache/           statements already read, so updates only read new ones (git-ignored, private)
workspace/.app/             the app window's saved labels, theme and expected spending (Linux; git-ignored),
                            its size (window.json), and the real-time Gmail log gmail-listen.log
.env                        your settings        (git-ignored, secret)
.venv/                      the Python environment ./install.sh makes (git-ignored)
Dashboard.html              opens the dashboard  (generated, git-ignored)
web/dist/index.html         the dashboard        (generated, git-ignored)
```

Your data files, secrets and the generated dashboard are all git-ignored, so it is safe to
commit the code. The dashboard file contains your transactions: share it only on purpose.

## Troubleshooting

- **Setup stops at `python3 -m venv`, with a message about `ensurepip`** (Debian/Ubuntu) → `sudo apt install
  python3-venv`, then `./install.sh` again.
- **`./install.sh` or `./run.sh`: Permission denied** → `chmod +x *.sh`, then again.
- **"Not set up yet"** (from `./gmail.sh`) → run `./install.sh` first.
- **The install failed halfway (no internet)** → run `./install.sh` again (`./run.sh` also retries it by itself).
- **"No PDFs in Statement/"** → add them on the page `./run.sh` opens, or copy them there first.
- **The app opens in the browser, not its own window** → Qt's web view couldn't open here (see *What you need*).
  Everything works the same, in a tab. On an X11 desktop: `sudo apt install libxcb-cursor0`. Otherwise run
  `./install.sh` again (the window's download may have failed), and `.venv/bin/python workspace/app.py` in a terminal
  to see the reason.
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
  download (read-only; it talks only to Google, including Pub/Sub for `--listen`). Nothing from your statements is
  ever uploaded.
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

Reading statements: one module per bank in `workspace/banks/` (`ktb.py`, `kbank.py`): its parser, a
self-check, and a `BANK = Bank(...)` record (id, name, password setting, file-name pattern, text that
identifies its PDFs). Copy the closest one, then add it to `BANKS` in `workspace/banks/__init__.py`. The
setup page, password lookup and build all read that list. Showing it: one entry in `web/src/lib/banks.ts` (name, card colour, logo).
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
