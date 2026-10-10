import { useState } from 'react'
import { Copy, X } from 'lucide-react'
import Chip from '@mui/material/Chip'
import Divider from '@mui/material/Divider'
import Drawer from '@mui/material/Drawer'
import IconButton from '@mui/material/IconButton'
import Snackbar from '@mui/material/Snackbar'
import Typography from '@mui/material/Typography'
import { LATE_NOTE, RULES, TX, bankName, baht, lateNight, merchant, ruleFor, saveRules, signed, type Rule, type Tx } from '@/lib/ledger'
import { cn } from '@/lib/utils'

const Row = ({ label, children }: { label: string; children: React.ReactNode }) => (
  <div className="flex items-baseline justify-between gap-4 py-3">
    <span className="eyebrow">{label}</span>
    <span className="num text-right text-sm">{children}</span>
  </div>
)

const CATS = [...new Set(TX.map((t) => t.cat))].sort()

// Label editor: key it by tx (and rule) so the fields reset when another one is opened. Edits the label that wins
// for this transaction, or `rule` when the caller picked a specific one (e.g. a label hidden by a broader one).
export function LabelForm({ tx, rule = ruleFor(tx.desc) }: { tx: Tx; rule?: Rule }) {
  const [match, setMatch] = useState(rule?.match ?? merchant(tx.desc))
  const [label, setLabel] = useState(rule?.label ?? '')
  const [cat, setCat] = useState(rule?.cat ?? '')
  const m = match.trim().toLowerCase()
  const others = RULES.filter((r) => r !== rule)
  const rows = m ? TX.filter((t) => t.desc.toLowerCase().includes(m)) : []
  // rows a longer (more specific) label would keep, since the most specific label wins
  const taken = rows.filter((t) => others.some((r) => r.match.length > m.length && t.desc.toLowerCase().includes(r.match.toLowerCase()))).length
  const hits = rows.length - taken
  const field = 'w-full rounded-xl border bg-transparent px-3 py-2 text-sm outline-none transition-shadow focus:ring-2 focus:ring-ring/40'
  return (
    <form className="mt-4 space-y-2" onSubmit={(e) => {
      e.preventDefault()
      if (m && label.trim()) saveRules([...others, { match: match.trim(), label: label.trim(), ...(cat.trim() && { cat: cat.trim() }) }])
    }}>
      <p className="eyebrow">Your label</p>
      <input className={field} placeholder="e.g. Auntie Kaek – Thai food" aria-label="Label" value={label} onChange={(e) => setLabel(e.target.value)} />
      <input className={field} placeholder="Category (optional)" aria-label="Category" list="ledger-cats" value={cat} onChange={(e) => setCat(e.target.value)} />
      <datalist id="ledger-cats">{CATS.map((c) => <option key={c} value={c} />)}</datalist>
      <label className="block text-xs text-muted-foreground">Apply to every description containing
        <input className={cn(field, 'mt-1')} aria-label="Match text" value={match} onChange={(e) => setMatch(e.target.value)} />
      </label>
      <p className="text-xs text-muted-foreground">Matches {hits} transaction{hits === 1 ? '' : 's'} now{taken ? ` (${taken} more keep a more specific label)` : ''}, and new ones as they arrive. Saved in this browser.</p>
      <div className="flex gap-2">
        <button type="submit" disabled={!m || !label.trim()} className="rounded-full bg-brand px-4 py-2 text-sm font-medium text-white shadow-[0_8px_20px_-8px_var(--brand)] transition hover:brightness-110 active:scale-95 disabled:opacity-40 disabled:shadow-none">Save label</button>
        {rule && <button type="button" onClick={() => confirm(`Remove the label "${rule.label}"?`) && saveRules(others)} className="rounded-full border px-4 py-2 text-sm text-neg transition hover:bg-muted active:scale-95">Remove</button>}
      </div>
    </form>
  )
}

export function TxDrawer({ tx, onClose }: { tx: Tx | null; onClose: () => void }) {
  const [toast, setToast] = useState('')
  const copy = async () => {
    try { await navigator.clipboard.writeText(tx!.desc); setToast('Description copied') }
    catch { setToast('Copy not available here') }
  }
  return (
    <>
      <Drawer anchor="right" open={!!tx} onClose={onClose}
        slotProps={{ paper: { sx: { width: 'min(420px, 100vw)', bgcolor: 'var(--card)', color: 'var(--foreground)',
          borderLeft: '1px solid var(--border)' } } }}>
        {tx && (
          <div className="flex h-full flex-col p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="eyebrow">Transaction</p>
                <Typography component="h2" className="display text-3xl">{tx.date.slice(0, 10)}</Typography>
                <p className="num text-xs text-muted-foreground">{tx.date.slice(11)}</p>
              </div>
              <IconButton aria-label="Close details" onClick={onClose} sx={{ color: 'var(--muted-foreground)' }}><X className="size-4" /></IconButton>
            </div>

            <div className={cn('display mt-6 text-5xl', tx.amt >= 0 ? 'text-pos' : 'text-neg')}>{signed(tx.amt)}</div>
            <div className="mt-2">
              <Chip size="small" variant="outlined" label={tx.cat} sx={{ color: 'inherit', borderColor: 'var(--border)' }} />
            </div>

            <Divider sx={{ my: 3, borderColor: 'var(--border)' }} />
            <Row label="Account">{bankName(tx.bank)}</Row>
            <Row label="Type">{tx.amt >= 0 ? 'Money in' : 'Money out'}</Row>
            <Row label="Balance after">{tx.bal == null ? '— (manual entry)' : baht(tx.bal)}</Row>
            <Divider sx={{ borderColor: 'var(--border)' }} />

            {tx.label && <p className="mt-4 text-lg font-medium">{tx.label}</p>}
            <p className="eyebrow mt-4">Description</p>
            <p className="mt-2 break-words text-sm leading-relaxed">{tx.desc}</p>
            {lateNight(tx) && <p className="mt-2 rounded-xl bg-muted/60 px-3 py-2 text-xs leading-relaxed text-muted-foreground">{LATE_NOTE}</p>}
            <button type="button" onClick={copy}
              className="mt-4 inline-flex w-fit items-center gap-2 rounded-lg border px-3 py-1.5 text-sm hover:bg-muted">
              <Copy className="size-4" />Copy description
            </button>
            <Divider sx={{ mt: 3, borderColor: 'var(--border)' }} />
            <LabelForm key={tx.date + tx.desc + tx.amt} tx={tx} />
          </div>
        )}
      </Drawer>
      <Snackbar open={!!toast} autoHideDuration={2200} onClose={() => setToast('')} message={toast} />
    </>
  )
}
