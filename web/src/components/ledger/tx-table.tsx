import { useMemo, useState, useSyncExternalStore } from 'react'
import Pagination from '@mui/material/Pagination'
import { ArrowDown, ArrowUp, Search } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { LATE_NOTE, bankName, baht, descOf, lateNight, signed, TX, type Tx } from '@/lib/ledger'
import { cn } from '@/lib/utils'
import { TxDrawer } from '@/components/ledger/tx-drawer'

// New-row highlight. The dashboard hot-reloads (main.tsx), so "new" = not in the set of rows the last page load saw.
// Rows get a stable key (date|amount|desc, #n for repeats) that is also the React key. First visit highlights nothing.
const SEEN = 'ledger-seen-rows'
export const KEY = new Map<Tx, string>()
const count = new Map<string, number>()
for (const t of TX) {
  const k = `${t.date}|${t.amt}|${t.desc}`
  const n = (count.get(k) ?? 0) + 1
  count.set(k, n)
  KEY.set(t, `${k}#${n}`)
}
const FRESH = (() => {
  try {
    if (!TX.length) return new Set<string>()   // empty ledger: don't record "no rows seen", or the first real load marks every row new
    const old = localStorage.getItem(SEEN)
    localStorage.setItem(SEEN, JSON.stringify([...KEY.values()]))
    if (!old) return new Set<string>()
    const had = new Set<string>(JSON.parse(old))
    return new Set([...KEY.values()].filter((k) => !had.has(k)))
  } catch { return new Set<string>() }  // storage blocked: no highlight
})()
const fresh = (r: Tx) => FRESH.has(KEY.get(r)!)

// Rows per numbered page (fits one screen without an inner scroll). Drawing all 1500 rows at once was ~6500 DOM
// nodes re-rendered on every keystroke / year switch.
const PAGE = 15
type Key = 'date' | 'desc' | 'cat' | 'amt' | 'bal'

const CMP: Record<Key, (a: Tx, b: Tx) => number> = {
  date: (a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0),
  desc: (a, b) => a.desc.localeCompare(b.desc, 'th'),
  cat: (a, b) => a.cat.localeCompare(b.cat, 'th'),
  amt: (a, b) => a.amt - b.amt,
  bal: (a, b) => (a.bal ?? 0) - (b.bal ?? 0),
}

const SORT_OPTIONS: { key: Key; label: string; ariaLabel: string }[] = [
  { key: 'date', label: 'Date', ariaLabel: 'Sort by date' },
  { key: 'desc', label: 'Desc', ariaLabel: 'Sort by description' },
  { key: 'cat', label: 'Cat', ariaLabel: 'Sort by category' },
  { key: 'amt', label: 'Amt', ariaLabel: 'Sort by amount' },
  { key: 'bal', label: 'Bal', ariaLabel: 'Sort by balance' },
]

// Mount only one of table / card list: rendering both doubles ~1500 rows of DOM on every sort/filter.
const lg = '(min-width: 1024px)'
const useDesktop = () =>
  useSyncExternalStore(
    (cb) => { const m = matchMedia(lg); m.addEventListener('change', cb); return () => m.removeEventListener('change', cb) },
    () => matchMedia(lg).matches,
  )

