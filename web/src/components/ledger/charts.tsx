import { Area, AreaChart, Bar, BarChart, CartesianGrid, XAxis, YAxis } from 'recharts'
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from '@/components/ui/chart'
import { baht, monthLabel, type Summary } from '@/lib/ledger'

const barConfig = {
  inc: { label: 'Income', color: 'var(--income)' },
  exp: { label: 'Expense', color: 'var(--expense)' },
} satisfies ChartConfig

const lineConfig = { b: { label: 'Balance', color: 'var(--income)' } } satisfies ChartConfig

const k = (v: number) => `${v / 1000}k`
const tick = { fontFamily: 'var(--font-mono)', fontSize: 11 }

export function MonthlyBars({ months }: { months: Summary['months'] }) {
  return (
    <ChartContainer config={barConfig} className="h-72 w-full">
      <BarChart data={months} margin={{ left: 0, right: 8 }}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="m" tick={tick} tickFormatter={monthLabel} tickLine={false} axisLine={false} interval="preserveStartEnd" />
        <YAxis tick={tick} tickFormatter={k} tickLine={false} axisLine={false} width={44} />
        <ChartTooltip
          content={<ChartTooltipContent labelFormatter={(_, p) => monthLabel(p[0].payload.m)}
            formatter={(v, name) => (
              <div className="flex w-full justify-between gap-4">
                <span className="text-muted-foreground">{barConfig[name as 'inc' | 'exp']?.label}</span>
                <span className="num font-medium">{baht(Number(v))}</span>
              </div>
            )} />}
        />
        <Bar dataKey="inc" fill="var(--color-inc)" radius={[2, 2, 0, 0]} barSize={7} />
        <Bar dataKey="exp" fill="var(--color-exp)" radius={[2, 2, 0, 0]} barSize={7} />
      </BarChart>
    </ChartContainer>
  )
}

export function BalanceArea({ balance }: { balance: Summary['balance'] }) {
  const top = Math.max(1000, Math.ceil(Math.max(...balance.map((p) => p.b), 0) / 1000) * 1000)
  // one tick per month start inside the data range, thinned to ~8 labels
  const t0 = balance[0]?.t ?? 0, t1 = balance[balance.length - 1]?.t ?? 0
  const starts: number[] = []
  for (let d = new Date(t0); d.setMonth(d.getMonth() + 1, 1), d.setHours(0, 0, 0, 0), d.getTime() <= t1;) starts.push(d.getTime())
  const ticks = starts.filter((_, i) => i % Math.ceil(starts.length / 8) === 0)
  return (
    <ChartContainer config={lineConfig} className="h-64 w-full">
      <AreaChart data={balance} margin={{ left: 0, right: 20 }}>
        <defs>
          <linearGradient id="balfill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--color-b)" stopOpacity={0.3} />
            <stop offset="100%" stopColor="var(--color-b)" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="t" tick={tick} type="number" scale="time" domain={['dataMin', 'dataMax']} tickLine={false} axisLine={false}
          ticks={ticks} tickFormatter={(t) => { const d = new Date(t); return monthLabel(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`) }} />
        <YAxis tick={tick} domain={[0, top]} tickFormatter={k} tickLine={false} axisLine={false} width={44} />
        <ChartTooltip
          content={<ChartTooltipContent hideIndicator labelFormatter={(_, p) => String(p[0].payload.date).slice(0, 16)}
            formatter={(v) => (
              <div className="flex w-full justify-between gap-4">
                <span className="text-muted-foreground">Balance</span>
                <span className="num font-medium">{baht(Number(v))}</span>
              </div>
            )} />}
        />
        <Area dataKey="b" type="linear" stroke="var(--color-b)" strokeWidth={1.5} fill="url(#balfill)" dot={false} isAnimationActive={false} />
      </AreaChart>
    </ChartContainer>
  )
}
