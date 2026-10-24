import { memo, useCallback, useEffect, useMemo, useState } from 'react'
import { motion } from 'motion/react'
import { CategoryCard } from '@/components/ledger/categories'
import { CustomTab } from '@/components/ledger/custom'
import { PlanTab } from '@/components/ledger/plan'
import { Reveal } from '@/components/ledger/motion'
import { Predict } from '@/components/ledger/predict'
import { Nav, TopBar } from '@/components/ledger/shell'
import { useActiveSection, useAfterPaint, type Tab } from '@/lib/nav'
import { usePlan, type PlanItem } from '@/lib/plan'
import { useTheme } from '@/lib/themes'
import { Wizard } from '@/components/setup/wizard'
import { SpendRate } from '@/components/ledger/spend-rate'
import { TxTable } from '@/components/ledger/tx-table'
import { MoneyMovement, MonthSpend, Overview, Payees, RecentTx, Segmented, WalletStack } from '@/components/ledger/widgets'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { LAST, META, TX, YEARS, bankName, baht, daysBetween, firstName, summarize, useLedger, type Tx } from '@/lib/ledger'
import { EASE, HOSTED, OPEN_APP, cn } from '@/lib/utils'

function Coverage() {
  const g = META.gaps
  if (!g.months.length && !g.breaks.length) return null
  return (
    <Card id="coverage" className="scroll-mt-20 ring-neg">
      <CardHeader>
        <CardTitle className="text-neg">Data may be missing</CardTitle>
        <CardDescription>A statement is probably missing — totals below won't include it</CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="list-disc space-y-1 pl-5 text-sm">
          {g.months.length > 0 && <li><b>No records at all:</b> {g.months.join(', ')}</li>}
          {g.breaks.map((b) => (
            <li key={b.after + b.before}>
              <b>{b.bank && `${bankName(b.bank)} `}{b.after.slice(0, 10)} → {b.before.slice(0, 10)}:</b> balance moved{' '}
              <span className="num">{b.missing > 0 ? '+' : '−'}{baht(b.missing)}</span> with no matching transactions
              ({b.missing > 0 ? 'money in' : 'money out'} not in the ledger)
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}

// How current the data is, so a stale statement is noticed before its numbers are trusted.
const fresh = () => {
  const d = daysBetween(LAST, new Date().toLocaleDateString('en-CA'))
  return d <= 0 ? 'updated today' : `last record ${d} day${d === 1 ? '' : 's'} ago`
}

// Time-of-day greeting with the account holder's first name (from the settings), like a banking app home screen.
const hello = () => {
  const h = new Date().getHours()
  const part = h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'
  return firstName ? `${part}, ${firstName}!` : `${part}!`
}

// The tab sits in the URL hash, so the reload after saving a label (saveRules) lands back on the same tab.
const hashTab = (): Tab => (location.hash === '#custom' ? 'custom' : location.hash === '#plan' ? 'plan' : 'dashboard')

function Ledger({ theme, onAdd, onSettings, inert }: {
  theme: ReturnType<typeof useTheme>; onAdd?: () => void; onSettings?: () => void; inert?: boolean
}) {
  const [tab, setTabState] = useState(hashTab)
  const [year, setYear] = useState('all')
  const [term, setTerm] = useState('')
  const [plan, setPlan] = usePlan()
  const tx = useLedger()   // a rebuild swaps the data in place (main.tsx): no reload, scroll and state kept
  const rows = useMemo(() => (year === 'all' ? tx : tx.filter((r) => r.date.startsWith(year))), [year, tx])
  const [seen, setSeen] = useState(() => new Set([tab]))
  // Stable (reads the tab from the hash), so the memoised Dashboard doesn't re-render on a tab change.
  const setTab = useCallback((t: Tab) => {
    if (t === hashTab()) return
    location.replace(t === 'dashboard' ? '#' : `#${t}`)
    setTabState(t)
    setSeen((s) => (s.has(t) ? s : new Set(s).add(t)))
    scrollTo({ top: 0 })
  }, [])
  // A tab mounts on its first visit and then stays mounted. A tab not shown is skipped with content-visibility: the
  // browser keeps its layout and React keeps its state and effects, so switching back redraws no chart and replays no
  // fade-in. (React's <Activity> was tried: it re-runs effects on show, and Recharts re-renders every chart then.)
  // my-0 cancels main's space-y gap for the hidden ones.
  const pane = (t: Tab) => cn('space-y-10', t !== tab && '[content-visibility:hidden] my-0')

  return (
    <div className="relative min-h-svh overflow-x-clip" inert={inert}>
      <div className="pointer-events-none absolute inset-x-0 top-16 h-[44rem] overflow-hidden" aria-hidden>
        <span className="glow top-16 left-1/4 size-96 bg-brand" />
        <span className="glow top-40 right-0 size-80 bg-expense [animation-delay:-7s]" />
      </div>
      <a href="#main" className="sr-only z-50 rounded-full bg-brand px-4 py-2 text-sm text-white focus:not-sr-only focus:fixed focus:top-3 focus:left-3">Skip to content</a>
      <TopBar rows={rows} year={year} tab={tab} onTab={setTab} theme={theme} onAdd={onAdd} onSettings={onSettings} />
      <main id="main" tabIndex={-1} className="relative mx-auto w-full max-w-[90rem] space-y-10 px-4 pb-28 sm:px-6 md:pb-14 md:pl-24 lg:pr-8">
        {seen.has('dashboard') && <div className={pane('dashboard')}>
          <DashboardPage rows={rows} year={year} setYear={setYear} term={term} setTerm={setTerm} plan={plan} onTab={setTab} />
        </div>}
        {seen.has('plan') && <div className={pane('plan')}><PlanTab plan={plan} onPlan={setPlan} /></div>}
        {seen.has('custom') && <div className={pane('custom')}><CustomTab /></div>}
        <p className="num pt-2 text-center text-xs text-muted-foreground">
          Built from Statement/ · {META.n} transactions · figures in Thai Baht (฿)
        </p>
      </main>
    </div>
  )
}

// The scroll-spy state lives here, so entering a new section re-renders the two nav rails, not every card and chart.
function Navs({ mounted }: { mounted: boolean }) {
  const active = useActiveSection(mounted)
  return <><Nav active={active} /><Nav active={active} mobile /></>
}

// Cards whose props don't change while you type in the search box or move between sections: memo skips their charts.
const OverviewCard = memo(Overview)
const WalletCard = memo(WalletStack)
const MoneyCard = memo(MoneyMovement)
const CategoryList = memo(CategoryCard)
const SpendRateCard = memo(SpendRate)
const PredictCard = memo(Predict)
const DashboardPage = memo(Dashboard)

function Dashboard({ rows, year, setYear, term, setTerm, plan, onTab }: {
  rows: Tx[]; year: string; setYear: (y: string) => void; term: string; setTerm: (t: string) => void; plan: PlanItem[]; onTab: (t: Tab) => void
}) {
  const onPlan = useCallback(() => onTab('plan'), [onTab])
  // The first paint is the top of the page (greeting, wallet, overview); the rest mounts right after it. Styling the
  // whole page up front kept the window blank for ~2 s in WebKitGTK.
  const later = useAfterPaint()
  const s = useMemo(() => summarize(rows), [rows])
  const range = s.n ? `${rows[0].date.slice(0, 10)} to ${rows[rows.length - 1].date.slice(0, 10)}` : 'no transactions'
  const fill = '[&>*]:h-full'

  return (
    <>
      <Navs mounted={later} />
      <section id="overview" className="scroll-mt-20 space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3 pt-4">
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, ease: EASE }}>
            <h1 className="text-3xl font-normal tracking-tight sm:text-4xl">{hello()}</h1>
            <p className="num mt-1 text-xs text-muted-foreground">
              {META.from.slice(0, 10)} → {META.to.slice(0, 10)} · showing {s.n} transactions over {s.months.length} months · {fresh()}
            </p>
          </motion.div>
          <motion.div data-od-id="scope-filter" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.08, ease: EASE }}>
            <Segmented big label="Filter by year" value={year} onChange={setYear}
              options={[{ value: 'all', label: 'All years' }, ...YEARS.map((y) => ({ value: y, label: y }))]} />
          </motion.div>
        </div>

        <Coverage />

        <div className="grid grid-cols-1 items-stretch gap-4 lg:grid-cols-[minmax(0,27rem)_minmax(0,1fr)] lg:min-h-[34rem]">
          <Reveal now className={fill}><WalletCard s={s} /></Reveal>
          <Reveal now className={cn(fill, 'min-w-0')} delay={0.08}><OverviewCard s={s} /></Reveal>
        </div>
        {later && <>
          <div className="grid grid-cols-1 items-stretch gap-4 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
            <Reveal className={fill} delay={0.12}><MonthSpend plan={plan} onPlan={onPlan} /></Reveal>
            <Reveal className={fill} delay={0.18}><Payees rows={rows} onShow={setTerm} /></Reveal>
          </div>
          <div className="grid grid-cols-1 items-stretch gap-4 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
            <Reveal className={fill}><RecentTx rows={rows} /></Reveal>
            <Reveal className={fill} delay={0.08}><MoneyCard /></Reveal>
          </div>
        </>}
      </section>

      {later && <>
        <section id="categories" className="scroll-mt-20 space-y-4">
          <h2 className="text-2xl tracking-tight sm:text-3xl">Categories</h2>
          <div className="grid min-w-0 grid-cols-1 items-stretch gap-4 lg:grid-cols-2" data-od-id="category-lists">
            <Reveal className={fill}><CategoryList title="Where money went" caption="Expenses by category" list={s.ecat} color="var(--expense)" /></Reveal>
            <Reveal className={fill} delay={0.06}><CategoryList title="Where money came from" caption="Income by category" list={s.icat} color="var(--income)" /></Reveal>
          </div>
        </section>

        <Reveal><SpendRateCard /></Reveal>
        <Reveal><PredictCard /></Reveal>
        <Reveal><TxTable rows={rows} caption={`${s.n} transactions · ${range}`} term={term} onTerm={setTerm} /></Reveal>
      </>}
    </>
  )
}

