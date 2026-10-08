import { useMemo, useState, type ReactNode } from 'react'
import Avatar from '@mui/material/Avatar'
import MuiTooltip from '@mui/material/Tooltip'
import { AnimatePresence, motion } from 'motion/react'
import { ArrowDownLeft, ArrowRight, ArrowUpRight, Gauge, Hourglass, Receipt, Smartphone } from 'lucide-react'
import { BalanceArea, DailyBars, FlowLines } from '@/components/ledger/charts'
import { InfoTip } from '@/components/ledger/info'
import { CountUp } from '@/components/ledger/motion'
import { TxDrawer } from '@/components/ledger/tx-drawer'
import { BANKS } from '@/lib/banks'
import { goTo } from '@/lib/nav'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { LAST, bankName, baht, daily, descOf, monthLabel, payees, signed, thisMonth, type Payee, type Summary, type Tx } from '@/lib/ledger'
import { expectedFor, type PlanItem } from '@/lib/plan'
import { EASE, cn } from '@/lib/utils'

// Pill switch whose lit background slides to the picked option (one shared layoutId per switch).
export function Segmented<T extends string>({ id, value, onChange, options, big, label, className }: {
  id: string; value: T; onChange: (v: T) => void; options: { value: T; label: ReactNode }[]; big?: boolean; label: string; className?: string
}) {
  return (
    <div role="radiogroup" aria-label={label} className={cn('inline-flex flex-wrap gap-1 rounded-full border bg-card p-1', className)}>
      {options.map((o) => {
        const on = o.value === value
        return (
          <button key={o.value} type="button" role="radio" aria-checked={on} onClick={() => onChange(o.value)}
            className={cn('relative rounded-full font-medium whitespace-nowrap transition-colors duration-300', big ? 'px-4 py-2 text-sm pointer-coarse:min-h-11' : 'px-3 py-1.5 text-xs pointer-coarse:min-h-11',
              on ? 'text-white' : 'text-muted-foreground hover:text-foreground')}>
            {on && <motion.span layoutId={id} transition={{ type: 'spring', stiffness: 420, damping: 32 }}
              className="absolute inset-0 rounded-full bg-brand shadow-[0_6px_16px_-6px_var(--brand)]" />}
            <span className="relative">{o.label}</span>
          </button>
        )
      })}
    </div>
  )
}

const RoundLink = ({ label, to, children }: { label: string; to: string; children: ReactNode }) => (
  <MuiTooltip title={label}>
    <button type="button" aria-label={label} onClick={() => goTo(to)}
      className="grid size-10 place-items-center rounded-full border bg-card text-muted-foreground transition hover:-translate-y-0.5 hover:text-foreground hover:shadow-md active:scale-95">
      {children}
    </button>
  </MuiTooltip>
)

const pct = (n: number) => `${n >= 0 ? '+' : '−'}${Math.abs(n * 100).toFixed(1)}%`
const SKINS = [
  'linear-gradient(120deg, oklch(0.62 0.2 280), oklch(0.56 0.23 300))',
  'linear-gradient(120deg, oklch(0.76 0.16 60), oklch(0.68 0.19 38))',
  'linear-gradient(120deg, oklch(0.74 0.13 330), oklch(0.66 0.17 310))',
]
// Each bank's colour and logo come from lib/banks.ts; a bank without them falls back to SKINS + initials.
const skinOf = (bank: string, i: number) => BANKS[bank]?.skin ?? SKINS[i % SKINS.length]
// The two main cards (wallet, overview) get a violet ring and glow so they read first.
const HERO = 'ring-2 ring-brand/20 shadow-[0_28px_64px_-30px_var(--brand)]'

export const BankLogo = ({ bank, size = 22 }: { bank: string; size?: number }) => {
  const b = BANKS[bank]?.img ? BANKS[bank] : undefined
  return (
    <span className="grid shrink-0 place-items-center rounded-full shadow-sm ring-1 ring-black/10"
      style={{ width: size, height: size, color: '#555', background: b?.badge ?? '#fff' }}>
      {b ? <img src={b.img} alt="" width={size * (b.full ? 1 : 0.8)} height={size * (b.full ? 1 : 0.8)}
          className={cn(!b.full && 'drop-shadow-[0_1px_1px_rgb(0_0_0/0.25)]')} />
        : <b className="text-[9px] leading-none">{bankName(bank).slice(0, 2).toUpperCase()}</b>}
    </span>
  )
}

