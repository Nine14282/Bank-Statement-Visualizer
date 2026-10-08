import { useMemo, useState } from 'react'
import LinearProgress from '@mui/material/LinearProgress'
import MuiTooltip from '@mui/material/Tooltip'
import { useColorScheme } from '@mui/material/styles'
import { ArrowRight, ArrowRightLeft, CircleAlert, CircleCheck, Hourglass, LayoutDashboard, ListOrdered, Moon, Sun, TrendingUp } from 'lucide-react'
import { BalanceArea, MonthlyBars } from '@/components/ledger/charts'
import { CategoryCard } from '@/components/ledger/categories'
import { Kpi, KpiGrid } from '@/components/ledger/kpi'
import { Predict } from '@/components/ledger/predict'
import { Index, SpendRate } from '@/components/ledger/spend-rate'
import { TxTable } from '@/components/ledger/tx-table'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Sidebar, SidebarContent, SidebarFooter, SidebarGroup, SidebarGroupContent, SidebarGroupLabel, SidebarHeader,
  SidebarInset, SidebarMenu, SidebarMenuButton, SidebarMenuItem, SidebarProvider, SidebarTrigger,
} from '@/components/ui/sidebar'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { LAST, META, TX, YEARS, baht, monthsBack, pctOf, rateTable, signed, summarize } from '@/lib/ledger'

// sidebar items scroll to a section of the single page (no view switching)
const goTo = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })

function useDark() {
  const { mode, setMode } = useColorScheme()
  const dark = mode !== 'light'
  return [dark, () => setMode(dark ? 'light' : 'dark')] as const
}

