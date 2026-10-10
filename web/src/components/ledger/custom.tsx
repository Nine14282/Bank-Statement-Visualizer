import { useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { Search, Trash2 } from 'lucide-react'
import { Reveal } from '@/components/ledger/motion'
import { LabelForm } from '@/components/ledger/tx-drawer'
import { PayeeAvatar, Segmented } from '@/components/ledger/widgets'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { OWN, RULES, TX, baht, payeeKey, payees, ruleFor, rowsFor, saveRules, type Rule, type Tx } from '@/lib/ledger'
import { EASE } from '@/lib/utils'

// Per label rule: every row containing its text, and how many of them another (more specific) label takes. Module level,
// not in the render: rules only change by saving, which reloads the page, and this scans the whole ledger per rule.
const RULE_STATS = RULES.map((r) => {
  const rows = rowsFor(r)
  const won = rows.filter((t) => ruleFor(t.desc) === r).length
  const taker = rows.find((t) => ruleFor(t.desc) !== r)
  return { r, rows, won, by: taker && ruleFor(taker.desc) }
})
const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? '' : 's'}`

// "Custom Your Transaction" tab: every payee (money out) or payer (money in), with the same label editor the
// transaction drawer has. Labels are browser-local rules; saving reloads, and the #custom hash brings you back here.
export function CustomTab() {
  const [dir, setDir] = useState<'out' | 'in'>('out')
  const [q, setQ] = useState('')
  const all = useMemo(() => payees(TX, Infinity, dir === 'in', true), [dir])
  const list = useMemo(() => {
    const t = q.trim().toLowerCase()
    return t ? all.filter((p) => `${p.name} ${p.key} ${p.last.desc} ${p.last.cat}`.toLowerCase().includes(t)) : all
  }, [all, q])
  const [sel, setSel] = useState<Tx | null>(null)
  const [selRule, setSelRule] = useState<Rule | undefined>()
  const tx = sel ?? list[0]?.last ?? null
  const p = tx && all.find((x) => x.key === payeeKey(tx))
  const labeled = all.filter((x) => x.last.label).length

  // Search matches in the other direction, so a payee filed under Money in isn't "missing" while Money out is shown.
  const other = useMemo(() => payees(TX, Infinity, dir !== 'in', true), [dir])
  const ql = q.trim().toLowerCase()
  const elsewhere = ql ? other.filter((p) => `${p.name} ${p.key} ${p.last.desc} ${p.last.cat}`.toLowerCase().includes(ql)).length : 0

  const pick = (t: Tx, rule?: Rule) => {
    setSel(t)
    setSelRule(rule)
    if (!matchMedia('(min-width: 1024px)').matches) document.getElementById('label-editor')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <div className="space-y-6 pt-4">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, ease: EASE }}>
        <h1 className="text-3xl font-normal tracking-tight sm:text-4xl">Custom your transactions</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          Give a payee your own name and category. Every matching transaction, total and chart uses it. Saved in this browser only.
        </p>
      </motion.div>

      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]">
        <Reveal>
          <Card data-od-id="custom-payees">
            <CardHeader>
              <CardTitle>{dir === 'out' ? 'Who you pay' : 'Who pays you'}</CardTitle>
              <CardDescription>{plural(all.length, dir === 'out' ? 'payee' : 'payer')} · {labeled} named · most frequent first</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                <div className="relative min-w-0 flex-1">
                  <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                  <Input className="rounded-full pl-9" placeholder="Search name, description, category…" aria-label="Search payees"
                    value={q} onChange={(e) => setQ(e.target.value)} />
                </div>
                <Segmented id="custom-dir" label="Direction" value={dir} onChange={(v) => { setDir(v); setSel(null); setSelRule(undefined) }}
                  options={[{ value: 'out', label: 'Money out' }, { value: 'in', label: 'Money in' }]} />
              </div>
              {elsewhere > 0 && (
                <button type="button" onClick={() => { setDir(dir === 'in' ? 'out' : 'in'); setSel(null); setSelRule(undefined) }}
                  className="w-full rounded-xl border border-dashed px-3 py-2 text-left text-sm text-muted-foreground transition hover:bg-muted/60 hover:text-foreground">
                  {`${elsewhere} ${elsewhere === 1 ? 'match' : 'matches'}`} in {dir === 'in' ? 'Money out' : 'Money in'} → show
                </button>
              )}
              <ul className="max-h-[38rem] divide-y overflow-y-auto rounded-2xl border">
                {list.length === 0 && <li className="py-10 text-center text-sm text-muted-foreground">Nothing matches your search{elsewhere ? '' : '.'}</li>}
                {list.map((x) => {
                  const on = x === p
                  return (
                    <li key={x.key}>
                      <button type="button" onClick={() => pick(x.last)} aria-pressed={on}
                        className="relative grid w-full grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 px-3 py-2.5 text-left transition-colors hover:bg-muted/60">
                        {on && <motion.span layoutId="custom-pick" className="absolute inset-0 bg-brand/10 ring-1 ring-brand/40 ring-inset"
                          transition={{ type: 'spring', stiffness: 420, damping: 34 }} />}
                        <span className="relative"><PayeeAvatar p={x} size={38} /></span>
                        <span className="relative min-w-0">
                          <span className="flex items-center gap-2">
                            <span className="truncate text-sm font-medium" title={x.name}>{x.name}</span>
                            {x.last.label && <Badge variant="outline" className="shrink-0 border-brand/50 text-brand">named</Badge>}
                            {x.last.cat === OWN && <Badge variant="outline" className="shrink-0" title="Category “Own transfer”: left out of income, expenses and spending">own transfer · not in totals</Badge>}
                          </span>
                          <span className="num block truncate text-xs text-muted-foreground">{x.last.cat} · {plural(x.n, 'time')} · last {x.last.date.slice(0, 10)}</span>
                        </span>
                        <span className="num relative text-right text-sm font-semibold">{baht(x.amt)}</span>
                      </button>
                    </li>
                  )
                })}
              </ul>
            </CardContent>
          </Card>
        </Reveal>

        <div className="space-y-4 lg:sticky lg:top-20">
          <Reveal delay={0.08}>
            <Card id="label-editor" data-od-id="label-editor" className="scroll-mt-20">
              <CardHeader>
                <CardTitle>Name it</CardTitle>
                <CardDescription>Pick a payee on the list, then set its label.</CardDescription>
              </CardHeader>
              <CardContent>
                <AnimatePresence mode="wait" initial={false}>
                  {tx ? (
                    <motion.div key={payeeKey(tx)} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.22, ease: EASE }}>
                      {p && (
                        <div className="flex items-center gap-3">
                          <PayeeAvatar p={p} size={52} />
                          <div className="min-w-0">
                            <p className="truncate font-medium" title={p.name}>{p.name}</p>
                            <p className="num text-xs text-muted-foreground">{plural(p.n, 'transaction')} · {baht(p.amt)}</p>
                          </div>
                        </div>
                      )}
                      <p className="eyebrow mt-4">Latest description</p>
                      <p className="mt-1 rounded-xl bg-muted/60 px-3 py-2 text-xs leading-relaxed break-words">{tx.desc}</p>
                      <LabelForm key={tx.date + tx.desc + tx.amt + (selRule?.match ?? '')} tx={tx} rule={selRule} />
                    </motion.div>
                  ) : <p className="py-8 text-center text-sm text-muted-foreground">No payees yet.</p>}
                </AnimatePresence>
              </CardContent>
            </Card>
          </Reveal>

          <Reveal delay={0.14}>
            <Card data-od-id="label-rules">
              <CardHeader>
                <CardTitle>Your labels</CardTitle>
                <CardDescription>{RULES.length ? `${plural(RULES.length, 'rule')}, applied to new statements too` : 'None yet: name a payee to add one.'}</CardDescription>
              </CardHeader>
              {RULES.length > 0 && (
                <CardContent>
                  <ul className="divide-y">
                    {RULE_STATS.map(({ r, rows, won, by }) => {
                      return (
                        <li key={r.match} className="flex items-center gap-2 py-2">
                          <button type="button" disabled={!rows.length} onClick={() => pick(rows.find((t) => ruleFor(t.desc) === r) ?? rows[0], r)} title={`Edit “${r.label}”`}
                            className="min-w-0 flex-1 rounded-lg px-1 py-0.5 text-left transition-colors hover:bg-muted/60 disabled:opacity-60">
                            <span className="block truncate text-sm font-medium">{r.label}{r.cat && <span className="text-muted-foreground"> · {r.cat}</span>}</span>
                            <span className="num block truncate text-xs text-muted-foreground" title={r.match}>contains “{r.match}” · {plural(won, 'transaction')}</span>
                            {by && <span className="block text-xs text-neg">{rows.length - won} shown as “{by.label}”, a more specific label</span>}
                            {!rows.length && <span className="block text-xs text-muted-foreground">No transaction contains this text yet</span>}
                          </button>
                          <button type="button" aria-label={`Remove label ${r.label}`} onClick={() => confirm(`Remove the label "${r.label}"?`) && saveRules(RULES.filter((x) => x !== r))}
                            className="grid size-10 shrink-0 place-items-center rounded-full text-muted-foreground transition hover:bg-muted hover:text-neg">
                            <Trash2 className="size-4" />
                          </button>
                        </li>
                      )
                    })}
                  </ul>
                </CardContent>
              )}
            </Card>
          </Reveal>
        </div>
      </div>
    </div>
  )
}
