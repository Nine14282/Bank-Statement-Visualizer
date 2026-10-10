import { useState } from 'react'
import Avatar from '@mui/material/Avatar'
import Badge from '@mui/material/Badge'
import IconButton from '@mui/material/IconButton'
import Popover from '@mui/material/Popover'
import MuiTooltip from '@mui/material/Tooltip'
import { motion } from 'motion/react'
import { Bell, Check, CircleCheck, Copy, Download, Moon, Settings, Sun, Upload } from 'lucide-react'
import { SECTIONS, goTo, type Tab } from '@/lib/nav'
import { THEMES, type useTheme } from '@/lib/themes'
import { META, bankName, baht, toCsv, type Tx } from '@/lib/ledger'
import { cn } from '@/lib/utils'

// Icon nav: a floating vertical rail on desktop, a bottom bar on phones. The lit pill slides between items.
export function Nav({ active, mobile }: { active: string; mobile?: boolean }) {
  return (
    <nav aria-label="Sections" data-od-id={mobile ? 'bottom-nav' : 'sidebar'}
      className={cn('fixed z-40 flex gap-1.5 rounded-full border bg-card/85 p-1.5 shadow-[0_12px_32px_-12px_rgb(0_0_0/0.3)] backdrop-blur-md',
        mobile ? 'bottom-3 left-1/2 -translate-x-1/2 md:hidden' : 'left-4 top-1/2 hidden -translate-y-1/2 flex-col md:flex')}>
      {SECTIONS.map((s) => {
        const on = active === s.id
        return (
          <MuiTooltip key={s.id} title={s.label} placement={mobile ? 'top' : 'right'} arrow>
            <button type="button" onClick={() => goTo(s.id)} aria-label={s.label} aria-current={on ? 'location' : undefined}
              className={cn('relative grid size-11 place-items-center rounded-full transition-colors duration-300',
                on ? 'text-white' : 'text-muted-foreground hover:bg-muted hover:text-foreground')}>
              {on && <motion.span layoutId={mobile ? 'nav-pill-m' : 'nav-pill'} transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                className="absolute inset-0 rounded-full bg-brand shadow-[0_8px_20px_-6px_var(--brand)]" />}
              <s.icon className="relative size-[18px]" />
            </button>
          </MuiTooltip>
        )
      })}
    </nav>
  )
}

function download(rows: Tx[], name: string) {
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([toCsv(rows)], { type: 'text/csv;charset=utf-8' }))
  a.download = name
  a.click()
  setTimeout(() => URL.revokeObjectURL(a.href), 1000)
}

// Top-bar popovers share one card look.
const POP = { mt: 1, maxWidth: 'calc(100vw - 24px)', p: 2, borderRadius: '18px', bgcolor: 'var(--popover)',
  color: 'var(--popover-foreground)', border: '1px solid var(--border)' }

