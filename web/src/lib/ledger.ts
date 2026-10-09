import { bankName } from '@/lib/banks'
import type { PlanItem } from '@/lib/plan'
export type Tx = { date: string; desc: string; cat: string; amt: number; bal: number | null; bank: string; label?: string }
export type Gaps = { months: string[]; breaks: { after: string; before: string; missing: number; bank?: string }[] }
// theme / plan: picked in the setup wizard (THEME setting, workspace/expected.json); absent in older ledgers.
export type Meta = { account: string; name: string; from: string; to: string; n: number; gaps: Gaps; theme?: string; plan?: PlanItem[] }

// The ledger is not part of the build: build_dashboard.py writes it into the page's <script id="ledger-data"> tag
// (the vite dev server does the same from src/data/ledger.json). So the committed prebuilt page holds no data, and
// users need no Node: null (the untouched placeholder) = no data yet, and the app shows its empty state.
const EMPTY = { meta: { account: '', name: '', from: '', to: '', n: 0, gaps: { months: [], breaks: [] } }, tx: [] }
export const DATA: { meta: Meta; tx: Tx[] } = JSON.parse(document.getElementById('ledger-data')?.textContent || 'null') ?? EMPTY
export const TX = DATA.tx

/* ---------- your own labels: "description contains X" -> label (+ optional category), kept in this browser ---------- */
export type Rule = { match: string; label: string; cat?: string }
const RULES_KEY = 'ledger-label-rules'
export const RULES: Rule[] = (() => { try { return JSON.parse(localStorage.getItem(RULES_KEY) ?? '[]') } catch { return [] } })()
// When several labels match one description the most specific wins (longest match text; newest on a tie), so a
// narrow label ("คนละครึ่ง" for one wallet) is not hidden by a broad one ("True Money" for every wallet).
export const ruleFor = (desc: string) => {
  const d = desc.toLowerCase()
  let best: Rule | undefined
  for (const r of RULES) if (r.match && d.includes(r.match.toLowerCase()) && (!best || r.match.length >= best.match.length)) best = r
  return best
}
// Rows a rule's text appears in, whether or not it is the one that wins there.
export const rowsFor = (r: Rule) => TX.filter((t) => t.desc.toLowerCase().includes(r.match.toLowerCase()))
for (const t of TX) {  // applied once at load, so every total, chart and search sees it
  const r = ruleFor(t.desc)
  if (r) { t.label = r.label; if (r.cat) t.cat = r.cat }
}
// ponytail: save = reload, so every derived number recomputes; live store if reloading ever feels slow
export function saveRules(rules: Rule[]) {
  localStorage.setItem(RULES_KEY, JSON.stringify(rules))
  location.reload()
}
// KTB marks a payment made after its nightly cut-off (~23:00) with "~ Future Amount: 65 ~ Tran: MORPSW": the
// statement shows it posted ~01:30-02:30 the next day (unless a payment email supplied the real time, see
// update_statement.py). descOf hides that bank code for display; matching still uses the full desc.
const FUTURE = /\s*~?\s*Future\s+Amount:\s*[\d.,]*\s*~\s*Tran:\s*\S+\s*$/
export const lateNight = (t: Tx) => FUTURE.test(t.desc)
export const descOf = (t: Tx) => t.desc.replace(FUTURE, '')
export const LATE_NOTE = 'Paid after the bank’s nightly cut-off (about 23:00). The statement posts it early the next morning; the time shown is the payment email’s when there is one.'
// Default text to match on: the merchant/recipient part of a payment-email row, else the whole description.
export const merchant = (desc: string) => desc.split(' (email) ')[1] ?? desc
export const META = DATA.meta
export const YEARS = [...new Set(TX.map((r) => r.date.slice(0, 4)))].sort()
export const FIRST = META.from.slice(0, 10)
export const LAST = META.to.slice(0, 10)

export { bankName }
// Money moved between your own accounts: left out of income, expenses and spend rate (it nets to zero).
export const OWN = 'Own transfer'

