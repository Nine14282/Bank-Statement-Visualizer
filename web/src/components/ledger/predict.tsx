import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { FIRST, LAST, TX, addDays, balanceNow, bankName, baht, daysBetween, rateRow } from '@/lib/ledger'
import { InfoTip } from '@/components/ledger/info'
import { cn } from '@/lib/utils'

// Current money = every account's last printed balance + later rows that carry none (payment-notice emails).
const NOW = (() => {
  const { total, parts } = balanceNow(TX)
  return parts.length ? { bal: total, parts } : null
})()

// The real date (local), re-checked every minute so an open tab rolls over at midnight.
const todayStr = () => new Date().toLocaleDateString('en-CA')
function useToday() {
  const [d, setD] = useState(todayStr)
  useEffect(() => { const id = setInterval(() => setD(todayStr()), 60_000); return () => clearInterval(id) }, [])
  return d
}

const WINDOWS: [number, string][] = [[-1, 'This month'], [7, '7 days'], [14, '14 days'], [30, '30 days'], [90, '90 days'], [0, 'All']]
const SCENARIOS = [0.5, 0.75, 1, 1.25, 1.5]

export function Predict() {
  const [days, setDays] = useState(30)
  const [cash, setCash] = useState(false)
  const [net, setNet] = useState(false)
  const real = useToday()
  if (!NOW) return null

  // Windows end today, not at the last record: days with no record count as days with no spending
  // (payment emails keep the ledger near-current). -1 = this month so far, 0 = all; never start before the first record.
  const today = real > LAST ? real : LAST
  const start = days < 0 ? today.slice(0, 8) + '01' : days ? addDays(today, 1 - days) : FIRST
  const t = rateRow(start > FIRST ? start : FIRST, today, cash)
  const rate = (net ? t.spend - t.inc : t.spend) / t.days  // ฿/day leaving the account
  const stale = daysBetween(LAST, today)  // days since the newest record
  // Money is as of LAST; the date it runs out is LAST + balance/rate, and "lasts" counts from today.
  const left = (r: number) => (NOW.bal <= 0 ? 0 : r > 0 ? Math.max(0, Math.floor(NOW.bal / r) - stale) : null)  // null = never runs out
  const until = (r: number) => (NOW.bal <= 0 ? LAST : r > 0 ? addDays(LAST, Math.floor(NOW.bal / r)) : '—')
  const main = left(rate)

  return (
    <Card id="predict" data-od-id="predict" className="scroll-mt-20">
      <CardHeader>
        <CardTitle className="flex items-center gap-1.5">How long will my money last?
          <InfoTip>
            Current money ÷ spending per day, assuming the rate stays flat. Money: {NOW.parts.map((p) => `${bankName(p.bank)} ${baht(p.bal)} (statement to ${p.at}${p.est ? ' + payment emails' : ''})`).join(' · ')}.
            {stale > 0 ? ` The newest record is ${stale} day${stale === 1 ? '' : 's'} old; those days are assumed spent at the same rate.` : ''} Transfers between your own accounts don't count.
          </InfoTip>
        </CardTitle>
        <CardDescription>A rough guide, not a forecast · today {today}, newest record {LAST}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
          <span>Rate from the last</span>
          <div className="flex flex-wrap gap-1">
            {WINDOWS.map(([n, l]) => (
              <Button key={l} size="sm" variant={days === n ? 'default' : 'outline'} onClick={() => setDays(n)}>{l}</Button>
            ))}
          </div>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={cash} onChange={(e) => setCash(e.target.checked)} />
            Count cash, lending &amp; stock as spending
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={net} onChange={(e) => setNet(e.target.checked)} />
            Subtract income (net rate)
          </label>
        </div>

        <div className="grid gap-4 border-y py-4 sm:grid-cols-3">
          <div>
            <div className="eyebrow">Current money</div>
            <div className="display mt-1 text-3xl">{baht(NOW.bal)}</div>
          </div>
          <div>
            <div className="eyebrow">{net ? 'Net burn' : 'Spending'} / day</div>
            <div className="display mt-1 text-3xl">{baht(rate)}</div>
            <div className="text-xs text-muted-foreground">over {t.days} day{t.days === 1 ? '' : 's'} up to {today}</div>
          </div>
          <div>
            <div className="eyebrow">Will last</div>
            <div className={cn('display mt-1 text-3xl', main != null && main < 14 && 'text-neg')}>
              {main == null ? 'Not running out' : `${main} day${main === 1 ? '' : 's'}`}
            </div>
            <div className="text-xs text-muted-foreground">
              {main == null ? 'income is at least what you spend' : NOW.bal <= 0 ? 'balance is already empty' : `until about ${until(rate)}`}
            </div>
          </div>
        </div>

        <div className="overflow-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow className="font-mono text-[11px] font-semibold uppercase tracking-[0.08em]">
                <TableHead>If spending is…</TableHead>
                {['฿ / day', 'Lasts', 'Until'].map((h) => <TableHead key={h} className="text-right">{h}</TableHead>)}
              </TableRow>
            </TableHeader>
            <TableBody>
              {SCENARIOS.map((m) => {
                const d = left(rate * m)
                return (
                  <TableRow key={m} className={cn(m === 1 && 'font-semibold')}>
                    <TableCell>{m === 1 ? 'Same as now' : m < 1 ? `${Math.round((1 - m) * 100)}% less` : `${Math.round((m - 1) * 100)}% more`}</TableCell>
                    <TableCell className="num text-right">{baht(rate * m)}</TableCell>
                    <TableCell className="num text-right">{d == null ? '∞' : `${d} day${d === 1 ? '' : 's'}`}</TableCell>
                    <TableCell className="num text-right">{until(rate * m)}</TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  )
}
