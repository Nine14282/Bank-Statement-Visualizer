export type Tx = { date: string; desc: string; cat: string; amt: number; bal: number | null; label?: string }
export type Gaps = { months: string[]; breaks: { after: string; before: string; missing: number }[] }
export type Meta = { account: string; name: string; from: string; to: string; n: number; gaps: Gaps }

// ledger.json is written by build_dashboard.py and git-ignored, so it is absent on a fresh clone:
// the glob then matches nothing and the app shows its empty state instead of failing to build.
const files = import.meta.glob<{ default: { meta: Meta; tx: Tx[] } }>('../data/ledger.json', { eager: true })
const EMPTY = { meta: { account: '', name: '', from: '', to: '', n: 0, gaps: { months: [], breaks: [] } }, tx: [] }
export const DATA: { meta: Meta; tx: Tx[] } = Object.values(files)[0]?.default ?? EMPTY
export const TX = DATA.tx

/* ---------- your own labels: "description contains X" -> label (+ optional category), kept in this browser ---------- */
export type Rule = { match: string; label: string; cat?: string }
const RULES_KEY = 'ledger-label-rules'
export const RULES: Rule[] = (() => { try { return JSON.parse(localStorage.getItem(RULES_KEY) ?? '[]') } catch { return [] } })()
export const ruleFor = (desc: string) => RULES.find((r) => r.match && desc.toLowerCase().includes(r.match.toLowerCase()))
for (const t of TX) {  // applied once at load, so every total, chart and search sees it
  const r = ruleFor(t.desc)
  if (r) { t.label = r.label; if (r.cat) t.cat = r.cat }
}
// ponytail: save = reload, so every derived number recomputes; live store if reloading ever feels slow
export function saveRules(rules: Rule[]) {
  localStorage.setItem(RULES_KEY, JSON.stringify(rules))
  location.reload()
}
// Default text to match on: the merchant/recipient part of a payment-email row, else the whole description.
export const merchant = (desc: string) => desc.split(' (email) ')[1] ?? desc
export const META = DATA.meta
export const YEARS = [...new Set(TX.map((r) => r.date.slice(0, 4)))].sort()
export const FIRST = META.from.slice(0, 10)
export const LAST = META.to.slice(0, 10)

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
  const bump = (m: Map<string, [number, number]>, k: string, v: number) => {
    const a = m.get(k) ?? [0, 0]
    a[0] += v
    a[1]++
    m.set(k, a)
  }
  for (const r of rows) {
    const mo = r.date.slice(0, 7)
    const m = months.get(mo) ?? { m: mo, inc: 0, exp: 0 }
    months.set(mo, m)
    bump(csum, r.cat, r.amt)
    if (r.amt >= 0) { inc += r.amt; nIn++; m.inc += r.amt; bump(icat, r.cat, r.amt) }
    else { exp -= r.amt; nOut++; m.exp -= r.amt; bump(ecat, r.cat, -r.amt) }
  }
  const catlist = (d: Map<string, [number, number]>): Cat[] =>
    [...d].map(([cat, v]) => ({ cat, amt: round2(v[0]), n: v[1] }))
  const flow = (o: string, i: string): Flow => {
    const a = csum.get(o) ?? [0, 0], b = csum.get(i) ?? [0, 0]
    return { out: round2(-a[0]), nOut: a[1], in: round2(b[0]), nIn: b[1] }
  }
  const known = rows.filter((r) => r.bal != null)  // manual rows carry no balance
  const k0 = known[0], kN = known[known.length - 1], last = rows[rows.length - 1]
  return {
    n: rows.length, inc: round2(inc), exp: round2(exp), net: round2(inc - exp), nIn, nOut,
    open: k0 ? round2(k0.bal! - k0.amt) : 0,
    // last printed balance + later rows with no balance (payment-notice emails), so it matches "Current money"
    close: kN ? round2(kN.bal! + rows.slice(rows.indexOf(kN) + 1).reduce((a, r) => a + r.amt, 0)) : 0,
    closeAt: kN && kN !== last ? kN.date.slice(0, 10) : '',
    months: [...months.values()].sort((a, b) => (a.m < b.m ? -1 : 1))
      .map((m) => ({ m: m.m, inc: round2(m.inc), exp: round2(m.exp), net: round2(m.inc - m.exp) })),
    ecat: catlist(ecat), icat: catlist(icat),
    cash: flow('Cash withdrawal', 'Cash deposit'),
    lend: flow('Lent out', 'Loan repaid to me'),
    stock: flow('Stock investment', 'Stock return'),
    balance: known.map((r) => ({ t: new Date(r.date.replace(' ', 'T')).getTime(), date: r.date, b: r.bal! })),
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
    if (d < a || d > b) continue
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