// Money in each account after `rows`: per bank, the last printed balance plus later rows that carry none
// (payment-notice emails). Manual entries are cash, not in any account.
export function balanceNow(rows: Tx[]) {
  const last = new Map<string, { bank: string; bal: number; at: string; est: boolean }>()
  for (const r of rows) {
    if (r.bank === 'Manual') continue
    const b = last.get(r.bank)
    if (r.bal != null) last.set(r.bank, { bank: r.bank, bal: r.bal, at: r.date.slice(0, 10), est: false })
    else if (b) { b.bal += r.amt; b.est = true }
  }
  const parts = [...last.values()].map((p) => ({ ...p, bal: round2(p.bal) }))
  return { total: round2(parts.reduce((a, p) => a + p.bal, 0)), parts }
}

export const round2 = (n: number) => Math.round(n * 100) / 100
export const baht = (n: number) =>
  '฿' + Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
export const signed = (n: number) => (n < 0 ? '−' : '+') + baht(n)

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
export const monthName = (m: string) => MONTHS[+m.slice(5, 7) - 1]
export const monthLabel = (m: string) => `${monthName(m)} '${m.slice(2, 4)}`

type Cat = { cat: string; amt: number; n: number }
type Flow = { out: number; nOut: number; in: number; nIn: number }

export function summarize(rows: Tx[]) {
  let inc = 0, exp = 0, nIn = 0, nOut = 0
  const months = new Map<string, { m: string; inc: number; exp: number }>()
  const ecat = new Map<string, [number, number]>()
  const icat = new Map<string, [number, number]>()
  const csum = new Map<string, [number, number]>()
  const banks = new Map<string, { bank: string; in: number; out: number; nIn: number }>()
  const bump = (m: Map<string, [number, number]>, k: string, v: number) => {
    const a = m.get(k) ?? [0, 0]
    a[0] += v
    a[1]++
    m.set(k, a)
  }
  for (const r of rows) {
    if (r.cat === OWN) continue
    const mo = r.date.slice(0, 7)
    const m = months.get(mo) ?? { m: mo, inc: 0, exp: 0 }
    months.set(mo, m)
    bump(csum, r.cat, r.amt)
    const b = banks.get(r.bank) ?? { bank: r.bank, in: 0, out: 0, nIn: 0 }
    banks.set(r.bank, b)
    if (r.amt >= 0) { b.in += r.amt; b.nIn++ } else b.out -= r.amt
    if (r.amt >= 0) { inc += r.amt; nIn++; m.inc += r.amt; bump(icat, r.cat, r.amt) }
    else { exp -= r.amt; nOut++; m.exp -= r.amt; bump(ecat, r.cat, -r.amt) }
  }
  const catlist = (d: Map<string, [number, number]>): Cat[] =>
    [...d].map(([cat, v]) => ({ cat, amt: round2(v[0]), n: v[1] }))
  const flow = (o: string, i: string): Flow => {
    const a = csum.get(o) ?? [0, 0], b = csum.get(i) ?? [0, 0]
    return { out: round2(-a[0]), nOut: a[1], in: round2(b[0]), nIn: b[1] }
  }
  // Opening = each account's balance before its first row; balance series = sum of every account's latest balance.
  const first = new Map<string, number>(), latest = new Map<string, number>()
  const balance: { t: number; date: string; b: number }[] = []
  for (const r of rows) {
    if (r.bal == null) continue   // manual / payment-email rows carry no balance
    if (!first.has(r.bank)) first.set(r.bank, r.bal - r.amt)
    latest.set(r.bank, r.bal)
    balance.push({ t: new Date(r.date.replace(' ', 'T')).getTime(), date: r.date, b: round2([...latest.values()].reduce((a, v) => a + v, 0)) })
  }
  const now = balanceNow(rows)
  return {
    n: rows.length, inc: round2(inc), exp: round2(exp), net: round2(inc - exp), nIn, nOut,
    open: round2([...first.values()].reduce((a, v) => a + v, 0)),
    close: now.total,
    closeParts: now.parts,
    // money in / out per bank, biggest source of income first
    banks: [...banks.values()].map((b) => ({ ...b, in: round2(b.in), out: round2(b.out) })).sort((a, b) => b.in - a.in),
    months: [...months.values()].sort((a, b) => (a.m < b.m ? -1 : 1))
      .map((m) => ({ m: m.m, inc: round2(m.inc), exp: round2(m.exp), net: round2(m.inc - m.exp) })),
    ecat: catlist(ecat), icat: catlist(icat),
    cash: flow('Cash withdrawal', 'Cash deposit'),
    lend: flow('Lent out', 'Loan repaid to me'),
    stock: flow('Stock investment', 'Stock return'),
    balance,
  }
}
export type Summary = ReturnType<typeof summarize>

