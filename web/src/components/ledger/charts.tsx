import { useMemo, useState } from 'react'
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, LabelList, ReferenceLine, XAxis, YAxis, type TooltipContentProps } from 'recharts'
import { ChartContainer, ChartTooltip, type ChartConfig } from '@/components/ui/chart'
import { baht, daily, monthLabel, type Summary } from '@/lib/ledger'
import { useStill } from '@/lib/utils'

const flowConfig = {
  inc: { label: 'Income', color: 'var(--income)' },
  exp: { label: 'Expense', color: 'var(--expense)' },
} satisfies ChartConfig

const lineConfig = { b: { label: 'Balance', color: 'var(--income)' } } satisfies ChartConfig
const barsConfig = { out: { label: 'Money out', color: 'var(--expense)' } } satisfies ChartConfig

// Axis money: ฿0, ฿500, ฿5.5k, ฿22k
const k = (v: number) => (Math.abs(v) >= 1000 ? `฿${+(v / 1000).toFixed(1)}k` : `฿${v}`)
const SPEED = 600  // chart draw-in, ms; off entirely under reduced motion
const tick = { fontFamily: 'var(--font-mono)', fontSize: 11 }
const day = (d: string) => `${+d.slice(8)} ${monthLabel(d).split(' ')[0]}`
const tipBox = 'rounded-2xl border bg-popover/95 px-3.5 py-2.5 text-popover-foreground shadow-xl backdrop-blur'
type TipProps = Pick<TooltipContentProps<number, string>, 'active' | 'payload'>

function FlowTip({ active, payload }: TipProps) {
  if (!active || !payload?.length) return null
  const m = payload[0].payload as Summary['months'][number]
  return (
    <div className={tipBox}>
      <p className="eyebrow mb-1.5">{monthLabel(m.m)}</p>
      <div className="flex gap-5">
        {([['Income', m.inc, 'var(--income)'], ['Expense', m.exp, 'var(--expense)']] as const).map(([l, v, c]) => (
          <div key={l}>
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground"><span className="size-2 rounded-full" style={{ background: c }} />{l}</div>
            <div className="num text-sm font-semibold">{baht(v)}</div>
          </div>
        ))}
      </div>
      <p className={`num mt-1.5 border-t pt-1.5 text-xs ${m.net >= 0 ? 'text-pos' : 'text-neg'}`}>net {m.net >= 0 ? '+' : '−'}{baht(m.net)}</p>
    </div>
  )
}