// Search term lives in App so the payee card's "Show" can set it.
export function TxTable({ rows, caption, term, onTerm }: { rows: Tx[]; caption: string; term: string; onTerm: (t: string) => void }) {
  const desktop = useDesktop()
  const [sel, setSel] = useState<Tx | null>(null)
  const [filter, setFilter] = useState<'all' | 'in' | 'out'>('all')
  const [sort, setSort] = useState<{ key: Key; dir: 1 | -1 }>({ key: 'date', dir: -1 })
  const [page, setPage] = useState(1)
  // back to one page whenever the list itself changes (adjusting state during render, no extra effect pass)
  const [seen, setSeen] = useState({ rows, term, filter, sort })
  if (seen.rows !== rows || seen.term !== term || seen.filter !== filter || seen.sort !== sort) {
    setSeen({ rows, term, filter, sort })
    setPage(1)
  }

  const shown = useMemo(() => {
    const t = term.trim().toLowerCase()
    const r = rows.filter((x) =>
      (filter === 'all' || (filter === 'in' ? x.amt >= 0 : x.amt < 0)) &&
      (!t || x.desc.toLowerCase().includes(t) || x.cat.toLowerCase().includes(t) || !!x.label?.toLowerCase().includes(t) || bankName(x.bank).toLowerCase().includes(t)))
    return r.sort((a, b) => CMP[sort.key](a, b) * sort.dir)  // stable: ties keep ledger order
  }, [rows, term, filter, sort])

  // Same column toggles direction; a new column starts at its natural end (text A first, else biggest/newest).
  const click = (key: Key) =>
    setSort((s) => (s.key === key ? { key, dir: (-s.dir) as 1 | -1 } : { key, dir: key === 'desc' || key === 'cat' ? 1 : -1 }))

  const head = (k: Key, children: string, opts: { num?: boolean; hide?: boolean } = {}) => (
    <TableHead key={k} className={cn('select-none whitespace-nowrap font-mono text-[11px] font-semibold uppercase tracking-[0.08em]',
      opts.num && 'text-right', opts.hide && 'hidden lg:table-cell')}
      aria-sort={sort.key === k ? (sort.dir < 0 ? 'descending' : 'ascending') : undefined}>
      <button type="button" onClick={() => click(k)} className="cursor-pointer uppercase tracking-[inherit]">
        {children}
        {sort.key === k && (sort.dir < 0 ? <ArrowDown className="ml-1 inline size-3" /> : <ArrowUp className="ml-1 inline size-3" />)}
      </button>
    </TableHead>
  )

  const pages = Math.ceil(shown.length / PAGE)
  const from = (page - 1) * PAGE
  const view = shown.slice(from, from + PAGE)
  // a new page starts at the top of the card, not wherever the pager was
  const turn = (p: number) => {
    setPage(p)
    const top = document.getElementById('transactions')
    if (top && top.getBoundingClientRect().top < 0) top.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <Card id="transactions" data-od-id="transactions" className="scroll-mt-20">
      <CardHeader className="pb-1">
        <CardTitle>All transactions</CardTitle>
        <CardDescription>{caption}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="space-y-2">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <div className="relative min-w-0 flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input className="pl-9" placeholder="Search description, label, category, bank…" aria-label="Search transactions"
                value={term} onChange={(e) => onTerm(e.target.value)} />
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2 sm:justify-start">
              <ToggleGroup variant="outline" value={[filter]} onValueChange={(v) => v[0] && setFilter(v[0] as typeof filter)} aria-label="Filter transactions">
                <ToggleGroupItem value="all">All</ToggleGroupItem>
                <ToggleGroupItem value="in">Income</ToggleGroupItem>
                <ToggleGroupItem value="out">Expense</ToggleGroupItem>
              </ToggleGroup>
              <span className="num text-xs text-muted-foreground">{shown.length} of {rows.length}</span>
            </div>
          </div>
          {!desktop && <div className="flex flex-wrap items-center gap-2">
            <span className="sr-only text-xs text-muted-foreground sm:not-sr-only">Sort by</span>
            <ToggleGroup size="sm" variant="outline" value={[sort.key]}
              onValueChange={(v) => v[0] && click(v[0] as Key)} aria-label="Sort transactions by">
              {SORT_OPTIONS.map((option) => (
                <ToggleGroupItem key={option.key} value={option.key} aria-label={option.ariaLabel}>{option.label}</ToggleGroupItem>
              ))}
            </ToggleGroup>
            <Button variant="outline" size="icon-sm" aria-label={`Sort ${sort.dir === 1 ? 'descending' : 'ascending'}`} onClick={() => click(sort.key)}>
              {sort.dir === 1 ? <ArrowUp /> : <ArrowDown />}
            </Button>
          </div>}
        </div>

        {desktop ? <div className="overflow-hidden rounded-lg border">
          <Table className="min-w-[660px]">
            <TableHeader className="bg-card">
              <TableRow>
                {head('date', 'Date / time')}
                {head('desc', 'Description')}
                {head('cat', 'Category', { hide: true })}
                {head('amt', 'Amount', { num: true })}
                {head('bal', 'Balance', { num: true })}
              </TableRow>
            </TableHeader>
            <TableBody>
              {shown.length === 0 && (
                <TableRow><TableCell colSpan={5} className="py-10 text-center text-muted-foreground">No transactions match your search.</TableCell></TableRow>
              )}
              {view.map((r) => (
                <TableRow key={KEY.get(r)} tabIndex={0} className={cn('cursor-pointer', fresh(r) && 'tx-new')} onClick={() => setSel(r)}
                  onKeyDown={(e) => e.key === 'Enter' && setSel(r)}>
                  <TableCell className="num whitespace-nowrap px-3 py-2 align-top text-xs text-muted-foreground">
                    {r.date.slice(0, 10)}<small className="block">{r.date.slice(11)}</small>
                  </TableCell>
                  <TableCell className="max-w-56 whitespace-normal px-3 py-2 align-top">
                    {r.label ? <><span className="font-medium">{r.label}</span><small className="block text-muted-foreground">{descOf(r)}</small></> : descOf(r)}
                    {lateNight(r) && <span title={LATE_NOTE} className="ml-1.5 inline-block rounded-full border px-1.5 text-xs text-muted-foreground align-middle">late-night</span>}
                  </TableCell>
                  <TableCell className="hidden px-3 py-2 align-top lg:table-cell">
                    <Badge variant="outline">{r.cat}</Badge><small className="mt-1 block text-muted-foreground">{bankName(r.bank)}</small>
                  </TableCell>
                  <TableCell className={cn('num px-3 py-2 text-right align-top font-semibold', r.amt >= 0 ? 'text-pos' : 'text-neg')}>{signed(r.amt)}</TableCell>
                  <TableCell className="num px-3 py-2 text-right align-top text-muted-foreground">{r.bal == null ? '—' : baht(r.bal)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div> : <div className="rounded-lg border px-3">
          {shown.length === 0 && <p className="py-10 text-center text-sm text-muted-foreground">No transactions match your search.</p>}
          {view.map((r) => (
            <article key={KEY.get(r)} tabIndex={0} onClick={() => setSel(r)} onKeyDown={(e) => e.key === 'Enter' && setSel(r)}
              className={cn(fresh(r) && 'tx-new', 'grid cursor-pointer grid-cols-[minmax(0,1fr)_auto] gap-x-3 border-b py-2.5 last:border-b-0')}>
              <div className="min-w-0">
                <p className="break-words text-sm font-medium leading-snug">{r.label ?? descOf(r)}{lateNight(r) && <span title={LATE_NOTE} className="ml-1.5 inline-block rounded-full border px-1.5 text-xs text-muted-foreground align-middle">late-night</span>}</p>
                {r.label && <p className="break-words text-xs text-muted-foreground">{descOf(r)}</p>}
                <div className="mt-1.5 flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
                  <span className="num text-xs text-muted-foreground">{r.date.slice(0, 10)} · {r.date.slice(11)} · {bankName(r.bank)}</span>
                  <Badge variant="outline" className="max-w-40 truncate">{r.cat}</Badge>
                </div>
              </div>
              <div className="text-right">
                <p className={cn('num whitespace-nowrap text-sm font-semibold', r.amt >= 0 ? 'text-pos' : 'text-neg')}>{signed(r.amt)}</p>
                <p className="num mt-1 text-xs text-muted-foreground">{r.bal == null ? '—' : baht(r.bal)}</p>
              </div>
            </article>
          ))}
        </div>}
        {pages > 1 && (
          <nav aria-label="Transaction pages" className="flex flex-col items-center gap-2 pt-1 sm:flex-row sm:justify-between">
            <span className="num text-xs text-muted-foreground">{from + 1}–{from + view.length} of {shown.length}</span>
            <Pagination count={pages} page={page} onChange={(_, p) => turn(p)} shape="rounded" size={desktop ? 'medium' : 'large'}
              siblingCount={desktop ? 1 : 0} boundaryCount={1}
              sx={{ '& .MuiPaginationItem-root': { color: 'var(--foreground)', borderColor: 'var(--border)', fontFamily: 'var(--font-mono)', borderRadius: '9999px' },
                '& .MuiPaginationItem-root:hover': { bgcolor: 'var(--muted)' },
                '& .MuiPaginationItem-root.Mui-selected': { bgcolor: 'var(--brand)', color: '#fff', fontWeight: 600 } }} />
          </nav>
        )}
      </CardContent>
      <TxDrawer tx={sel} onClose={() => setSel(null)} />
    </Card>
  )
}
