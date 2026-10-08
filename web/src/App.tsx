import { useMemo, useState } from 'react'
import LinearProgress from '@mui/material/LinearProgress'
import { motion } from 'motion/react'
import { ArrowRight } from 'lucide-react'
import { CategoryCard } from '@/components/ledger/categories'
import { CustomTab } from '@/components/ledger/custom'
import { PlanTab } from '@/components/ledger/plan'
import { InfoTip } from '@/components/ledger/info'
import { Reveal } from '@/components/ledger/motion'
import { Predict } from '@/components/ledger/predict'
import { Nav, TopBar } from '@/components/ledger/shell'
import { goTo, useActiveSection, type Tab } from '@/lib/nav'
import { usePlan, type PlanItem } from '@/lib/plan'
import { useTheme } from '@/lib/themes'
import { Wizard } from '@/components/setup/wizard'
import { Index, SpendRate } from '@/components/ledger/spend-rate'
import { TxTable } from '@/components/ledger/tx-table'
import { MoneyMovement, MonthSpend, Overview, Payees, RecentTx, Segmented, WalletStack } from '@/components/ledger/widgets'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { LAST, META, TX, YEARS, bankName, baht, daysBetween, firstName, monthsBack, pctOf, rateTable, summarize, type Tx } from '@/lib/ledger'
import { EASE, cn } from '@/lib/utils'

function Recent() {
  const { months, total, usual } = useMemo(() => rateTable(monthsBack(4), LAST, false), [])
  return (
    <Card data-od-id="recent-months">
      <CardHeader className="pb-1">
        <CardTitle>Last 4 months</CardTitle>
        <CardDescription>
          {months[0].k} → {months[months.length - 1].k} · spending excludes cash, lending &amp; stock
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 gap-3 border-y py-3">
          <div>
            <div className="eyebrow">Spend / day</div>
            <div className="display mt-1 text-2xl">{baht(total.rate)}</div>
            <div className="text-xs text-muted-foreground">usual {usual == null ? '—' : baht(usual)}</div>
          </div>
          <div>
            <div className="eyebrow flex items-center gap-1">vs usual
              <InfoTip>This period's ฿/day ÷ your usual ฿/day (median of earlier months). Above 1× = spending faster than usual.</InfoTip>
            </div>
            <div className="display mt-1 text-2xl"><Index r={total.rate} usual={usual} /></div>
            <div className="text-xs text-muted-foreground">daily rate ÷ usual rate</div>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-x-3 gap-y-2">
          <div>
            <div className="eyebrow">Avg spend / month</div>
            <div className="num mt-1 text-sm font-medium">{baht(total.spend / months.length)}</div>
          </div>
          <div>
            <div className="eyebrow">Expense ÷ income</div>
            <div className="num mt-1 text-sm font-medium">{pctOf(total.out, total.inc)}</div>
          </div>
        </div>
        <div className="divide-y border-t">
          {months.map((r) => (
            <div key={r.k} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-2 gap-y-0.5 py-2">
              <span className="text-sm text-muted-foreground">{r.k}{r.partial && <small className="ml-1">· partial</small>}</span>
              <span className="num text-right text-sm">{baht(r.spend)} <small className="text-muted-foreground">spent</small></span>
              <LinearProgress variant="determinate" aria-label={`${r.k} daily spend rate`}
                value={Math.min(100, (r.rate / Math.max(...months.map((m) => m.rate), 1)) * 100)}
                sx={{ height: 4, borderRadius: 2, bgcolor: 'var(--muted)', gridColumn: '1 / -1', order: 3,
                  '& .MuiLinearProgress-bar': { borderRadius: 2, bgcolor: (usual && r.rate / usual > 1.15) ? 'var(--neg)' : 'var(--expense)' } }} />
              <span className="num col-span-2 whitespace-nowrap text-right text-xs sm:col-span-1" title="Daily rate · vs usual · out ÷ in">
                {baht(r.rate)}/day · <Index r={r.rate} usual={usual} /> · {pctOf(r.out, r.inc)}
              </span>
            </div>
          ))}
        </div>
        <Button variant="ghost" size="sm" className="w-full justify-between px-0" onClick={() => goTo('spend-rate')}>
          View spend rate <ArrowRight />
        </Button>
      </CardContent>
    </Card>
  )
}

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