/* ---------- spend rate (฿/day per month inside a date range) ---------- */
const NOT_SPEND = new Set(['Cash withdrawal', 'Lent out', 'Stock investment'])  // own money moving, not consumed
const utcDay = (d: string) => Date.UTC(+d.slice(0, 4), +d.slice(5, 7) - 1, +d.slice(8, 10)) / 864e5
export const daysBetween = (a: string, b: string) => utcDay(b) - utcDay(a)
export const addDays = (d: string, n: number) => new Date((utcDay(d) + n) * 864e5).toISOString().slice(0, 10)
const mEnd = (k: string) => new Date(Date.UTC(+k.slice(0, 4), +k.slice(5), 0)).toISOString().slice(0, 10)
const median = (a: number[]) => {
  const s = [...a].sort((x, y) => x - y), h = s.length >> 1
  return s.length ? (s.length % 2 ? s[h] : (s[h - 1] + s[h]) / 2) : null
}

export function monthsBack(n: number) {
  let y = +LAST.slice(0, 4), m = +LAST.slice(5, 7) - (n - 1)
  while (m < 1) { m += 12; y-- }
  return `${y}-${String(m).padStart(2, '0')}-01`
}

export type RateRow = { days: number; spend: number; inc: number; out: number; rate: number }

export function rateRow(a: string, b: string, cash: boolean): RateRow {
  let spend = 0, inc = 0, out = 0
  for (const t of TX) {
    const d = t.date.slice(0, 10)
    if (d < a || d > b || t.cat === OWN) continue
    if (t.amt > 0) inc += t.amt
    else { out -= t.amt; if (cash || !NOT_SPEND.has(t.cat)) spend -= t.amt }
  }
  const days = utcDay(b) - utcDay(a) + 1
  return { days, spend, inc, out, rate: spend / days }
}

export function rateTable(from: string, to: string, cash: boolean) {
  const end = to < LAST ? to : LAST  // never count days after the last record as zero spending
  // "Usual" = median ฿/day of the calendar months before the range
  const before = new Set(TX.filter((t) => t.date < from).map((t) => t.date.slice(0, 7)))
  const prior = [...before].map((k) => rateRow(k + '-01' > FIRST ? k + '-01' : FIRST, mEnd(k), cash).rate)
  const months: (RateRow & { k: string; partial: boolean })[] = []
  for (let k = from.slice(0, 7); k <= end.slice(0, 7);) {
    const a = k + '-01' > from ? k + '-01' : from
    const b = mEnd(k) < end ? mEnd(k) : end
    months.push({ k, partial: a > k + '-01' || b < mEnd(k), ...rateRow(a, b, cash) })
    let y = +k.slice(0, 4), m = +k.slice(5) + 1
    if (m > 12) { m = 1; y++ }
    k = `${y}-${String(m).padStart(2, '0')}`
  }
  const own = !prior.length  // no earlier months: compare against the range's own months
  const usual = median(own ? months.map((m) => m.rate) : prior)
  return { months, total: rateRow(from, end, cash), usual, nPrior: own ? months.length : prior.length, own, clipped: to > LAST }
}