function EmptyState() {
  const steps: [string, React.ReactNode][] = [
    ['Open the app', OPEN_APP],
    ['Add your statements', 'It walks you through adding your statement PDFs and their passwords.'],
    ['Reload this page', 'Your income, expenses, balance and spend rate appear here.'],
  ]
  return (
    <main className="grid min-h-svh place-items-center px-6 py-16" data-od-id="empty-state">
      <div className="w-full max-w-lg space-y-8">
        <div className="space-y-3">
          <p className="eyebrow">Statement Visualizer</p>
          <h1 className="display text-4xl sm:text-5xl">No data yet</h1>
          <p className="text-sm text-muted-foreground">Nothing has been imported, so there is nothing to show. Three steps:</p>
        </div>
        <ol className="divide-y rounded-xl border bg-card">
          {steps.map(([title, body], i) => (
            <li key={title} className="flex gap-4 p-4">
              <span className="pill h-fit">{i + 1}</span>
              <div className="space-y-1">
                <div className="font-medium">{title}</div>
                <p className="text-sm text-muted-foreground">{body}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </main>
  )
}

// welcome.py --setup opens this page at /?setup: the setup wizard alone, instead of the dashboard.
const SETUP = new URLSearchParams(location.search).has('setup')

export default function App() {
  useLedger()   // re-render on a data swap: the empty state turns into the dashboard, and back
  const theme = useTheme()
  // App window: Add statements (and Settings: the full setup) open over the dashboard, in this same page (no page load,
  // no transition). The dashboard stays underneath, inert, scroll position kept.
  const [panel, setPanel] = useState<'add' | 'setup' | null>(null)
  useEffect(() => {
    if (!panel) return
    document.documentElement.style.overflow = 'hidden'   // the page underneath doesn't scroll meanwhile
    return () => { document.documentElement.style.overflow = '' }
  }, [panel])

  if (SETUP) return <Wizard />
  // No data yet: the app (window or ?web) runs the first-time setup itself; a page opened from disk can only say to
  // open the app.
  if (!TX.length) return HOSTED ? <Wizard mode="setup" /> : <EmptyState />
  return (
    <>
      <Ledger theme={theme} inert={!!panel}
        onAdd={HOSTED ? () => setPanel('add') : undefined} onSettings={HOSTED ? () => setPanel('setup') : undefined} />
      {/* closed without an update of its own: catch up on any the listener pushed meanwhile (main.tsx); after the
          panel has left the page, which the update checks for */}
      {panel && <Wizard mode={panel} onClose={() => { setPanel(null); setTimeout(() => (window as { __ledgerUpdate?: () => void }).__ledgerUpdate?.()) }} />}
    </>
  )
}