// The command to add statements. Opened from disk (file:///…/web/dist/index.html), the project folder is in this
// page's own address, so the hint says exactly what to type; anywhere else (dev server, a WSL host) just ./run.sh.
const runCmd = () => {
  const p = decodeURIComponent(location.pathname)
  const end = /\/web\/dist\/index\.html$/
  if (location.protocol !== 'file:' || location.host || !end.test(p)) return './run.sh'
  return `cd '${p.replace(end, '').replace(/'/g, `'\\''`)}' && ./run.sh`
}

// "Add statements": in the app window (workspace/app.py) it opens the add page over the dashboard (onAdd, App.tsx;
// the window's Python reads and saves the PDFs). In a browser this dashboard is a file, which can't save PDFs or read
// them, so it says what to run: ./run.sh opens the add page, and this page reloads itself after the update.
function AddStatements({ onAdd }: { onAdd?: () => void }) {
  const [at, setAt] = useState<HTMLElement | null>(null)
  const [copied, setCopied] = useState(false)
  const cmd = runCmd()
  const copy = async () => {
    try { await navigator.clipboard.writeText(cmd); setCopied(true) } catch { /* no clipboard here: the text is selectable */ }
  }
  return (
    <>
      <button type="button" aria-label="Add statements" aria-haspopup={onAdd ? undefined : 'dialog'}
        onClick={(e) => { if (onAdd) return onAdd(); setCopied(false); setAt(e.currentTarget) }}
        data-od-id="add-statements"
        className="flex h-11 items-center gap-2 rounded-full bg-brand px-3.5 text-sm font-medium text-white shadow-[0_8px_20px_-8px_var(--brand)] transition hover:brightness-110 active:scale-95 sm:px-4">
        <Upload className="size-4" /><span className="hidden sm:inline">Add statements</span>
      </button>
      <Popover open={!!at} anchorEl={at} onClose={() => setAt(null)} anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }} slotProps={{ paper: { sx: { ...POP, width: 380 } } }}>
        <p className="eyebrow mb-2">Add statements</p>
        <p className="text-sm text-muted-foreground">
          Got a new statement PDF from your bank? Run this in a terminal. A page opens where you drop the PDF and type its
          password, then this dashboard updates by itself.
        </p>
        <div className="mt-3 flex items-center gap-2 rounded-xl border bg-muted/50 p-1.5 pl-3">
          <code className="num min-w-0 flex-1 select-all break-all text-xs">{cmd}</code>
          <button type="button" onClick={copy} aria-label="Copy command"
            className="grid size-9 shrink-0 place-items-center rounded-lg text-muted-foreground transition hover:bg-muted hover:text-foreground">
            {copied ? <Check className="size-4 text-pos" /> : <Copy className="size-4" />}
          </button>
          <span role="status" className="sr-only">{copied ? 'Command copied' : ''}</span>
        </div>
        <p className="mt-3 text-xs text-muted-foreground">
          Rather have them added automatically? <code className="num">./gmail.sh</code> fetches statements from Gmail
          (README, “Option 2”).
        </p>
      </Popover>
    </>
  )
}

const initials = (s: string) => s.split(/\s+/).filter((w) => !/^(mr|mrs|ms|miss)\.?$/i.test(w)).slice(0, 2).map((w) => w[0]).join('').toUpperCase()

// `short` is shown below lg, where three full labels don't fit beside the buttons.
const TABS: { id: Tab; label: string; short: string }[] = [
  { id: 'dashboard', label: 'Dashboard', short: 'Dashboard' },
  { id: 'plan', label: 'Expected Spending', short: 'Expected' },
  { id: 'custom', label: 'Custom Your Transaction', short: 'Custom' },
]

// Top-level page tabs; the lit pill slides between them. Wraps onto its own row on phones.
function Tabs({ tab, onTab }: { tab: Tab; onTab: (t: Tab) => void }) {
  return (
    <nav aria-label="Pages" data-od-id="top-tabs"
      className="order-last flex w-full gap-1 rounded-full border bg-card p-1 shadow-sm md:order-none md:w-auto">
      {TABS.map((t) => {
        const on = t.id === tab
        return (
          <button key={t.id} type="button" aria-current={on ? 'page' : undefined} onClick={() => onTab(t.id)}
            aria-label={t.label} className={cn('relative flex-1 rounded-full px-3 py-2 text-sm sm:px-4 font-medium whitespace-nowrap transition-colors duration-300 md:flex-none',
              on ? 'text-white' : 'text-muted-foreground hover:text-foreground')}>
            {on && <motion.span layoutId="top-tab" transition={{ type: 'spring', stiffness: 400, damping: 32 }}
              className="absolute inset-0 rounded-full bg-brand shadow-[0_6px_16px_-6px_var(--brand)]" />}
            <span className="relative lg:hidden">{t.short}</span>
            <span className="relative hidden lg:inline">{t.label}</span>
          </button>
        )
      })}
    </nav>
  )
}

export function TopBar({ rows, year, tab, onTab, theme: [theme, pickTheme], onAdd, onSettings }: {
  rows: Tx[]; year: string; tab: Tab; onTab: (t: Tab) => void; theme: ReturnType<typeof useTheme>; onAdd?: () => void
  onSettings?: () => void   // app window only: the full setup again (theme, expected spending, passwords)
}) {
  // the button steps to the next theme in the registry (with two themes: light <-> dark)
  const next = THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length]
  const [bell, setBell] = useState<HTMLElement | null>(null)
  const g = META.gaps
  const issues = g.months.length + g.breaks.length
  const icon = { color: 'var(--muted-foreground)', border: '1px solid var(--border)', bgcolor: 'var(--card)', width: 44, height: 44,
    '&:hover': { bgcolor: 'var(--muted)', color: 'var(--foreground)' } }
  return (
    <header data-od-id="topbar"
      className="sticky top-0 z-30 flex flex-wrap items-center gap-3 border-b border-transparent bg-background/80 px-4 py-3 backdrop-blur-md sm:px-6 md:flex-nowrap md:pl-24 lg:pr-8">
      <span className="grid size-11 shrink-0 place-items-center rounded-full bg-foreground text-lg text-background md:absolute md:left-4" aria-hidden>฿</span>
      <Tabs tab={tab} onTab={onTab} />
      <div className="ml-auto flex shrink-0 items-center gap-2">
        <AddStatements onAdd={onAdd} />
        <button type="button" onClick={() => download(rows, `ledger-${year}.csv`)}
          className="hidden h-11 items-center gap-2 rounded-full border bg-card px-4 text-sm font-medium transition hover:bg-muted active:scale-95 sm:flex">
          <Download className="size-4" />Export CSV
        </button>
        {onSettings && (
          <MuiTooltip title="Settings">
            <IconButton aria-label="Settings" onClick={onSettings} sx={icon} data-od-id="settings"><Settings className="size-[18px]" /></IconButton>
          </MuiTooltip>
        )}
        <MuiTooltip title={issues ? `${issues} coverage issue${issues > 1 ? 's' : ''}` : 'Coverage OK'}>
          <IconButton aria-label="Data coverage" onClick={(e) => setBell(e.currentTarget)} sx={icon} data-od-id="coverage-status">
            <Badge color="error" variant="dot" invisible={!issues} overlap="circular"><Bell className="size-[18px]" /></Badge>
          </IconButton>
        </MuiTooltip>
        <Popover open={!!bell} anchorEl={bell} onClose={() => setBell(null)} anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
          transformOrigin={{ vertical: 'top', horizontal: 'right' }}
          slotProps={{ paper: { sx: { ...POP, width: 340 } } }}>
          <p className="eyebrow mb-2">Data coverage</p>
          {!issues && <p className="flex items-center gap-2 text-sm text-pos"><CircleCheck className="size-4" />No gaps — every month and balance lines up.</p>}
          <ul className="space-y-2 text-sm">
            {g.months.length > 0 && <li><b>No records:</b> {g.months.join(', ')}</li>}
            {g.breaks.map((b) => (
              <li key={b.after + b.before}>
                <b>{b.bank && `${bankName(b.bank)} `}{b.after.slice(0, 10)} → {b.before.slice(0, 10)}</b>: balance moved{' '}
                <span className="num">{b.missing > 0 ? '+' : '−'}{baht(b.missing)}</span> with no matching rows
              </li>
            ))}
          </ul>
        </Popover>
        <MuiTooltip title={`Theme: ${theme.label}. Switch to ${next.label}`}>
          <IconButton aria-label={`Switch to the ${next.label} theme`} onClick={() => pickTheme(next.id)} sx={icon}>
            <motion.span key={theme.id} initial={{ rotate: -90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} className="grid">
              {next.mode === 'light' ? <Sun className="size-[18px]" /> : <Moon className="size-[18px]" />}
            </motion.span>
          </IconButton>
        </MuiTooltip>
        {META.name && (
          <MuiTooltip title={[META.account, META.name].filter(Boolean).join(' · ')}>
            <Avatar sx={{ width: 44, height: 44, fontSize: 15, fontWeight: 600, color: '#fff',
              background: 'var(--brand)' }}>{initials(META.name)}</Avatar>
          </MuiTooltip>
        )}
      </div>
    </header>
  )
}