function Flows({ s }: { s: ReturnType<typeof summarize> }) {
  const cards = [
    { h: 'Cash', f: s.cash, note: 'net converted to cash', out: 'Withdrawn to cash', in: 'Deposited from cash' },
    { h: 'Lending', f: s.lend, note: 'net settled this period', out: 'Lent out', in: 'Repaid to you' },
    { h: 'Investing (stocks)', f: s.stock, note: 'net placed into stocks', out: 'Invested', in: 'Returns received' },
  ]
  return (
    <div className="divide-y lg:grid lg:grid-cols-3 lg:divide-x lg:divide-y-0 xl:block xl:divide-x-0 xl:divide-y">
      {cards.map((c) => {
        const net = c.f.in - c.f.out
        return (
          <div key={c.h} className="py-3 first:pt-0 last:pb-0 lg:px-4 lg:py-0 lg:first:pl-0 lg:last:pr-0 xl:px-0 xl:py-3 xl:first:pt-0 xl:last:pb-0">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
              <div className="text-sm font-semibold">{c.h}</div>
              <div className={`display whitespace-nowrap text-2xl ${net >= 0 ? 'text-pos' : 'text-neg'}`}>{signed(net)}</div>
            </div>
            <div className="eyebrow mt-0.5 normal-case tracking-normal">{c.note}</div>
            {[[c.out, c.f.out, c.f.nOut, 'var(--expense)'], [c.in, c.f.in, c.f.nIn, 'var(--income)']].map(([l, v, n, col]) => (
              <div key={l as string} className="mt-2 flex items-center justify-between gap-3 text-sm">
                <span className="flex min-w-0 items-center gap-2 text-muted-foreground">
                  <span className="size-2 shrink-0 rounded-full" style={{ background: col as string }} />
                  <span className="truncate">{l as string}</span>
                </span>
                <span className="num shrink-0 font-semibold">{baht(v as number)}<small className="ml-1 font-normal text-muted-foreground">{n as number}×</small></span>
              </div>
            ))}
          </div>
        )
      })}
    </div>
  )
}

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
            <MuiTooltip title="This period's average ฿/day divided by your usual ฿/day (median of earlier months). Above 1× = spending faster than usual." arrow>
              <div className="eyebrow w-fit cursor-help underline decoration-dotted underline-offset-4">vs usual</div>
            </MuiTooltip>
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
                  '& .MuiLinearProgress-bar': { borderRadius: 2, bgcolor: (usual && r.rate / usual > 1.15) ? 'var(--expense)' : 'var(--income)' } }} />
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
    <Card id="coverage" className="ring-neg">
      <CardHeader>
        <CardTitle className="text-neg">Data may be missing</CardTitle>
        <CardDescription>A statement is probably missing — totals below won't include it</CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="list-disc space-y-1 pl-5 text-sm">
          {g.months.length > 0 && <li><b>No records at all:</b> {g.months.join(', ')}</li>}
          {g.breaks.map((b) => (
            <li key={b.after + b.before}>
              <b>{b.after.slice(0, 10)} → {b.before.slice(0, 10)}:</b> balance moved{' '}
              <span className="num">{b.missing > 0 ? '+' : '−'}{baht(b.missing)}</span> with no matching transactions
              ({b.missing > 0 ? 'money in' : 'money out'} not in the ledger)
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}

function Dashboard() {
  const [year, setYear] = useState('all')
  const [dark, toggleDark] = useDark()

  const rows = useMemo(() => (year === 'all' ? TX : TX.filter((r) => r.date.startsWith(year))), [year])
  const s = useMemo(() => summarize(rows), [rows])
  const gaps = META.gaps.months.length + META.gaps.breaks.length
  const range = s.n ? `${rows[0].date.slice(0, 10)} to ${rows[rows.length - 1].date.slice(0, 10)}` : 'no transactions'


  return (
    <SidebarProvider>
      <Sidebar data-od-id="sidebar">
        <SidebarHeader className="gap-3 p-4">
          <div className="flex items-center gap-3 font-serif text-lg leading-tight">
            <span className="grid size-9 place-items-center rounded-xl bg-foreground text-lg text-background">฿</span>
            Income &amp; Expense<br />Ledger
          </div>
          {(META.account || META.name) && (
            <div className="num rounded-lg border bg-muted/40 p-2.5 text-[11.5px] leading-relaxed text-muted-foreground [overflow-wrap:anywhere]">
              {[META.account, META.name].filter(Boolean).join(' · ')}
            </div>
          )}
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupLabel>Views</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                <SidebarMenuItem>
                  <SidebarMenuButton onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}><LayoutDashboard />Overview</SidebarMenuButton>
                </SidebarMenuItem>
                <SidebarMenuItem>
                  <SidebarMenuButton onClick={() => goTo('spend-rate')}><TrendingUp />Spend rate</SidebarMenuButton>
                </SidebarMenuItem>
                <SidebarMenuItem>
                  <SidebarMenuButton onClick={() => goTo('predict')}><Hourglass />Predict</SidebarMenuButton>
                </SidebarMenuItem>
                <SidebarMenuItem>
                  <SidebarMenuButton onClick={() => goTo('transactions')}><ListOrdered />Transactions</SidebarMenuButton>
                </SidebarMenuItem>
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
        <SidebarFooter className="gap-2 p-4">
          <a href="#coverage" data-od-id="coverage-status"
            className={`flex items-start gap-2 rounded-lg border p-2.5 text-xs ${gaps ? 'border-neg text-neg' : 'text-pos'}`}>
            {gaps ? <CircleAlert className="mt-0.5 size-4 shrink-0" /> : <CircleCheck className="mt-0.5 size-4 shrink-0" />}
            {gaps ? `Data may be missing (${gaps} issue${gaps > 1 ? 's' : ''})` : 'Coverage OK — no gaps'}
          </a>
          <Button variant="outline" size="sm" onClick={toggleDark} aria-label="Toggle light or dark theme">
            {dark ? <Sun /> : <Moon />}{dark ? 'Light' : 'Dark'} mode
          </Button>
        </SidebarFooter>
      </Sidebar>

      <SidebarInset className="min-w-0">
        <header className="mx-auto flex w-full max-w-7xl items-center gap-3 px-4 pt-5 pb-3 sm:px-6 sm:pt-6 lg:px-8" data-od-id="topbar">
          <SidebarTrigger className="md:hidden" />
          <div className="min-w-0">
            <p className="eyebrow">Statement period</p>
            <h1 className="display text-3xl sm:text-4xl">{META.from.slice(0, 10)} → {META.to.slice(0, 10)}</h1>
          </div>
        </header>

        <main className="mx-auto w-full max-w-7xl space-y-5 px-4 pb-14 sm:space-y-7 sm:px-6 lg:px-8">
          <>
              <div data-od-id="scope-filter"
                className="sticky top-0 z-20 -mx-4 flex flex-wrap items-center gap-x-3 gap-y-2 border-y bg-background/95 px-4 py-2.5 backdrop-blur sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
                <span className="eyebrow">Year</span>
                <ToggleGroup className="max-w-full flex-wrap" variant="outline" value={[year]} onValueChange={(v) => v[0] && setYear(v[0])} aria-label="Filter by year">
                  <ToggleGroupItem value="all">All years</ToggleGroupItem>
                  {YEARS.map((y) => <ToggleGroupItem key={y} value={y}>{y}</ToggleGroupItem>)}
                </ToggleGroup>
                <span className="num text-xs text-muted-foreground">
                  {year === 'all' ? `All ${YEARS.length} years` : year} · {s.n} transactions · {s.months.length} months
                </span>
              </div>

              <Coverage />

              <div className="grid items-start gap-4 xl:grid-cols-[1.2fr_0.9fr]">
                <div className="grid min-w-0 gap-4">
                  <Card data-od-id="kpis">
                    <CardHeader className="pb-0">
                      <CardTitle>Account summary</CardTitle>
                      <CardDescription>Income and expenses reconcile to the closing balance.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <KpiGrid className="grid-cols-1 gap-x-8 gap-y-4 overflow-visible rounded-none border-0 bg-transparent sm:grid-cols-2 lg:grid-cols-2">
                        <Kpi label="Net change" value={signed(s.net)} sub="income − expenses"
                          dot={s.net >= 0 ? 'var(--pos)' : 'var(--neg)'}
                          valueClass={`text-4xl sm:text-5xl ${s.net >= 0 ? 'text-pos' : 'text-neg'}`}
                          className="space-y-1.5 bg-transparent p-0 md:p-0" />
                        <Kpi label="Closing balance" value={baht(s.close)} sub={s.closeAt ? `bank balance ${s.closeAt} + later payment emails` : undefined}
                          className="space-y-1.5 bg-transparent p-0 md:p-0" valueClass="text-4xl sm:text-5xl" />
                      </KpiGrid>
                      <div className="grid grid-cols-2 gap-x-4 gap-y-3 border-t pt-3 sm:grid-cols-3">
                        <div>
                          <div className="eyebrow">Opening balance</div>
                          <div className="num mt-1 text-sm font-medium">{baht(s.open)}</div>
                        </div>
                        <div>
                          <div className="eyebrow flex items-center gap-1.5"><span className="size-1.5 rounded-full" style={{ background: 'var(--income)' }} />Income · {s.nIn} deposits</div>
                          <div className="num mt-1 text-sm font-medium">{baht(s.inc)}</div>
                        </div>
                        <div>
                          <div className="eyebrow flex items-center gap-1.5"><span className="size-1.5 rounded-full" style={{ background: 'var(--expense)' }} />Expenses · {s.nOut} payments</div>
                          <div className="num mt-1 text-sm font-medium">{baht(s.exp)}</div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                  <Card data-od-id="money-flows">
                    <CardHeader className="pb-1">
                      <CardTitle className="flex items-center gap-2"><ArrowRightLeft className="size-4" />Personal money flows</CardTitle>
                      <CardDescription>Cash, lending and investing are tracked apart from spending.</CardDescription>
                    </CardHeader>
                    <CardContent><Flows s={s} /></CardContent>
                  </Card>
                </div>
                <Recent />
              </div>

              <section className="space-y-3 pt-1">
                <h2 className="display text-2xl sm:text-3xl">Monthly activity and balance</h2>
                <div className="grid min-w-0 gap-4 xl:grid-cols-[1.2fr_1fr]">
                  <Card className="min-w-0" data-od-id="chart-monthly">
                    <CardHeader className="pb-0"><CardTitle>Monthly income vs. expense</CardTitle><CardDescription>Baht per calendar month</CardDescription></CardHeader>
                    <CardContent className="pt-2"><MonthlyBars months={s.months} /></CardContent>
                  </Card>
                  <Card className="min-w-0" data-od-id="chart-balance">
                    <CardHeader className="pb-0"><CardTitle>Account balance over time</CardTitle><CardDescription>Closing balance after every transaction</CardDescription></CardHeader>
                    <CardContent className="pt-2"><BalanceArea balance={s.balance} /></CardContent>
                  </Card>
                </div>
              </section>

              <section className="space-y-3 pt-1">
                <h2 className="display text-2xl sm:text-3xl">Categories</h2>
                <div className="grid min-w-0 gap-4 xl:grid-cols-2" data-od-id="category-lists">
                  <CategoryCard title="Where money went" caption="Expenses by category" list={s.ecat} color="var(--expense)" />
                  <CategoryCard title="Where money came from" caption="Income by category" list={s.icat} color="var(--income)" />
                </div>
              </section>

              <SpendRate />

              <Predict />

              <TxTable rows={rows} caption={`${s.n} transactions · ${range}`} />
          </>
          <p className="num pt-4 text-center text-xs text-muted-foreground">
            Built from Statement/ · {META.n} transactions · figures in Thai Baht (฿)
          </p>
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}

function EmptyState() {
  const steps: [string, React.ReactNode][] = [
    ['Add statements', <>Put your statement PDFs in <code className="num">Statement/</code>, or set up Gmail (see the README).</>],
    ['Build', <>Run <code className="num">./run.sh</code> to build from the PDFs, or <code className="num">./gmail.sh</code> to fetch them from Gmail first.</>],
    ['Reload this page', 'Your income, expenses, balance and spend rate appear here.'],
  ]
  return (
    <main className="grid min-h-svh place-items-center px-6 py-16" data-od-id="empty-state">
      <div className="w-full max-w-lg space-y-8">
        <div className="space-y-3">
          <p className="eyebrow">Income &amp; Expense Ledger</p>
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

export default function App() {
  return TX.length ? <Dashboard /> : <EmptyState />
}
