// The dashboard's money logic (src/lib/ledger.ts): `npm test` (watch) or `npx vitest run`. Fixtures are made up;
// nothing reads your ledger. ledger.ts reads the data tag and the saved labels when it loads, so the page's globals
// are stubbed first and the module is imported afterwards.
import { beforeAll, describe, expect, it, vi } from 'vitest'
import type { Tx } from './ledger'

const rules = [{ match: 'True Money', label: 'Wallet' }, { match: 'คนละครึ่ง', label: 'Half-half', cat: 'Own transfer' }]

let L: typeof import('./ledger')

beforeAll(async () => {
  vi.stubGlobal('localStorage', { getItem: (k: string) => (k === 'ledger-label-rules' ? JSON.stringify(rules) : null), setItem() {} })
  vi.stubGlobal('document', { getElementById: () => null })
  L = await import('./ledger')
})

const meta = (from: string, to: string) => ({ account: '', name: '', from, to, n: 0, gaps: { months: [], breaks: [] } })
const T = (date: string, amt: number, desc = 'x', cat = 'Bill / purchase', bank = 'KTB', bal: number | null = null) =>
  ({ date, desc, cat, amt, bal, bank }) as Tx

describe('labels', () => {
  // The narrowest wins (its text in fewer rows), not the longest text: "คนละครึ่ง" (9 letters) beats "True Money" (10)
  // on the row holding both, and its category takes that row out of expenses.
  it('narrowest rule wins and its category leaves expenses', () => {
    L.setData({ meta: meta('2026-01-05', '2026-01-06'), tx: [T('2026-01-05 10:00', -40, 'True Money คนละครึ่ง top-up'),
      T('2026-01-06 10:00', -10, 'True Money x')] })
    expect(L.TX.map((t) => [t.label, t.cat])).toEqual([['Half-half', 'Own transfer'], ['Wallet', 'Bill / purchase']])
    expect(L.summarize(L.TX).exp).toBe(10)
  })
})

describe('rateTable', () => {
  // "Usual" baht/day = the calendar months before the range, never the range's own month (From mid-month).
  const days = (a: string, n: number) => Array.from({ length: n }, (_, i) => T(`${L.addDays(a, i)} 12:00`, -100))

  it.each(['2026-03-15', '2026-03-01'])('usual ignores the own month (from %s)', (from) => {
    L.setData({ meta: meta('2026-02-01', '2026-03-20'), tx: days('2026-02-01', 48) })
    const r = L.rateTable(from, '2026-03-20', false)
    expect([r.nPrior, r.usual, r.own]).toEqual([1, 100, false])
  })

  it('compares with itself when nothing is earlier', () => {
    L.setData({ meta: meta('2026-03-01', '2026-03-20'), tx: days('2026-03-01', 20) })
    expect(L.rateTable('2026-03-15', '2026-03-20', false).own).toBe(true)
  })
})

describe('thisMonth', () => {
  // Payees on the plan are a part of what was spent, so cash, lending and stocks count in neither.
  it('planned never exceeds spent; Lent out counts in neither', () => {
    L.setData({ meta: meta('2026-04-02', '2026-04-03'), tx: [T('2026-04-02 10:00', -200, 'To MOM', 'Lent out'),
      T('2026-04-03 10:00', -100, 'SHOP')] })
    const month = (t: Tx) => L.thisMonth(new Set([L.payeeKey(t)]))
    expect([month(L.TX[0]).planned, month(L.TX[0]).spent]).toEqual([0, 100])
    expect([month(L.TX[1]).planned, month(L.TX[1]).spent]).toEqual([100, 100])
  })
})

describe('summarize', () => {
  // Own transfers left out, months by the row's own date (31 Dec 23:59 stays in December), opening per bank, money now
  // = last printed balance + later notices without one; a Manual (cash) row is spending but no account.
  it('totals, months, opening and closing balance', () => {
    L.setData({ meta: meta('2025-12-31', '2026-01-04'), tx: [
      T('2025-12-31 23:59', 1000, 'salary', 'Salary', 'KTB', 6000), T('2026-01-01 00:00', -200, 'shop', 'Bill / purchase', 'KBANK', 1800),
      T('2026-01-02 10:00', -500, 'to me', 'Own transfer', 'KTB', 5500), T('2026-01-02 10:01', 500, 'from me', 'Own transfer', 'KBANK', 2300),
      T('2026-01-03 09:00', -50, 'lunch', 'Food', 'Manual'), T('2026-01-04 09:00', -30, 'notice', 'Bill / purchase', 'KTB')] })
    const s = L.summarize(L.TX)
    expect([s.inc, s.exp, s.open, s.close]).toEqual([1000, 280, 7000, 7770])
    expect(s.months.map((m) => [m.m, m.inc, m.exp])).toEqual([['2025-12', 1000, 0], ['2026-01', 0, 280]])
    expect(s.closeParts.map((p) => [p.bank, p.bal, p.est])).toEqual([['KTB', 5470, true], ['KBANK', 2300, false]])
  })
})

describe('toCsv', () => {
  // Text that a spreadsheet would run as a formula is kept as text; amounts stay numbers.
  it('guards formulas', () => {
    const line = L.toCsv([T('2026-01-01 10:00', 500, '=HYPERLINK("x")', '-x', 'KTB', -12.5)]).split('\n')[1]
    expect(line).toContain(`"'=HYPERLINK(""x"")"`)
    expect(line).toContain(",'-x,")
    expect(line.endsWith(',500.00,-12.50,Krungthai')).toBe(true)
  })
})

describe('runway', () => {
  // From today (2 days after the last record); a rate of 0 never runs out.
  it('counts days from today', () => {
    expect(L.runway(1000, 100, 2, '2026-01-10')).toEqual({ days: 8, until: '2026-01-20' })
    expect(L.runway(0, 100, 2, '2026-01-10')).toEqual({ days: 0, until: '2026-01-10' })
  })
  it('never runs out at rate 0', () => {
    expect(L.runway(1000, 0, 2, '2026-01-10')).toEqual({ days: null, until: '—' })
  })
})
