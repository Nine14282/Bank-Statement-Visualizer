import { motion } from 'motion/react'
import { Bell, CircleCheck, Download, Moon, Settings, Sun, Upload } from 'lucide-react'
import { Tip } from '@/components/ledger/info'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { SECTIONS, goTo, type Tab } from '@/lib/nav'
import { THEMES, type useTheme } from '@/lib/themes'
import { META, bankName, baht, toCsv, type Tx } from '@/lib/ledger'
import { APP, OPEN_APP, bridge, cn } from '@/lib/utils'

// Icon nav: a floating vertical rail on desktop, a bottom bar on phones. The lit pill slides between items.
export function Nav({ active, mobile }: { active: string; mobile?: boolean }) {
  return (
    <nav aria-label="Sections" data-od-id={mobile ? 'bottom-nav' : 'sidebar'}
      className={cn('fixed z-40 flex gap-1.5 rounded-full border bg-card/85 p-1.5 shadow-[0_12px_32px_-12px_rgb(0_0_0/0.3)] backdrop-blur-md',
        mobile ? 'bottom-3 left-1/2 -translate-x-1/2 md:hidden' : 'left-4 top-1/2 hidden -translate-y-1/2 flex-col md:flex')}>
      {SECTIONS.map((s) => {
        const on = active === s.id
        return (
          <Tip key={s.id} label={s.label} side={mobile ? 'top' : 'right'}>
            <button type="button" onClick={() => goTo(s.id)} aria-label={s.label} aria-current={on ? 'location' : undefined}
              className={cn('relative grid size-11 place-items-center rounded-full transition-colors duration-300',
                on ? 'text-white' : 'text-muted-foreground hover:bg-muted hover:text-foreground')}>
              {on && <span className="absolute inset-0 rounded-full bg-brand shadow-[0_8px_20px_-6px_var(--brand)]" />}
              <s.icon className="relative size-[18px]" />
            </button>
          </Tip>
        )
      })}
    </nav>
  )
}

// In the app window a page download goes nowhere (pywebview turns them off): app.py asks where to save it instead.
async function download(rows: Tx[], name: string) {
  if (APP) return void (await bridge()).save(name, toCsv(rows))
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([toCsv(rows)], { type: 'text/csv;charset=utf-8' }))
  a.download = name
  a.click()
  setTimeout(() => URL.revokeObjectURL(a.href), 1000)
}

// Top-bar popovers share one card look (sideOffset 8 on each).
const POP = 'block max-w-[calc(100vw-24px)] rounded-[18px] border p-4 ring-0'
// Round icon buttons in the top bar.
const ICON = 'grid size-11 place-items-center rounded-full border bg-card text-muted-foreground transition hover:bg-muted hover:text-foreground'

// "Add statements": in the app window (workspace/app.py) it opens the add page over the dashboard (onAdd, App.tsx;
// the window's Python reads and saves the PDFs). In a browser this dashboard is a file, which can't save PDFs or read
// them, so it sends people to the app; this page reloads itself after the update.
function AddStatements({ onAdd }: { onAdd?: () => void }) {
  const cls = 'flex h-11 items-center gap-2 rounded-full bg-brand px-3.5 text-sm font-medium text-white shadow-[0_8px_20px_-8px_var(--brand)] transition hover:brightness-110 active:scale-95 sm:px-4'
  const face = <><Upload className="size-4" /><span className="hidden sm:inline">Add statements</span></>
  if (onAdd) return <button type="button" aria-label="Add statements" onClick={onAdd} data-od-id="add-statements" className={cls}>{face}</button>
  return (
    <Popover>
      <PopoverTrigger aria-label="Add statements" data-od-id="add-statements" className={cls}>{face}</PopoverTrigger>
      <PopoverContent align="end" sideOffset={8} className={cn(POP, 'w-[380px]')}>
        <p className="eyebrow mb-2">Add statements</p>
        <p className="text-sm text-muted-foreground">
          Got a new statement PDF from your bank? Add it in the app: press Add statements there, drop the PDF and type
          its password. This dashboard then updates by itself.
        </p>
        <p className="mt-3 text-sm">{OPEN_APP}</p>
        <p className="mt-3 text-xs text-muted-foreground">
          Rather have them added automatically? The app can fetch statements from Gmail: the last step of its Settings
          shows how.
        </p>
      </PopoverContent>
    </Popover>
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
            {on && <span className="absolute inset-0 rounded-full bg-brand shadow-[0_6px_16px_-6px_var(--brand)]" />}
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
  const g = META.gaps
  const issues = g.months.length + g.breaks.length
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
          <Tip label="Settings">
            <button type="button" aria-label="Settings" onClick={onSettings} className={ICON} data-od-id="settings"><Settings className="size-[18px]" /></button>
          </Tip>
        )}
        <Popover>
          <Tip label={issues ? `${issues} coverage issue${issues > 1 ? 's' : ''}` : 'Coverage OK'}>
            <PopoverTrigger aria-label="Data coverage" className={cn(ICON, 'relative')} data-od-id="coverage-status">
              <Bell className="size-[18px]" />
              {issues > 0 && <span className="absolute right-2.5 top-2.5 size-2 rounded-full bg-neg ring-2 ring-card" />}
            </PopoverTrigger>
          </Tip>
          <PopoverContent align="end" sideOffset={8} className={cn(POP, 'w-[340px]')}>
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
          </PopoverContent>
        </Popover>
        <Tip label={`Theme: ${theme.label}. Switch to ${next.label}`}>
          <button type="button" aria-label={`Switch to the ${next.label} theme`} onClick={() => pickTheme(next.id)} className={ICON}>
            <motion.span key={theme.id} initial={{ rotate: -90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} className="grid">
              {next.mode === 'light' ? <Sun className="size-[18px]" /> : <Moon className="size-[18px]" />}
            </motion.span>
          </button>
        </Tip>
        {META.name && (
          <Tip label={[META.account, META.name].filter(Boolean).join(' · ')}>
            <span className="grid size-11 select-none place-items-center rounded-full bg-brand text-[15px] font-semibold text-white">{initials(META.name)}</span>
          </Tip>
        )}
      </div>
    </header>
  )
}
