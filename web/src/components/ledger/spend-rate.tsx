import { useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { FIRST, LAST, baht, idx, monthsBack, pctOf, rateTable, type RateRow } from '@/lib/ledger'
import { InfoTip } from '@/components/ledger/info'
import { cn } from '@/lib/utils'

export function Index({ r, usual }: { r: number; usual: number | null }) {
  const v = idx(r, usual)
  if (v == null) return <>—</>
  return <span className={cn(v > 1.15 ? 'text-neg' : v < 0.85 && 'text-pos')}>{v.toFixed(2)}×</span>
}

const PRESETS: [number, string][] = [[3, '3 mo'], [4, '4 mo'], [6, '6 mo'], [12, '12 mo'], [0, 'All']]

export function SpendRate() {
  const [from, setFrom] = useState(monthsBack(4))
  const [to, setTo] = useState(LAST)
  const [cash, setCash] = useState(false)
  const bad = !from || !to || from > to
  const t = useMemo(() => (bad ? null : rateTable(from, to, cash)), [bad, from, to, cash])

  const line = (label: React.ReactNode, r: RateRow, usual: number | null, total?: boolean) => (
    <TableRow key={String(label)} className={cn(total && 'border-t-2 font-semibold')}>
      <TableCell>{label}</TableCell>
      <TableCell className="num text-right">{r.days}</TableCell>
      <TableCell className="num text-right">{baht(r.spend)}</TableCell>
      <TableCell className="num text-right">{baht(r.rate)}</TableCell>
      <TableCell className="num text-right"><Index r={r.rate} usual={usual} /></TableCell>
      <TableCell className="num text-right">{baht(r.inc)}</TableCell>
      <TableCell className="num text-right">{pctOf(r.out, r.inc)}</TableCell>
    </TableRow>
  )

  return (
    <Card id="spend-rate" data-od-id="spend-rate" className="scroll-mt-20">
      <CardHeader>
        <CardTitle className="flex items-center gap-1.5">Spend rate by period
          <InfoTip>
            ฿/day = spending ÷ calendar days{t?.clipped ? ` (counted up to the last record, ${LAST})` : ''}. "vs usual" = that ÷ your usual rate:
            above 1× is faster than usual. Out ÷ in = all money out ÷ income.
          </InfoTip>
        </CardTitle>
        <CardDescription>
          {t && (t.usual == null ? 'No data in this range.'
            : <>Your usual rate is <b className="num text-foreground">{baht(t.usual)}/day</b> (the median of {t.nPrior}{t.own ? ' months in this range' : ' earlier months'}).</>)}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
          <label className="flex items-center gap-2">From
            <Input type="date" className="w-40" min={FIRST} max={LAST} value={from} onChange={(e) => setFrom(e.target.value)} />
          </label>
          <label className="flex items-center gap-2">To
            <Input type="date" className="w-40" min={FIRST} max={LAST} value={to} onChange={(e) => setTo(e.target.value)} />
          </label>
          <div className="flex flex-wrap gap-1">
            {PRESETS.map(([n, l]) => (
              <Button key={l} size="sm" variant="outline"
                onClick={() => { setFrom(n ? monthsBack(n) : FIRST); setTo(LAST) }}>{l}</Button>
            ))}
          </div>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={cash} onChange={(e) => setCash(e.target.checked)} />
            Count cash, lending &amp; stock as spending
          </label>
        </div>
        <div className="overflow-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow className="font-mono text-[11px] font-semibold uppercase tracking-[0.08em]">
                <TableHead>Period</TableHead>
                {['Days', 'Spending', '฿ / day', 'vs usual', 'Income', 'Out ÷ in'].map((h) => (
                  <TableHead key={h} className="text-right">{h}</TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {!t && <TableRow><TableCell colSpan={7} className="py-10 text-center text-muted-foreground">Pick a start date on or before the end date.</TableCell></TableRow>}
              {t?.months.map((m) => line(<>{m.k}{m.partial && <small className="ml-1 text-muted-foreground">partial</small>}</>, m, t.usual))}
              {t && line('Whole range', t.total, t.usual, true)}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  )
}