function Ledger({ theme }: { theme: ReturnType<typeof useTheme> }) {
  const [tab, setTabState] = useState(hashTab)
  const [year, setYear] = useState('all')
  const [term, setTerm] = useState('')
  const [plan, setPlan] = usePlan()
  const rows = useMemo(() => (year === 'all' ? TX : TX.filter((r) => r.date.startsWith(year))), [year])
  const setTab = (t: Tab) => {
    if (t === tab) return
    location.replace(t === 'dashboard' ? '#' : `#${t}`)
    setTabState(t)
    scrollTo({ top: 0 })
  }

  return (
    <div className="relative min-h-svh overflow-x-clip">
      <div className="pointer-events-none absolute inset-x-0 top-16 h-[44rem] overflow-hidden" aria-hidden>
        <span className="glow top-16 left-1/4 size-96 bg-brand" />
        <span className="glow top-40 right-0 size-80 bg-expense [animation-delay:-7s]" />
      </div>
      <a href="#main" className="sr-only z-50 rounded-full bg-brand px-4 py-2 text-sm text-white focus:not-sr-only focus:fixed focus:top-3 focus:left-3">Skip to content</a>
      <TopBar rows={rows} year={year} tab={tab} onTab={setTab} theme={theme} />
      <main id="main" tabIndex={-1} className="relative mx-auto w-full max-w-[90rem] space-y-10 px-4 pb-28 sm:px-6 md:pb-14 md:pl-24 lg:pr-8">
        {tab === 'dashboard' ? <Dashboard rows={rows} year={year} setYear={setYear} term={term} setTerm={setTerm} plan={plan} onPlan={() => setTab('plan')} />
          : tab === 'plan' ? <PlanTab plan={plan} onPlan={setPlan} />
          : <CustomTab />}
        <p className="num pt-2 text-center text-xs text-muted-foreground">
          Built from Statement/ · {META.n} transactions · figures in Thai Baht (฿)
        </p>
      </main>
    </div>
  )
}

function Dashboard({ rows, year, setYear, term, setTerm, plan, onPlan }: {
  rows: Tx[]; year: string; setYear: (y: string) => void; term: string; setTerm: (t: string) => void; plan: PlanItem[]; onPlan: () => void
}) {
  const active = useActiveSection()
  const s = useMemo(() => summarize(rows), [rows])
  const range = s.n ? `${rows[0].date.slice(0, 10)} to ${rows[rows.length - 1].date.slice(0, 10)}` : 'no transactions'
  const fill = '[&>*]:h-full'

  return (
    <>
      <Nav active={active} />
      <Nav active={active} mobile />
      <section id="overview" className="scroll-mt-20 space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3 pt-4">
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, ease: EASE }}>
            <h1 className="text-3xl font-normal tracking-tight sm:text-4xl">{hello()}</h1>
            <p className="num mt-1 text-xs text-muted-foreground">
              {META.from.slice(0, 10)} → {META.to.slice(0, 10)} · showing {s.n} transactions over {s.months.length} months · {fresh()}
            </p>
          </motion.div>
          <motion.div data-od-id="scope-filter" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.08, ease: EASE }}>
            <Segmented id="year" big label="Filter by year" value={year} onChange={setYear}
              options={[{ value: 'all', label: 'All years' }, ...YEARS.map((y) => ({ value: y, label: y }))]} />
          </motion.div>
        </div>

        <Coverage />

        <div className="grid grid-cols-1 items-stretch gap-4 lg:grid-cols-[minmax(0,27rem)_minmax(0,1fr)] lg:min-h-[34rem]">
          <Reveal now className={fill}><WalletStack s={s} /></Reveal>
          <Reveal now className={cn(fill, 'min-w-0')} delay={0.08}><Overview s={s} /></Reveal>
        </div>
        <div className="grid grid-cols-1 items-stretch gap-4 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
          <Reveal className={fill} delay={0.12}><MonthSpend plan={plan} onPlan={onPlan} /></Reveal>
          <Reveal className={fill} delay={0.18}><Payees rows={rows} onShow={setTerm} /></Reveal>
        </div>
        <div className="grid grid-cols-1 items-stretch gap-4 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
          <Reveal className={fill}><RecentTx rows={rows} /></Reveal>
          <Reveal className={fill} delay={0.08}><MoneyMovement /></Reveal>
        </div>
      </section>

      <section id="categories" className="scroll-mt-20 space-y-4">
        <h2 className="text-2xl tracking-tight sm:text-3xl">Categories</h2>
        <div className="grid min-w-0 grid-cols-1 items-stretch gap-4 lg:grid-cols-2 xl:grid-cols-3" data-od-id="category-lists">
          <Reveal className={fill}><CategoryCard title="Where money went" caption="Expenses by category" list={s.ecat} color="var(--expense)" /></Reveal>
          <Reveal className={fill} delay={0.06}><CategoryCard title="Where money came from" caption="Income by category" list={s.icat} color="var(--income)" /></Reveal>
          <Reveal className={fill} delay={0.12}><Recent /></Reveal>
        </div>
      </section>

      <Reveal><SpendRate /></Reveal>
      <Reveal><Predict /></Reveal>
      <Reveal><TxTable rows={rows} caption={`${s.n} transactions · ${range}`} term={term} onTerm={setTerm} /></Reveal>
    </>
  )
}

function EmptyState() {
  const steps: [string, React.ReactNode][] = [
    ['Run setup', <>Run <code className="num">./run.sh</code>: a setup page opens in your browser and walks you through adding your statement PDFs.</>],
    ['Or by hand', <>Put the PDFs in <code className="num">Statement/</code> and run <code className="num">./run.sh</code>, or <code className="num">./gmail.sh</code> to fetch them from Gmail (see the README).</>],
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

// ./run.sh's setup server opens this page at /?setup: show the setup wizard instead of the dashboard.
const SETUP = new URLSearchParams(location.search).has('setup')

export default function App() {
  const theme = useTheme()
  if (SETUP) return <Wizard theme={theme} />
  return TX.length ? <Ledger theme={theme} /> : <EmptyState />
}
