import { useMemo, useState } from 'react'
import { motion } from 'motion/react'
import { Check, Plus, Search, Trash2 } from 'lucide-react'
import { InfoTip } from '@/components/ledger/info'
import { CountUp, Reveal } from '@/components/ledger/motion'
import { PayeeAvatar, Segmented } from '@/components/ledger/widgets'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { FIRST, LAST, TX, addDays, baht, daysBetween, monthLabel, payees } from '@/lib/ledger'
import { expectedFor, newId, perMonth, type PlanItem } from '@/lib/plan'
import { EASE } from '@/lib/utils'

type Every = PlanItem['every']
const LOOKBACK = 90  // days of history behind the suggested amounts
const EVERY: { value: Every; label: string }[] = [{ value: 'day', label: 'Daily' }, { value: 'month', label: 'Monthly' }]
const money = (s: string) => Math.max(0, Math.round((parseFloat(s) || 0) * 100) / 100)

// "Expected Spending" tab: the list of daily / monthly spending that sets the full bar of "Spent this month".
// Items come from the user's real payees (amount suggested from the last 90 days) or are typed in by hand.
export function PlanTab({ plan, onPlan }: { plan: PlanItem[]; onPlan: (p: PlanItem[]) => void }) {
  const monthDays = new Date(Date.UTC(+LAST.slice(0, 4), +LAST.slice(5, 7), 0)).getUTCDate()
  const total = expectedFor(plan, monthDays)
  const daily = plan.filter((i) => i.every === 'day').reduce((a, i) => a + i.amount, 0)
  const monthly = plan.filter((i) => i.every === 'month').reduce((a, i) => a + i.amount, 0)
  // Suggestions: the 30 most frequent payees of the last 90 days; a search looks through every payee ever (labels
  // included), so one with few or older payments can still be added.
  const recent = useMemo(() => new Map(payees(TX.filter((t) => t.date.slice(0, 10) > addDays(LAST, -LOOKBACK)), Infinity).map((p) => [p.key, p])), [])
  const everyone = useMemo(() => payees(TX, Infinity), [])
  const [q, setQ] = useState('')
  const ql = q.trim().toLowerCase()
  const suggest = ql
    ? everyone.filter((p) => `${p.name} ${p.key} ${p.last.desc} ${p.last.cat}`.toLowerCase().includes(ql)).slice(0, 50)
    : [...recent.values()].slice(0, 30)
  const span = daysBetween(FIRST, LAST) + 1
  const listed = new Set(plan.flatMap((i) => (i.key ? [i.key] : [])))

  const [name, setName] = useState('')
  const [amount, setAmount] = useState('')
  const [every, setEvery] = useState<Every>('day')
  const add = (i: Omit<PlanItem, 'id'>) => onPlan([...plan, { ...i, id: newId() }])
  const edit = (id: string, patch: Partial<PlanItem>) => onPlan(plan.map((i) => (i.id === id ? { ...i, ...patch } : i)))
  const ok = name.trim() && money(amount) > 0

  return (
    <div className="space-y-6 pt-4">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, ease: EASE }}>
        <h1 className="text-3xl font-normal tracking-tight sm:text-4xl">Expected spending</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          Mark what you spend every day or every month. Together they become the full bar of “Spent this month” on the dashboard. Saved in this browser only.
        </p>
      </motion.div>

      <Reveal now>
        <Card data-od-id="plan-total" className="ring-2 ring-brand/20 shadow-[0_28px_64px_-30px_var(--brand)]">
          <CardContent className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="flex items-center gap-1.5 text-sm text-muted-foreground">Expected for {monthLabel(LAST)} ({monthDays} days)
                <InfoTip>Daily items × days in the month, plus every monthly item once. This is the 100% mark of the “Spent this month” bar.</InfoTip>
              </p>
              <CountUp value={total} format={baht} className="display mt-1 block text-5xl" />
            </div>
            <dl className="grid grid-cols-2 gap-x-8 gap-y-1 text-sm">
              <dt className="text-muted-foreground">Daily items</dt><dd className="num text-right">{baht(daily)} × {monthDays}</dd>
              <dt className="text-muted-foreground">Monthly items</dt><dd className="num text-right">{baht(monthly)}</dd>
              <dt className="text-muted-foreground">About per day</dt><dd className="num text-right font-semibold">{baht(total / monthDays)}</dd>
            </dl>
          </CardContent>
        </Card>
      </Reveal>

      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <Reveal>
          <Card data-od-id="plan-list">
            <CardHeader>
              <CardTitle>Your list</CardTitle>
              <CardDescription>{plan.length ? `${plan.length} item${plan.length === 1 ? '' : 's'} · change the amount or how often any time` : 'Nothing yet: pick a payee on the right or add your own below.'}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              {plan.length > 0 && (
                <ul className="divide-y rounded-2xl border">
                  {plan.map((i) => (
                    <li key={i.id} className="flex flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2.5">
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium" title={i.name}>{i.name}</span>
                        <span className="num block text-xs text-muted-foreground">= {baht(perMonth(i, monthDays))} this month{i.key ? ' · from your payments' : ''}</span>
                      </span>
                      <Segmented id={`every-${i.id}`} label={`How often for ${i.name}`} value={i.every} onChange={(v) => edit(i.id, { every: v })} options={EVERY} />
                      <label className="flex items-center gap-1 text-sm text-muted-foreground">฿
                        <Input type="number" inputMode="decimal" min={0} step="any" aria-label={`Amount for ${i.name}`} className="num h-9 w-28 rounded-full text-right"
                          value={i.amount} onChange={(e) => edit(i.id, { amount: money(e.target.value) })} />
                      </label>
                      <button type="button" aria-label={`Remove ${i.name}`} onClick={() => onPlan(plan.filter((x) => x.id !== i.id))}
                        className="grid size-10 place-items-center rounded-full text-muted-foreground transition hover:bg-muted hover:text-neg">
                        <Trash2 className="size-4" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}

              <form className="space-y-3 rounded-2xl bg-muted/50 p-4" onSubmit={(e) => {
                e.preventDefault()
                if (!ok) return
                add({ name: name.trim(), amount: money(amount), every })
                setName(''); setAmount('')
              }}>
                <p className="text-sm font-medium">Add your own</p>
                <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_8rem]">
                  <label className="space-y-1 text-xs text-muted-foreground">What
                    <Input className="rounded-full" placeholder="e.g. Lunch, rent, phone bill" value={name} onChange={(e) => setName(e.target.value)} />
                  </label>
                  <label className="space-y-1 text-xs text-muted-foreground">Amount (฿)
                    <Input type="number" inputMode="decimal" min={0} step="any" className="num rounded-full text-right" placeholder="0" value={amount} onChange={(e) => setAmount(e.target.value)} />
                  </label>
                </div>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <Segmented id="new-every" label="How often" value={every} onChange={setEvery} options={EVERY} />
                  <button type="submit" disabled={!ok}
                    className="inline-flex items-center gap-1.5 rounded-full bg-brand px-4 py-2 text-sm font-medium text-white shadow-[0_8px_20px_-8px_var(--brand)] transition hover:brightness-110 active:scale-95 disabled:opacity-40 disabled:shadow-none">
                    <Plus className="size-4" />Add</button>
                </div>
                <p className="text-xs text-muted-foreground">Hand-added items count toward expected spending; use them for cash or anything not in your statements.</p>
              </form>
            </CardContent>
          </Card>
        </Reveal>

        <Reveal delay={0.08}>
          <Card data-od-id="plan-suggest">
            <CardHeader>
              <CardTitle className="flex items-center gap-1.5">From your payments
                <InfoTip>Your most frequent payees in the last {LOOKBACK} days. “Daily” suggests their total ÷ {LOOKBACK} days; “Monthly” suggests their total ÷ {LOOKBACK / 30} months. Search finds any payee, including ones you labelled; a payee with no recent payments gets its all-time average. You can change the amount after adding.</InfoTip>
              </CardTitle>
              <CardDescription>{ql ? 'Every payee matching your search' : `Last ${LOOKBACK} days, most frequent first`}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input className="rounded-full pl-9" placeholder="Search payee, your label, description…" aria-label="Search payees"
                  value={q} onChange={(e) => setQ(e.target.value)} />
              </div>
              <ul className="max-h-[36rem] divide-y overflow-y-auto rounded-2xl border">
                {suggest.length === 0 && <li className="py-8 text-center text-sm text-muted-foreground">No payee matches. Add it by hand on the left.</li>}
                {suggest.map((p) => {
                  // last-90-day total when there is one, else this payee's average over the whole ledger
                  const r = recent.get(p.key)
                  const perDay = Math.round((r ? r.amt / LOOKBACK : p.amt / span) * 100) / 100
                  const perMo = Math.round((r ? r.amt / (LOOKBACK / 30) : (p.amt / span) * 30) * 100) / 100
                  const on = listed.has(p.key)
                  return (
                    <li key={p.key} className="flex flex-wrap items-center gap-3 px-3 py-2.5">
                      <PayeeAvatar p={p} size={38} />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium" title={p.name}>{p.name}</span>
                        <span className="num block text-xs text-muted-foreground">{p.n} payments · {baht(p.amt)}{ql && (r ? ` · ${r.n} in last ${LOOKBACK} days` : ' · none lately, all-time average')}</span>
                      </span>
                      {on ? <span className="inline-flex items-center gap-1 text-xs text-pos"><Check className="size-4" />On your list</span> : (
                        <span className="flex gap-1.5">
                          <button type="button" onClick={() => add({ name: p.name, amount: perDay, every: 'day', key: p.key })}
                            className="rounded-full border px-3 py-1.5 text-xs transition hover:bg-muted active:scale-95 pointer-coarse:min-h-11">
                            Daily <span className="num text-muted-foreground">{baht(perDay)}</span></button>
                          <button type="button" onClick={() => add({ name: p.name, amount: perMo, every: 'month', key: p.key })}
                            className="rounded-full border px-3 py-1.5 text-xs transition hover:bg-muted active:scale-95 pointer-coarse:min-h-11">
                            Monthly <span className="num text-muted-foreground">{baht(perMo)}</span></button>
                        </span>
                      )}
                    </li>
                  )
                })}
              </ul>
            </CardContent>
          </Card>
        </Reveal>
      </div>
    </div>
  )
}