// Smooth income / expense curves per month, soft gradient underneath (the "Overview" chart).
export function FlowLines({ months }: { months: Summary['months'] }) {
  const still = useStill()
  return (
    <ChartContainer config={flowConfig} className="aspect-auto h-72 w-full lg:h-80" role="img"
      aria-label={`Monthly income (solid line) and expenses (dashed line), ${months.length} months from ${months[0] ? monthLabel(months[0].m) : '—'}`}>
      <AreaChart data={months} margin={{ left: 0, right: 8, top: 8 }}>
        <defs>
          {(['inc', 'exp'] as const).map((s) => (
            <linearGradient key={s} id={`fill-${s}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={`var(--color-${s})`} stopOpacity={0.28} />
              <stop offset="100%" stopColor={`var(--color-${s})`} stopOpacity={0} />
            </linearGradient>
          ))}
        </defs>
        <CartesianGrid vertical={false} strokeDasharray="3 6" />
        <XAxis dataKey="m" tick={tick} tickFormatter={monthLabel} tickLine={false} axisLine={false} interval="preserveStartEnd" minTickGap={18}
          padding={{ left: 10, right: 24 }} />
        <YAxis tick={tick} tickFormatter={k} tickLine={false} axisLine={false} width={54} />
        <ChartTooltip content={FlowTip} cursor={{ stroke: 'var(--muted-foreground)', strokeDasharray: '4 4' }} />
        {(['inc', 'exp'] as const).map((s) => (
          <Area key={s} dataKey={s} type="monotone" stroke={`var(--color-${s})`} strokeWidth={2.5} strokeDasharray={s === 'exp' ? '7 5' : undefined} fill={`url(#fill-${s})`}
            activeDot={{ r: 6, strokeWidth: 3, stroke: 'var(--card)' }} isAnimationActive={!still} animationDuration={SPEED} animationEasing="ease-out" />
        ))}
      </AreaChart>
    </ChartContainer>
  )
}

function BalanceTip({ active, payload }: TipProps) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload as Summary['balance'][number]
  return (
    <div className={tipBox}>
      <p className="eyebrow mb-1">{p.date.slice(0, 16)}</p>
      <p className="num text-sm font-semibold">{baht(p.b)}</p>
    </div>
  )
}

export function BalanceArea({ balance: all }: { balance: Summary['balance'] }) {
  const still = useStill()
  // one point per day (that day's last balance): same line, a fraction of the SVG nodes and hover targets
  const balance = useMemo(() => [...new Map(all.map((p) => [p.date.slice(0, 10), p])).values()], [all])
  const top = Math.max(1000, Math.ceil(Math.max(...balance.map((p) => p.b), 0) / 1000) * 1000)
  // one tick per month start inside the data range, thinned to ~8 labels
  const t0 = balance[0]?.t ?? 0, t1 = balance[balance.length - 1]?.t ?? 0
  const starts: number[] = []
  for (let d = new Date(t0); d.setMonth(d.getMonth() + 1, 1), d.setHours(0, 0, 0, 0), d.getTime() <= t1;) starts.push(d.getTime())
  const ticks = starts.filter((_, i) => i % Math.ceil(starts.length / 8) === 0)
  return (
    <ChartContainer config={lineConfig} className="aspect-auto h-72 w-full lg:h-80" role="img"
      aria-label={`Account balance per day, ${balance.length} days, ending at ${baht(balance[balance.length - 1]?.b ?? 0)}`}>
      <AreaChart data={balance} margin={{ left: 0, right: 24, top: 8 }}>
        <defs>
          <linearGradient id="balfill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--color-b)" stopOpacity={0.3} />
            <stop offset="100%" stopColor="var(--color-b)" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid vertical={false} strokeDasharray="3 6" />
        <XAxis dataKey="t" tick={tick} type="number" scale="time" domain={['dataMin', 'dataMax']} tickLine={false} axisLine={false}
          ticks={ticks} tickFormatter={(t) => { const d = new Date(t); return monthLabel(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`) }} />
        <YAxis tick={tick} domain={[0, top]} tickFormatter={k} tickLine={false} axisLine={false} width={54} />
        <ChartTooltip content={BalanceTip} cursor={{ stroke: 'var(--muted-foreground)', strokeDasharray: '4 4' }} />
        <Area dataKey="b" type="linear" stroke="var(--color-b)" strokeWidth={1.75} fill="url(#balfill)" dot={false} isAnimationActive={!still} animationDuration={SPEED} />
      </AreaChart>
    </ChartContainer>
  )
}

// Money out per day, dashed line at the daily average; the hovered day (else the biggest) is lit and carries a
// date pill. Pills on edge days align to the bar's outer side so they never leave the card.
export function DailyBars({ days, avg }: { days: ReturnType<typeof daily>; avg: number }) {
  const still = useStill()
  const [hot, setHot] = useState<number | null>(null)
  const peak = days.reduce((m, d, i) => (d.out > days[m].out ? i : m), 0)
  const on = hot ?? peak
  return (
    <ChartContainer config={barsConfig} className="aspect-auto min-h-36 w-full flex-1" role="img"
      aria-label={`Money out per day for ${days.length} days; biggest day ${day(days[peak]?.d ?? '')} at ${baht(days[peak]?.out ?? 0)}`}>
      <BarChart data={days} margin={{ top: 30, left: 0, right: 0, bottom: 0 }} barCategoryGap="18%"
        onMouseMove={(st) => st.activeTooltipIndex != null && setHot(Number(st.activeTooltipIndex))} onMouseLeave={() => setHot(null)}>
        <defs>
          <linearGradient id="barhot" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--expense)" />
            <stop offset="100%" stopColor="var(--expense)" stopOpacity={0.45} />
          </linearGradient>
        </defs>
        <XAxis dataKey="d" hide />
        <YAxis hide domain={[0, 'dataMax']} />
        <ReferenceLine y={avg} stroke="var(--muted-foreground)" strokeDasharray="4 4" strokeOpacity={0.7} />
        <Bar dataKey="out" radius={6} minPointSize={4} isAnimationActive={!still} animationDuration={SPEED}>
          {days.map((d, i) => (
            <Cell key={d.d} fill={i === on ? 'url(#barhot)' : 'color-mix(in oklab, var(--expense) 24%, transparent)'} style={{ transition: 'fill .2s' }} />
          ))}
          <LabelList dataKey="out" content={(p) => {
            if (p.index !== on) return null
            const bx = Number(p.x), bw = Number(p.width), y = Number(p.y)
            const text = `${day(days[on].d)} · ${baht(days[on].out)}`
            const w = text.length * 6.8 + 18
            const at = days.length > 1 ? on / (days.length - 1) : 0.5
            const left = at < 0.25 ? bx : at > 0.75 ? bx + bw - w : bx + bw / 2 - w / 2
            return (
              <g style={{ pointerEvents: 'none' }}>
                <rect x={left} y={y - 28} width={w} height={22} rx={11} fill="var(--card)" stroke="var(--border)" />
                <text x={left + w / 2} y={y - 13} textAnchor="middle" fontSize={11} fontFamily="var(--font-mono)" fill="var(--foreground)">{text}</text>
              </g>
            )
          }} />
        </Bar>
      </BarChart>
    </ChartContainer>
  )
}