// One coloured tab per account, stacked like cards in a wallet (they fan out on hover), over the total
// and a "where your money comes from" split of this period's money in by bank.
export function WalletStack({ s }: { s: Summary }) {
  const change = s.open ? (s.close - s.open) / Math.abs(s.open) : null
  const order = s.closeParts.map((p) => p.bank)
  const tint = (bank: string) => skinOf(bank, Math.max(0, order.indexOf(bank)))
  return (
    <Card data-od-id="kpis" className={cn('gap-0 bg-muted/70 p-2 dark:bg-muted/40', HERO)}>
      <motion.div initial="rest" animate="rest" whileHover="fan" className="px-2 pt-2">
        {s.closeParts.map((p, i) => (
          <motion.div key={p.bank} variants={{ rest: { marginTop: i ? -40 : 0 }, fan: { marginTop: i ? -22 : 0 } }}
            transition={{ type: 'spring', stiffness: 300, damping: 24 }}
            className="flex h-24 items-start justify-between rounded-2xl px-4 pt-3 text-white shadow-[0_-6px_16px_-8px_rgb(0_0_0/0.35)]"
            style={{ background: skinOf(p.bank, i) }}>
            <span className="flex items-center gap-2.5 text-sm font-semibold"><BankLogo bank={p.bank} size={30} />{bankName(p.bank)}</span>
            <span className="num pt-1 text-sm font-semibold">{baht(p.bal)}</span>
          </motion.div>
        ))}
      </motion.div>
      <div className={cn('relative z-10 flex flex-1 flex-col gap-5 rounded-[1.25rem] bg-card p-5 shadow-[0_-10px_24px_-14px_rgb(0_0_0/0.35)]', s.closeParts.length && '-mt-12')}
        style={{ mask: 'radial-gradient(circle 26px at 50% 0, transparent 25px, #000 26px)' }}>
        <div className="flex items-center justify-between">
          <span className="rounded-full border px-2.5 py-0.5 text-xs">{s.closeParts.length} account{s.closeParts.length === 1 ? '' : 's'}</span>
          <RoundLink label="How long will it last?" to="predict"><Hourglass className="size-4" /></RoundLink>
        </div>
        <div>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            Total balance
            <InfoTip>Money in all your bank accounts now: each statement's last balance plus payment emails after it. The % compares it with the balance at the start of the period.</InfoTip>
            {change != null && <span className={cn('num rounded-full px-2 py-0.5 text-xs font-semibold', change >= 0 ? 'bg-pos/15 text-pos' : 'bg-neg/15 text-neg')}>{pct(change)}</span>}
          </div>
          <CountUp value={s.close} format={baht} className="display mt-1 block text-5xl sm:text-6xl" />
          <p className="num mt-1.5 text-xs text-muted-foreground">opened at {baht(s.open)}</p>
        </div>
        {s.inc > 0 && (
          <div className="mt-auto space-y-3 border-t pt-4" data-od-id="bank-sources">
            <p className="flex items-center gap-1.5 text-base font-medium">Where your money comes from
              <InfoTip>Money received in this period, split by the bank it arrived in. Transfers between your own accounts are left out.</InfoTip></p>
            <div className="flex h-3 gap-1 overflow-hidden rounded-full">
              {s.banks.filter((b) => b.in > 0).map((b, i) => (
                <motion.span key={b.bank} className="h-full min-w-1.5 rounded-full" style={{ background: tint(b.bank) }}
                  initial={{ flexGrow: 0 }} animate={{ flexGrow: b.in }} transition={{ duration: 0.8, delay: 0.2 + i * 0.05, ease: EASE }} />
              ))}
            </div>
            <ul className="space-y-2.5">
              {s.banks.filter((b) => b.in > 0).map((b, i) => (
                <motion.li key={b.bank} className="flex items-center gap-3" initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.3 + i * 0.08, duration: 0.4, ease: EASE }}>
                  <BankLogo bank={b.bank} size={32} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-semibold" title={bankName(b.bank)}>{bankName(b.bank)}</span>
                    <span className="num block text-xs text-muted-foreground">{b.nIn} deposit{b.nIn === 1 ? '' : 's'}</span>
                  </span>
                  <span className="text-right">
                    <span className="num block text-sm font-semibold">{baht(b.in)}</span>
                    <span className="num block text-xs text-muted-foreground">{((b.in / s.inc) * 100).toFixed(1)}% of income</span>
                  </span>
                </motion.li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Card>
  )
}

// Income / expense curves per month, or the running balance, with the period totals counting up on top.
export function Overview({ s }: { s: Summary }) {
  const [view, setView] = useState<'flow' | 'balance' | 'table'>('flow')
  // One sentence that says what the chart shows, so the numbers read without hovering.
  const top = s.months.reduce<Summary['months'][number] | null>((a, m) => (!a || m.exp > a.exp ? m : a), null)
  const avgExp = s.months.length ? s.exp / s.months.length : 0
  const short = s.months.filter((m) => m.net < 0).length
  const stats: [string, number, (n: number) => string, string][] = [
    ['Income', s.inc, baht, 'var(--income)'], ['Expenses', s.exp, baht, 'var(--expense)'], ['Net change', s.net, signed, s.net >= 0 ? 'var(--pos)' : 'var(--neg)'],
  ]
  return (
    <Card data-od-id="chart-monthly" className={cn('min-w-0', HERO)}>
      <CardHeader className="pb-0">
        <CardTitle className="text-2xl">Overview</CardTitle>
        <CardDescription>{view === 'balance' ? 'Total balance at the end of each day' : 'Income and expenses per month'}</CardDescription>
        <CardAction>
          <Segmented id="overview-view" label="Chart" value={view} onChange={setView}
            options={[{ value: 'flow', label: 'Cash flow' }, { value: 'balance', label: 'Balance' }, { value: 'table', label: 'Table' }]} />
        </CardAction>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-2 sm:grid-cols-3 sm:gap-3">
          {stats.map(([l, v, f, c]) => (
            <div key={l} className="flex min-w-0 items-center justify-between gap-2 rounded-2xl bg-muted/60 px-4 py-3 sm:block">
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground"><span className="size-2 rounded-full" style={{ background: c }} />{l}</div>
              <CountUp value={v} format={f} className="display mt-0.5 block truncate text-2xl lg:text-3xl" />
            </div>
          ))}
        </div>
        {top && view !== 'balance' && (
          <p className="text-sm text-muted-foreground">
            You spend <b className="num text-foreground">{baht(avgExp)}</b> a month on average; most in <b className="text-foreground">{monthLabel(top.m)}</b> (<span className="num">{baht(top.exp)}</span>).
            {' '}{short ? <>Expenses beat income in <b className="text-foreground">{short} of {s.months.length}</b> months.</> : 'Income covered expenses every month.'}
          </p>
        )}
        {view === 'flow' && (
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground" aria-hidden>
            <span className="flex items-center gap-1.5"><span className="h-0.5 w-5 rounded bg-income" />Income</span>
            <span className="flex items-center gap-1.5"><span className="h-0 w-5 border-t-2 border-dashed border-expense" />Expenses</span>
          </div>
        )}
        <AnimatePresence mode="wait" initial={false}>
          <motion.div key={view} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
            {view === 'flow' ? <FlowLines months={s.months} />
              : view === 'balance' ? <BalanceArea balance={s.balance} />
              : <MonthTable months={s.months} />}
          </motion.div>
        </AnimatePresence>
      </CardContent>
    </Card>
  )
}

// The chart's numbers as a plain table, newest month first.
function MonthTable({ months }: { months: Summary['months'] }) {
  return (
    <div className="max-h-80 overflow-auto rounded-2xl border">
      <Table>
        <TableHeader className="sticky top-0 z-10 bg-card">
          <TableRow className="text-xs text-muted-foreground">
            <TableHead>Month</TableHead><TableHead className="text-right">Income</TableHead>
            <TableHead className="text-right">Expenses</TableHead><TableHead className="text-right">Net</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {[...months].reverse().map((m) => (
            <TableRow key={m.m}>
              <TableCell>{monthLabel(m.m)}</TableCell>
              <TableCell className="num text-right">{baht(m.inc)}</TableCell>
              <TableCell className="num text-right">{baht(m.exp)}</TableCell>
              <TableCell className={cn('num text-right font-semibold', m.net >= 0 ? 'text-pos' : 'text-neg')}>{signed(m.net)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

const TICKS = 48
const dm = (d: string) => `${+d.slice(8)} ${monthLabel(d)}`

// This month's spending against the user's expected spending, drawn as a row of ticks that fill in one by one.
// No list yet: the card says so and links to the Expected Spending tab instead of inventing a target.
export function MonthSpend({ plan, onPlan }: { plan: PlanItem[]; onPlan: () => void }) {
  const keys = useMemo(() => new Set(plan.flatMap((i) => (i.key ? [i.key] : []))), [plan])
  const t = useMemo(() => thisMonth(keys), [keys])
  const expected = expectedFor(plan, t.days)
  // Expected by today: daily items for the days gone, monthly items prorated.
  // ponytail: prorates a monthly bill paid on day 1; track due dates if that early spike reads as "ahead"
  const dayGone = Math.round(t.elapsed * t.days)
  const dueNow = plan.reduce((a, i) => a + (i.every === 'day' ? i.amount * dayGone : i.amount * t.elapsed), 0)
  const ratio = expected ? t.spent / expected : 0
  const filled = Math.min(TICKS, Math.round(ratio * TICKS))
  const pace = Math.min(TICKS - 1, Math.round(t.elapsed * TICKS))
  const status = t.spent > expected ? 'Over expected' : t.spent > dueNow * 1.1 ? 'Ahead of plan' : 'On track'
  const bad = status !== 'On track'
  return (
    <Card data-od-id="month-spend" className="min-w-0">
      <CardHeader>
        <CardTitle className="flex items-center gap-1.5">Spent this month
          <InfoTip>Spending so far this month (cash withdrawals, lending and stock buys left out). The full bar is your expected spending: daily items × days in the month + monthly items, from the Expected Spending tab.</InfoTip>
        </CardTitle>
        <CardDescription>From {dm(t.from)} to {dm(t.end)} · excludes cash, lending &amp; stock</CardDescription>
        <CardAction><RoundLink label="Spend rate" to="spend-rate"><Gauge className="size-4" /></RoundLink></CardAction>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-baseline gap-x-2">
          <CountUp value={t.spent} format={baht} className="display text-3xl" />
          {expected > 0 && (
            <span className={cn('ml-auto rounded-full px-2.5 py-0.5 text-xs font-semibold', bad ? 'bg-neg/15 text-neg' : 'bg-pos/15 text-pos')}>{status}</span>
          )}
        </div>
        {!expected ? (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-dashed p-4">
            <p className="max-w-sm text-sm text-muted-foreground">Mark what you spend every day or every month, and this bar shows how far through it you are.</p>
            <button type="button" onClick={onPlan}
              className="rounded-full bg-brand px-4 py-2 text-sm font-medium text-white shadow-[0_8px_20px_-8px_var(--brand)] transition hover:brightness-110 active:scale-95">
              Set expected spending</button>
          </div>
        ) : <>
          <div className="relative flex h-9 items-end gap-[3px]" aria-label={`${Math.round(ratio * 100)}% of expected spending used`} role="img">
            {Array.from({ length: TICKS }, (_, i) => (
              <span key={i} className={cn('tick h-7 flex-1 rounded-full', i < filled ? (bad ? 'bg-neg' : 'bg-expense') : 'bg-muted', i === pace && 'h-9 ring-2 ring-foreground/30')}
                style={{ animationDelay: `${i * 16}ms` }} />
            ))}
          </div>
          <div className="flex flex-wrap justify-between gap-2 text-xs text-muted-foreground">
            <span>Used <b className="num text-foreground">{Math.round(ratio * 100)}%</b> of expected, <b className="num text-foreground">{Math.round(t.elapsed * 100)}%</b> of the month gone · outlined tick = today</span>
            <button type="button" onClick={onPlan} className="underline-offset-4 hover:text-foreground hover:underline">
              Expected spending <b className="num text-foreground">{baht(expected)}</b></button>
          </div>
          {keys.size > 0 && (
            <p className="text-xs text-muted-foreground">
              <b className="num text-foreground">{baht(t.planned)}</b> to payees on your list · <b className="num text-foreground">{baht(Math.max(0, t.spent - t.planned))}</b> everything else
            </p>
          )}
        </>}
      </CardContent>
    </Card>
  )
}

const CAT_ICON: Record<string, ReactNode> = {
  'Bill / purchase': <Receipt className="size-5" />, 'PromptPay out': <Smartphone className="size-5" />, 'Transfer out': <ArrowUpRight className="size-5" />,
}
// Named payees (your label, or a merchant from a payment email) get initials; bare account numbers get a category icon.
const face = (p: Payee) =>
  (p.name !== p.key && CAT_ICON[p.last.cat]) || p.name.replace(/[^\p{L}\p{N}]/gu, '').slice(0, 2).toUpperCase()

// Neutral faces: the colour budget stays on money (income / spending / good / bad), not on decoration.
export const PayeeAvatar = ({ p, size = 46 }: { p: Payee; size?: number }) => (
  <Avatar sx={{ width: size, height: size, fontSize: size / 3, fontWeight: 600, color: 'var(--foreground)', bgcolor: 'var(--muted)',
    border: '1px solid var(--border)', transition: 'transform .2s', '&:hover': { transform: 'scale(1.06)' } }}>{face(p)}</Avatar>
)

// Who you pay most often: pick a face to see the total, then jump to those payments (naming them is the Custom tab).
export function Payees({ rows, onShow }: { rows: Tx[]; onShow: (term: string) => void }) {
  const list = useMemo(() => payees(rows, 7), [rows])
  const [pick, setPick] = useState(0)
  const p = list[Math.min(pick, list.length - 1)]
  return (
    <Card data-od-id="payees" className="min-w-0">
      <CardHeader>
        <CardTitle className="flex items-center gap-1.5">Frequent payees
          <InfoTip>People and shops you pay most often, grouped by the account number in the bank description. Name them in the Custom Your Transaction tab.</InfoTip>
        </CardTitle>
        <CardDescription>Who you pay most often in this period</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {!p ? <p className="text-sm text-muted-foreground">No payments in this period.</p> : <>
          <div className="no-scrollbar -mx-1 flex gap-2.5 overflow-x-auto px-1 py-1">
            {list.map((x, i) => (
              <MuiTooltip key={x.key} title={x.name}>
                <button type="button" onClick={() => setPick(i)} aria-label={x.name} aria-pressed={x === p} className="relative shrink-0 rounded-full p-[3px]">
                  {x === p && <motion.span layoutId="payee-ring" className="absolute inset-0 rounded-full border-2 border-brand" transition={{ type: 'spring', stiffness: 400, damping: 30 }} />}
                  <PayeeAvatar p={x} />
                </button>
              </MuiTooltip>
            ))}
          </div>
          <AnimatePresence mode="wait" initial={false}>
            <motion.div key={p.key} initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -12 }} transition={{ duration: 0.22, ease: EASE }}
              className="flex flex-wrap items-end justify-between gap-3 border-t pt-4">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium" title={p.name}>{p.name}</p>
                <p className="num text-xs text-muted-foreground">{p.n} payment{p.n === 1 ? '' : 's'} · last {p.last.date.slice(0, 10)}</p>
                <p className="display mt-1 text-2xl">{baht(p.amt)}</p>
              </div>
              <div className="flex gap-2">
                <button type="button" onClick={() => { onShow(p.key); goTo('transactions') }}
                  className="inline-flex items-center gap-1.5 rounded-full bg-brand px-4 py-2 text-sm font-medium text-white shadow-[0_8px_20px_-8px_var(--brand)] transition hover:brightness-110 active:scale-95">
                  Show<ArrowRight className="size-4" /></button>
              </div>
            </motion.div>
          </AnimatePresence>
        </>}
      </CardContent>
    </Card>
  )
}

// The newest few rows of the period; click one for its details.
export function RecentTx({ rows }: { rows: Tx[] }) {
  const [open, setOpen] = useState<Tx | null>(null)
  const last = rows.slice(-6).reverse()
  return (
    <Card data-od-id="recent-tx" className="min-w-0">
      <CardHeader>
        <CardTitle>Recent transactions</CardTitle>
        <CardDescription>Newest in this period</CardDescription>
        <CardAction>
          <button type="button" onClick={() => goTo('transactions')} className="rounded-full border px-3.5 py-1.5 text-xs transition hover:bg-muted pointer-coarse:min-h-11">See all</button>
        </CardAction>
      </CardHeader>
      <CardContent>
        <ul className="divide-y">
          {last.map((r, i) => (
            <motion.li key={`${r.date}${r.amt}${r.desc}`} initial={{ opacity: 0, x: -10 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }}
              transition={{ delay: i * 0.06, duration: 0.4, ease: EASE }}>
              <button type="button" onClick={() => setOpen(r)}
                className="grid w-full grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 rounded-xl py-2.5 text-left transition-colors hover:bg-muted/60 sm:grid-cols-[auto_minmax(0,1fr)_auto_auto] sm:px-1">
                <span className={cn('grid size-9 place-items-center rounded-full', r.amt >= 0 ? 'bg-income/15 text-income' : 'bg-expense/15 text-expense')}>
                  {r.amt >= 0 ? <ArrowDownLeft className="size-4" /> : <ArrowUpRight className="size-4" />}
                </span>
                <span className="min-w-0">
                  <span className="block truncate text-sm font-medium" title={r.label ?? r.desc}>{r.label ?? descOf(r)}</span>
                  <span className="block truncate text-xs text-muted-foreground">{r.cat}</span>
                </span>
                <span className="num hidden text-xs text-muted-foreground sm:block">{r.date.slice(0, 10)}<br />{bankName(r.bank)}</span>
                <span className={cn('num text-right text-sm font-semibold', r.amt >= 0 ? 'text-pos' : 'text-neg')}>{signed(r.amt)}</span>
              </button>
            </motion.li>
          ))}
        </ul>
      </CardContent>
      <TxDrawer tx={open} onClose={() => setOpen(null)} />
    </Card>
  )
}

// Daily money out as bars over the last 7 / 30 / 90 days of records, money in and out totals on top.
export function MoneyMovement() {
  const [n, setN] = useState<'7' | '30' | '90'>('30')
  const days = useMemo(() => daily(+n), [n])
  const tin = days.reduce((a, d) => a + d.in, 0), tout = days.reduce((a, d) => a + d.out, 0)
  const avg = tout / days.length
  const busiest = days.reduce((m, d) => (d.out > m.out ? d : m), days[0])
  return (
    <Card data-od-id="money-movement" className="min-w-0">
      <CardHeader>
        <CardTitle className="flex items-center gap-1.5">Money movement
          <InfoTip>Each bar is one day's money out. The dashed line is your daily average for the range. Hover a bar to see that day.</InfoTip>
        </CardTitle>
        <CardDescription>Money out per day, up to {LAST}</CardDescription>
        <CardAction>
          <Segmented id="movement-range" label="Days" value={n} onChange={setN}
            options={[{ value: '7', label: '7d' }, { value: '30', label: '30d' }, { value: '90', label: '90d' }]} />
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-2">
        <div className="flex justify-between">
          <div>
            <div className="text-xs text-muted-foreground">Money in</div>
            <CountUp value={tin} format={baht} className="num text-base font-semibold text-pos" />
          </div>
          <div className="text-right">
            <div className="text-xs text-muted-foreground">Money out</div>
            <CountUp value={tout} format={baht} className="num text-base font-semibold text-neg" />
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          Average <b className="num text-foreground">{baht(avg)}</b>/day (dashed line) · busiest {dm(busiest.d)} <b className="num text-foreground">{baht(busiest.out)}</b>
        </p>
        <DailyBars days={days} avg={avg} />
      </CardContent>
    </Card>
  )
}