export const pctOf = (o: number, i: number) => (i > 0 ? ((o / i) * 100).toFixed(0) + '%' : '—')
export const idx = (r: number, usual: number | null) => (usual ? r / usual : null)

/* ---------- dashboard widgets ---------- */
// Money in / out per calendar day over the n days ending at the last record (own transfers left out).
export function daily(n: number) {
  const days = new Map<string, { d: string; in: number; out: number }>()
  for (let i = n - 1; i >= 0; i--) { const d = addDays(LAST, -i); days.set(d, { d, in: 0, out: 0 }) }
  for (const t of TX) {
    const r = days.get(t.date.slice(0, 10))
    if (!r || t.cat === OWN) continue
    if (t.amt >= 0) r.in += t.amt
    else r.out -= t.amt
  }
  return [...days.values()].map((r) => ({ ...r, in: round2(r.in), out: round2(r.out) }))
}

// Who you pay most often (or, with `inc`, who pays you). Key = your label, else the description's payee part
// (account numbers repeat per payee), so it also works as a search term for the transaction table.
export type Payee = { key: string; name: string; n: number; amt: number; last: Tx }
export const payeeKey = (t: Tx) => t.label ?? merchant(t.desc)
// `own`: keep own-account transfers too (the label editor must still list a payee the user filed as one).
export function payees(rows: Tx[], n: number, inc = false, own = false) {
  const m = new Map<string, Payee>()
  for (const t of rows) {
    if ((inc ? t.amt <= 0 : t.amt >= 0) || (t.cat === OWN && !own)) continue
    const key = payeeKey(t)
    const id = t.desc.match(/(\d{3,})\D*$/)?.[1]
    const p = m.get(key) ?? { key, name: t.label ?? (key !== t.desc ? key : `${t.cat}${id ? ` ··${id.slice(-4)}` : ''}`), n: 0, amt: 0, last: t }
    p.n++
    p.amt = round2(p.amt + Math.abs(t.amt))
    p.last = t
    m.set(key, p)
  }
  return [...m.values()].sort((a, b) => b.n - a.n).slice(0, n)
}

// Spending in the month of the last record so far; `keys` = payees on the expected-spending list, whose share is
// reported apart (the rest is unplanned).
export function thisMonth(keys: Set<string>) {
  const from = LAST.slice(0, 8) + '01', end = mEnd(LAST.slice(0, 7))
  const days = +end.slice(8)
  let planned = 0
  for (const t of TX) if (t.amt < 0 && t.cat !== OWN && t.date.slice(0, 10) >= from && keys.has(payeeKey(t))) planned -= t.amt
  return { from, end, days, spent: rateRow(from, LAST, false).spend, planned: round2(planned), elapsed: +LAST.slice(8) / days }
}

// "MR. SOMCHAI JAIDEE" -> "Somchai" for the greeting; blank when the settings carry no name.
export const firstName = (() => {
  const w = META.name.replace(/^(mr|mrs|ms|miss|นางสาว|นาย|นาง)\.?\s*/i, '').split(/\s+/)[0] ?? ''
  return w && w[0].toUpperCase() + w.slice(1).toLowerCase()
})()

// Text that a spreadsheet would run as a formula (=, +, -, @, tab, CR first) gets a leading ' so it stays text.
// Only for text columns: the Amount / Balance numbers we format ourselves and must stay numbers.
export const csvText = (v: string) => (/^[=+\-@\t\r]/.test(v) ? `'${v}` : v)

// Rows as a spreadsheet-friendly CSV (BOM so Excel reads the Thai text).
export function toCsv(rows: Tx[]) {
  const q = (v: string) => (/[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v)
  const head = ['Date', 'Description', 'Label', 'Category', 'Amount', 'Balance', 'Bank']
  const body = rows.map((t) => [t.date, csvText(t.desc), csvText(t.label ?? ''), csvText(t.cat), t.amt.toFixed(2),
    t.bal == null ? '' : t.bal.toFixed(2), csvText(bankName(t.bank))].map(q).join(','))
  return '﻿' + [head.join(','), ...body].join('\n')
}
