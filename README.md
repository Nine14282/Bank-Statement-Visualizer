# Income & Expense Ledger

Turns your **Krungthai (KTB) and Kasikorn (KBank) statement PDFs** into one merged ledger and an offline dashboard
(`web/dist/index.html`): income vs expense, balance over time, categories, monthly spend rate,
a searchable transaction table, and a warning if a statement month looks missing.

Everything runs on your machine. Nothing is uploaded. The only network use is the optional
read-only Gmail download.

> Supports Krungthai's and KBank's Thai statement PDFs (the parsers read those layouts; the bank is
> detected per file). Both accounts go into one ledger; each row shows which bank it came from, and
> transfers between the two accounts are marked "Own transfer" and left out of income and spending.
> Linux and macOS; on Windows use WSL.

## Setup (once)

Needs Python 3.10+, Node.js 20+ and npm.

```bash
./setup.sh
```

It creates `.venv`, installs the Python and web packages, creates a private `.env` from
`.env.example`, and builds the dashboard. With no data yet, `web/dist/index.html` is a blank
"No data yet" page that tells you the next steps; it fills in as soon as you add statements.
Re-running setup is safe.

## Option 1: add statements yourself

1. Put your statement PDFs in `Statement/`.
2. Run `./run.sh`.
3. Open `web/dist/index.html` in a browser.

**PDF password** (bank PDFs are usually encrypted). KTB and KBank use different passwords:
`KTB_PW` and `KBANK_PW`. KBank files are the ones named `STM_...`; each file tries its own bank's
password first. Pick one:

| How | When |
|---|---|
| Do nothing | `./run.sh` asks (typed, hidden) the first time a file needs it |
| `KTB_PW=...` and `KBANK_PW=...` in `.env` | never asked again |
| `./run.sh --password=yourpassword` | one-off, but it stays in shell history and shows in `ps` to other users of the machine |

Run it again whenever you add a new PDF. Duplicates are dropped automatically, so overlapping
statements are fine.

## Option 2: fetch from Gmail automatically

`./gmail.sh` finds statement emails, downloads new PDFs into `Statement/`, then builds the
dashboard. It only asks Gmail for **read-only** access and never changes your mailbox.

It also reads Krungthai NEXT "payment done" emails (`from:noreply@krungthai.com`, subject starts
`แจ้งผลการ…`: bill, transfer, PromptPay). These have no PDF and no balance, so each becomes a row
in `workspace/manual_entries.csv` and shows up before the monthly statement does. When the statement
arrives, the matching row (same amount within 4 hours) is dropped in favour of the statement row.
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
- While the consent screen is in *Testing*, Google expires the login after **7 days**; the
  script then opens the browser again. Switching the consent screen to *In production* avoids
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
  `0 * * * * cd /path/to/this/folder && ./gmail.sh >> gmail.log 2>&1`

## Optional personalisation (all in `.env`)

| Setting | Effect |
|---|---|
| `ACCOUNT_LABEL`, `ACCOUNT_HOLDER` | text shown in the dashboard sidebar |
| `LEDGER_CASH_REF` | account number in the transaction detail for *your own cash channel* → "Cash withdrawal / Cash deposit" |
| `LEDGER_PEER_REF` | a person you lend to → "Lent out / Loan repaid to me" |
| `LEDGER_STOCK_REF` | your investment account → "Stock investment / Stock return" |

Blank means off. Changes apply the next time statements are processed (`./run.sh`).
Hand-entered spends with no bank record go in `workspace/manual_entries.csv`
(columns `Date, Description, Category, Amount, Balance`; leave Balance blank, Amount negative for spending).

## Where things are

```
Statement/                  your PDFs            (git-ignored)
workspace/ledger.csv        the merged ledger    (git-ignored)
workspace/token.json        cached Gmail login   (git-ignored, secret)
.env                        your settings        (git-ignored, secret)
web/dist/index.html         the dashboard        (generated, git-ignored)
```

Your data files, secrets and the generated dashboard are all git-ignored, so it is safe to
commit the code. The dashboard file contains your transactions: share it only on purpose.

## Troubleshooting

- **"Not set up yet"** → run `./setup.sh`.
- **"No PDFs in Statement/"** → copy your statements there first.
- **"Data may be missing" on the dashboard** → a statement for that period isn't in `Statement/`
  (or the balance doesn't add up across a gap). Add it and run again.
- **Wrong password** → you are asked for that file's password; unattended runs stop without touching
  the ledger. Check `KTB_PW` / `KBANK_PW`.
- **A PDF isn't read / amounts look wrong** → only Krungthai's and KBank's layouts are supported. A
  KBank file whose rows don't add up to the statement's own totals is rejected rather than half-read.
- **`npm not found`** → install Node.js 20+, then `./setup.sh`.

## Security notes

- Everything stays on your machine. Gmail access is read-only; the only data sent anywhere is the
  Google login itself.
- `.env`, `workspace/token.json`, your PDFs, `ledger.csv` and the dashboard are created readable by
  you only and are git-ignored. The dashboard file contains all your transactions: don't share it.
- Statement PDFs are parsed locally. Only run this on statements from your own bank.
- Secrets from `.env` are not passed on to `npm` when the dashboard is built.
