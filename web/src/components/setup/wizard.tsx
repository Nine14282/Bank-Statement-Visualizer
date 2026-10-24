import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { AnimatePresence, MotionConfig, motion } from 'motion/react'
import {
  ArrowLeft, ArrowRight, Check, CircleAlert, Eye, EyeOff, FileText, FolderOpen, GitMerge, LayoutDashboard, Loader2, LockKeyhole,
  Mail, Plus, ShieldCheck, Sparkles, Trash2, Upload, type LucideIcon,
} from 'lucide-react'
import { BankLogo, Segmented } from '@/components/ledger/widgets'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { bankName } from '@/lib/banks'
import { baht } from '@/lib/ledger'
import { expectedFor, newId, type PlanItem } from '@/lib/plan'
import { APP, EASE, HOSTED, OPEN_APP, bridge, cn } from '@/lib/utils'

// Setup: the app's first run (App.tsx, mode="setup", in the window or the browser app at ?web), Settings over the
// dashboard (onClose: no Welcome screen), or the browser's setup page alone (/?setup, welcome.py --setup).
// Add statements (mode="add") is the short version over the dashboard: no welcome or spending steps, and
// finishing leaves the saved expected spending alone.
// One screen per step, no page scroll. The server already swapped its one-time link token for an HttpOnly cookie
// (sent automatically); every call adds the X-Setup header, which other sites can't send without a CORS preflight.
const SETUP_STEPS = ['Welcome', 'Statements', 'Passwords', 'Spending', 'Finish'] as const
const ADD_STEPS = ['Statements', 'Passwords', 'Finish'] as const
type Step = (typeof SETUP_STEPS)[number]

// The app window (App.tsx shows this over the dashboard) has no server: pywebview's bridge (lib/utils.ts) calls
// workspace/app.py's Api.call with the same paths. PDFs travel base64-encoded.
const base64 = (b: Blob) => new Promise<string>((ok, fail) => {
  const r = new FileReader()
  r.onload = () => ok(String(r.result).split(',', 2)[1])
  r.onerror = () => fail(r.error)
  r.readAsDataURL(b)
})

const api: Api = async (path, body, raw = false) => {
  if (APP) {
    const [p, q] = path.split('?')
    const j = await (await bridge()).call(p, new URLSearchParams(q).get('name') ?? '', raw ? await base64(body as Blob) : body ?? null)
    if (j?.error) throw new Error(j.error)
    return j
  }
  const r = await fetch(path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { 'X-Setup': '1', ...(body === undefined ? {} : { 'Content-Type': raw ? 'application/pdf' : 'application/json' }) },
    body: body === undefined ? undefined : raw ? (body as Blob) : JSON.stringify(body),
  })
  const j = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(j.error ?? (r.status === 403 ? `This page's session ended. ${OPEN_APP}` : `Statement Visualizer stopped answering (${r.status}): was its window closed? ${OPEN_APP}`))
  return j
}

type Progress = { stage: string; done: number; total: number }   // /api/progress: what the build is doing
type BankRow = { id: string; name: string; saved: boolean }
type FileRow = { name: string; bank: string | null; locked: boolean; ok: boolean; uploaded: boolean }
// gmail: the Google keys are set; google: the Gmail settings (the secret only as saved or not); folder: the data folder
type Google = { id: string; secret: boolean; project: string; topic: string; subscription: string }
type State = { banks: BankRow[]; files: FileRow[]; plan: PlanItem[]; gmail: boolean; google: Google; folder: string }
type Api = (path: string, body?: unknown, raw?: boolean) => Promise<any>   // JSON from welcome.py; each caller reads its own fields


const primary = 'inline-flex items-center justify-center gap-2 rounded-full bg-brand px-5 py-2.5 text-sm font-medium text-white shadow-[0_8px_20px_-8px_var(--brand)] transition hover:brightness-110 active:scale-95 disabled:pointer-events-none disabled:opacity-40 disabled:shadow-none'
const ghost = 'inline-flex items-center justify-center gap-2 rounded-full border px-4 py-2.5 text-sm transition hover:bg-muted active:scale-95 disabled:opacity-40'

// mode: App.tsx says which; none = the browser's setup page. Over the dashboard (onClose, Settings) the full setup
// skips its Welcome screen.
export function Wizard({ mode, onClose }: {
  mode?: 'setup' | 'add'; onClose?: () => void
}) {
  const add = mode === 'add'
  const steps: readonly Step[] = add ? ADD_STEPS : onClose ? SETUP_STEPS.slice(1) : SETUP_STEPS
  const [step, setStep] = useState(0)
  const [st, setSt] = useState<State | null>(null)
  const [error, setError] = useState('')
  const [plan, setPlan] = useState<PlanItem[]>([])
  const [result, setResult] = useState<{ ok: boolean; log?: string; dashboard?: string } | null>(null)
  const [building, setBuilding] = useState(false)
  const [progress, setProgress] = useState<Progress>({ stage: 'start', done: 0, total: 0 })

  const refresh = useCallback(() => api('/api/state').then((s: State) => setSt(s)).catch((e) => setError(e.message)), [setError])
  useEffect(() => {
    api('/api/state').then((s: State) => { setSt(s); setPlan(s.plan ?? []) }).catch((e) => setError(e.message))
  }, [])

  const files = st?.files ?? []
  const lockedBanks = [...new Set(files.filter((f) => f.locked && f.bank).map((f) => f.bank!))]
  const [uploading, setUploading] = useState(0)
  const name = steps[step]
  // A bank is only needed to route a password: an unrecognised file that opens without one (e.g. a non-statement
  // PDF from a statement email) doesn't block, and the build just reads nothing from it.
  const canNext = name === 'Statements' ? files.length > 0 && files.every((f) => f.bank || f.ok) && !uploading
    : name === 'Passwords' ? files.every((f) => f.ok) : true
  const hint = name === 'Statements' ? (!files.length ? 'Add at least one statement to continue' : files.some((f) => !f.bank && !f.ok) ? 'Pick the bank for each locked file' : '')
    : name === 'Passwords' ? (files.some((f) => !f.ok) ? 'Unlock every bank to continue' : '')
    : name === 'Spending' ? 'Optional: you can skip this' : ''

  const go = (d: number) => { setError(''); setStep((s) => s + d) }
  // Esc goes back to the dashboard, like the Dashboard button (only over it: onClose). Not while files upload or the
  // update builds, nor after it worked (the page reloads by itself then). A popover or menu closes first: Base UI stops
  // its Esc before it reaches the window.
  const closable = !!onClose && !building && !uploading && !result?.ok
  useEffect(() => {
    if (!closable) return
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape' && !e.isComposing && !e.defaultPrevented) onClose!() }
    window.addEventListener('keydown', esc)
    return () => window.removeEventListener('keydown', esc)
  }, [closable, onClose])
  const finish = async () => {
    setBuilding(true)
    setResult(null)
    setProgress({ stage: 'start', done: 0, total: 0 })
    // The build answers only when it's done; meanwhile ask what it's doing, for the loader.
    const poll = setInterval(() => api('/api/progress').then((p: Progress) => p.stage && setProgress(p)).catch(() => {}), 300)
    try {
      const r = await api('/api/finish', add ? {} : { plan })
      clearInterval(poll)
      if (HOSTED && r.ok) {
        // The app: the loader lands on "Done", this page's content fades to its bare background, and the page reloads
        // for the new data (it's baked into the page), which then plays the dashboard's entrance.
        setProgress({ stage: 'done', done: 0, total: 0 })
        setTimeout(() => {
          for (const c of document.querySelector('[data-od-id="setup-wizard"]')?.children ?? [])
            c.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 400, easing: 'ease-out', fill: 'forwards' })
          // by the clock, not the animations' `finished` (a cancelled one never resolves): nothing can keep it here
          setTimeout(() => location.replace(APP ? '?app' : '?web'), 420)
        }, 900)
        return
      }
      setResult(r)
    }
    catch (e) { setResult({ ok: false, log: (e as Error).message }) }
    clearInterval(poll)
    setBuilding(false)
  }

  const body: ReactNode = {
    Welcome: null,   // the full-screen Hero, rendered below
    Statements: <Statements key="s" add={add} api={api} st={st} refresh={refresh} onError={setError} onBusy={setUploading} />,
    Passwords: <Passwords key="p" api={api} st={st} banks={lockedBanks} refresh={refresh} />,
    Spending: <Spending key="e" plan={plan} setPlan={setPlan} />,
    Finish: <Finish key="f" add={add} settings={!!onClose} building={building} progress={progress} result={result} retry={finish}
      api={api} st={st} refresh={refresh} onError={setError} />,
  }[name]

  if (name === 'Welcome') return <Hero onStart={() => go(1)} />

  return (
    <div className={cn('flex h-dvh flex-col overflow-hidden', onClose ? 'fixed inset-0 z-50 bg-background' : 'relative')} data-od-id="setup-wizard">
      <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
        <span className="glow -top-24 left-1/4 size-96 bg-brand" />
        <span className="glow bottom-0 right-0 size-80 bg-expense" />
      </div>

      <header className="relative flex items-center gap-3 px-4 pt-4 sm:px-8">
        <span className="grid size-10 shrink-0 place-items-center rounded-full bg-foreground text-lg text-background" aria-hidden>฿</span>
        <div className="min-w-0">
          <p className="text-sm font-medium">Statement Visualizer</p>
          <p className="text-xs text-muted-foreground">{add ? 'Add statements' : onClose ? 'Settings' : 'Setup'} · step {step + 1} of {steps.length}</p>
        </div>
        <ol className="ml-auto hidden items-center gap-1 rounded-full border bg-card p-1 md:flex" aria-label="Setup steps">
          {steps.map((s, i) => (
            <li key={s} aria-current={i === step ? 'step' : undefined}
              className={cn('relative rounded-full px-3 py-1.5 text-xs font-medium', i === step ? 'text-white' : i < step ? 'text-foreground' : 'text-muted-foreground')}>
              {i === step && <motion.span layoutId="setup-step" className="absolute inset-0 rounded-full bg-brand" transition={{ type: 'spring', stiffness: 400, damping: 32 }} />}
              <span className="relative flex items-center gap-1">{i < step && <Check className="size-3" />}{s}</span>
            </li>
          ))}
        </ol>
      </header>

      <main className="relative flex min-h-0 flex-1 items-center justify-center px-4 py-3 sm:px-8">
        <AnimatePresence mode="wait" initial={false}>
          <motion.section key={step} initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -24 }}
            transition={{ duration: 0.25, ease: EASE }} className="flex max-h-full w-full max-w-2xl min-h-0 flex-col">
            {body}
          </motion.section>
        </AnimatePresence>
      </main>

      {error && (
        <div role="alert" className="relative mx-4 mb-2 flex items-start gap-2 rounded-2xl border border-neg/40 bg-neg/10 px-4 py-2 text-sm text-neg sm:mx-8">
          <CircleAlert className="mt-0.5 size-4 shrink-0" /><span className="min-w-0 flex-1">{error}</span>
          <button type="button" onClick={() => setError('')} className="text-xs underline">Dismiss</button>
        </div>
      )}

      {!result?.ok && !building && (   // while building, the loader is the whole story
        <footer className="relative flex items-center gap-3 border-t bg-background/80 px-4 py-3 backdrop-blur sm:px-8">
          {/* over the dashboard (app window), Back on the first step returns to it */}
          <button type="button" className={ghost} onClick={() => (onClose && step === 0 ? onClose() : go(-1))}
            disabled={step === 0 && !onClose}>
            <ArrowLeft className="size-4" />{onClose && step === 0 ? 'Dashboard' : 'Back'}
          </button>
          <span className="min-w-0 flex-1 truncate text-center text-xs text-muted-foreground">{hint}</span>
          {step < steps.length - 1 ? (
            <button type="button" className={primary} disabled={!canNext} onClick={() => go(1)}>
              {name === 'Spending' && !plan.length ? 'Skip' : 'Next'}<ArrowRight className="size-4" />
            </button>
          ) : (
            <button type="button" className={primary} onClick={finish}>
              {add ? 'Update my dashboard' : 'Build my dashboard'}<ArrowRight className="size-4" />
            </button>
          )}
        </footer>
      )}
    </div>
  )
}

// A step's frame: title + subtitle, then content that may scroll inside the card (the page itself never does).
function Frame({ title, sub, children, icon }: { title: string; sub: ReactNode; children?: ReactNode; icon?: ReactNode }) {
  return (
    <Card className="flex min-h-0 flex-col gap-4 overflow-y-auto p-5 sm:p-7">
      <div className="space-y-1.5">
        {icon && <div className="mb-3 grid size-11 place-items-center rounded-2xl bg-brand/12 text-brand">{icon}</div>}
        <h1 className="text-2xl font-normal tracking-tight sm:text-3xl">{title}</h1>
        <p className="text-sm text-muted-foreground">{sub}</p>
      </div>
      {children}
    </Card>
  )
}

// Welcome: a full-screen landing hero, one big name, one line, one button.
function Hero({ onStart }: { onStart: () => void }) {
  const rise = (delay: number) => ({ initial: { opacity: 0, y: 24 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.6, delay, ease: EASE } })
  return (
    <div className="hero relative h-dvh overflow-hidden text-foreground" data-od-id="setup-hero">
      <div className="hero-glow" aria-hidden />
      <header className="absolute inset-x-0 top-0 z-10 flex items-center justify-between px-5 py-5 sm:px-10">
        <span className="flex items-center gap-2.5 text-sm font-semibold tracking-wide">
          <span className="grid size-9 place-items-center rounded-full bg-foreground text-base text-background" aria-hidden>฿</span>
          Statement Visualizer
        </span>
        <span className="flex items-center gap-1.5 text-xs text-muted-foreground"><ShieldCheck className="size-4 text-pos" />Stays on this computer</span>
      </header>
      <main className="relative z-10 grid h-full place-items-center px-6 text-center">
        <div>
          <motion.p {...rise(0)} className="text-sm font-medium uppercase tracking-[0.35em] text-muted-foreground">Welcome to</motion.p>
          <motion.h1 {...rise(0.08)} className="mt-4 font-semibold leading-[0.92] tracking-tight text-[clamp(3.25rem,13vw,9.5rem)]">
            Statement<br />Visualizer
          </motion.h1>
          <motion.p {...rise(0.16)} className="mt-6 text-lg text-muted-foreground sm:text-xl">Your bank statements, made clear.</motion.p>
          <motion.button {...rise(0.24)} type="button" onClick={onStart} autoFocus
            className="mt-10 inline-flex items-center gap-2 rounded-full bg-brand px-8 py-3.5 text-base font-semibold text-white shadow-[0_18px_40px_-12px_var(--brand)] transition-transform hover:scale-105 active:scale-95">
            Get started<ArrowRight className="size-5" />
          </motion.button>
        </div>
      </main>
      <p className="absolute inset-x-0 bottom-5 z-10 text-center text-xs text-muted-foreground">About 2 minutes · 6 short steps</p>
    </div>
  )
}

function Statements({ add, api, st, refresh, onError, onBusy }: {
  add: boolean; api: Api; st: State | null; refresh: () => Promise<void>; onError: (m: string) => void; onBusy: (n: number) => void
}) {
  const [over, setOver] = useState(false)
  const [asking, setAsking] = useState('')   // a file that was already there: removing it asks first
  const remove = async (name: string) => {
    await api('/api/remove', { name, confirm: true }).catch((x) => onError(x.message))
    setAsking('')
    refresh()
  }
  const [busy, setBusy] = useState<string[]>([])
  const addFiles = async (list: FileList | null) => {
    const pdfs = Array.from(list ?? [])
    const bad = pdfs.filter((f) => !/\.pdf$/i.test(f.name))
    if (bad.length) onError(`${bad.map((f) => f.name).join(', ')}: only PDF statements can be added.`)
    const good = pdfs.filter((f) => /\.pdf$/i.test(f.name))
    setBusy(good.map((f) => f.name))
    onBusy(good.length)
    for (const f of good) {
      try { await api(`/api/upload?name=${encodeURIComponent(f.name)}`, f, true) }
      catch (e) { onError(`${f.name}: ${(e as Error).message}`) }
    }
    setBusy([])
    onBusy(0)
    await refresh()
  }
  // The add page lists only what's new, or locked with no bank known (pick one to unlock it); the rest, including a
  // PDF that opens but isn't a statement, is summed up in one line.
  const all = st?.files ?? []
  const files = add ? all.filter((f) => f.uploaded || (!f.bank && !f.ok)) : all
  const older = all.length - files.length
  return (
    <Frame title={add ? 'Add new statements' : 'Add your statements'} icon={<Upload className="size-5" />}
      sub={add ? <>Drop the PDFs your bank sent since last time. Supported: {(st?.banks ?? []).map((b) => b.name).join(', ') || '…'}.</>
        : <>PDF statements from your bank, as many as you have. Supported: {(st?.banks ?? []).map((b) => b.name).join(', ') || '…'}.</>}>
      <label onDragOver={(e) => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); addFiles(e.dataTransfer.files) }}
        className={cn('flex cursor-pointer flex-col items-center gap-1.5 rounded-2xl border-2 border-dashed px-4 py-6 text-center transition-colors focus-within:ring-2 focus-within:ring-ring/40',
          over ? 'border-brand bg-brand/10' : 'hover:bg-muted/50')}>
        <Upload className="size-6 text-brand" />
        <span className="text-sm font-medium">Drop PDFs here, or click to choose</span>
        <span className="text-xs text-muted-foreground">They are copied into the Statement/ folder</span>
        <input type="file" accept="application/pdf,.pdf" multiple className="sr-only" onChange={(e) => { addFiles(e.target.files); e.target.value = '' }} />
      </label>
      {st?.gmail && <GmailFetch api={api} refresh={refresh} onError={onError} onBusy={onBusy} />}
      <ul className="min-h-0 divide-y overflow-y-auto rounded-2xl border" aria-label="Statements">
        {!files.length && !busy.length && <li className="px-4 py-5 text-center text-sm text-muted-foreground">{add ? 'No new statements yet.' : 'No statements yet.'}</li>}
        {files.map((f) => (
          <li key={f.name} className="flex flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2.5">
            {f.bank ? <BankLogo bank={f.bank} size={30} /> : <span className="grid size-[30px] place-items-center rounded-full bg-muted"><FileText className="size-4" /></span>}
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium" title={f.name}>{f.name}</span>
              <span className="block text-xs text-muted-foreground">
                {f.bank ? bankName(f.bank) : f.ok ? 'Not recognised as a statement (adds nothing)' : 'Bank not recognised'} · {f.locked ? (f.ok ? 'unlocked' : 'password needed') : 'no password'}
                {!f.uploaded && ' · already in Statement/'}
              </span>
            </span>
            {!f.bank && (
              <select aria-label={`Bank for ${f.name}`} defaultValue="" className="h-9 rounded-full border bg-card px-3 text-sm"
                onChange={async (e) => { await api('/api/bank', { name: f.name, bank: e.target.value }).catch((x) => onError(x.message)); refresh() }}>
                <option value="" disabled>Which bank?</option>
                {(st?.banks ?? []).map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
              </select>
            )}
            {asking !== f.name && (
              <button type="button" aria-label={`Remove ${f.name}`} className="grid size-9 place-items-center rounded-full text-muted-foreground transition hover:bg-muted hover:text-neg"
                onClick={() => (f.uploaded ? remove(f.name) : setAsking(f.name))}>
                <Trash2 className="size-4" />
              </button>
            )}
            {asking === f.name && (
              <div role="alert" className="flex w-full flex-wrap items-center gap-2 rounded-xl bg-neg/10 px-3 py-2 text-xs">
                <span className="min-w-0 flex-1">Delete this PDF from Statement/? Its transactions leave the dashboard at the next update.</span>
                <button type="button" className={cn(ghost, 'py-1.5 text-neg')} onClick={() => remove(f.name)}>Remove</button>
                <button type="button" className={cn(ghost, 'py-1.5')} onClick={() => setAsking('')}>Keep</button>
              </div>
            )}
          </li>
        ))}
        {busy.map((n) => (
          <li key={`busy-${n}`} className="flex items-center gap-3 px-3 py-2.5 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" /><span className="truncate">Adding {n}…</span>
          </li>
        ))}
      </ul>
      {older > 0 && (
        <p className="flex items-center gap-2 text-xs text-muted-foreground">
          <Check className="size-3.5 text-pos" />{older} file{older === 1 ? '' : 's'} already in Statement/ {older === 1 ? 'is' : 'are'} included too.
        </p>
      )}
    </Frame>
  )
}

// Fetch from Gmail: the Statements step, and the Gmail settings once saved. The first press signs in to Google.
function GmailFetch({ api, refresh, onError, onBusy }: {
  api: Api; refresh: () => Promise<void>; onError: (m: string) => void; onBusy?: (n: number) => void
}) {
  const [mail, setMail] = useState<'' | 'busy' | string>('')   // idle, fetching, or what it found
  const fetchMail = async () => {
    setMail('busy')
    onBusy?.(1)
    try {
      const r = await api('/api/gmail', {})
      setMail(r.files || r.notices
        ? `Gmail: ${r.files} new statement${r.files === 1 ? '' : 's'}, ${r.notices} payment notice${r.notices === 1 ? '' : 's'}.`
        : 'Gmail: nothing new.')
    }
    catch (e) { setMail(''); onError((e as Error).message) }
    onBusy?.(0)
    await refresh()
  }
  return (
    <div className="flex flex-wrap items-center gap-3">
      <button type="button" className={ghost} disabled={mail === 'busy'} onClick={fetchMail}>
        {mail === 'busy' ? <Loader2 className="size-4 animate-spin" /> : <Mail className="size-4" />}
        {mail === 'busy' ? 'Checking Gmail…' : 'Fetch from Gmail'}
      </button>
      <span className="text-xs text-muted-foreground" aria-live="polite">
        {mail === 'busy' ? 'The first time, sign in to Google in your browser.' : mail}
      </span>
    </div>
  )
}

function Passwords({ api, st, banks, refresh }: { api: Api; st: State | null; banks: string[]; refresh: () => Promise<void> }) {
  return (
    <Frame title="Unlock your statements" icon={<LockKeyhole className="size-5" />}
      sub="Banks lock statement PDFs with a password (often your birth date or ID number). Enter it once per bank.">
      {!banks.length ? (
        <p className="flex items-center gap-2 rounded-2xl border bg-muted/40 px-4 py-4 text-sm"><Check className="size-4 text-pos" />None of your statements need a password.</p>
      ) : (
        <div className="min-h-0 space-y-3 overflow-y-auto">
          {banks.map((id) => (
            <Unlock key={id} api={api} bank={id} refresh={refresh}
              files={(st?.files ?? []).filter((f) => f.bank === id && f.locked)} saved={!!st?.banks.find((b) => b.id === id)?.saved} />
          ))}
        </div>
      )}
    </Frame>
  )
}

function Unlock({ api, bank, files, saved, refresh }: { api: Api; bank: string; files: FileRow[]; saved: boolean; refresh: () => Promise<void> }) {
  const [pw, setPw] = useState('')
  const [show, setShow] = useState(false)
  const [remember, setRemember] = useState(false)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const done = files.every((f) => f.ok)
  const submit = async () => {
    setBusy(true)
    setMsg(null)
    try {
      const r = await api('/api/password', { bank, password: pw, remember })
      setMsg(r.ok ? { ok: true, text: `Opened ${r.files} file${r.files === 1 ? '' : 's'} · ${r.rows} transactions${remember ? ' · saved on this computer' : ''}` }
        : { ok: false, text: `That password doesn't open ${r.bad.join(', ')}.` })
      if (r.ok) setPw('')
      await refresh()
    } catch (e) { setMsg({ ok: false, text: (e as Error).message }) }
    setBusy(false)
  }
  return (
    <div className="rounded-2xl border p-4">
      <div className="flex items-center gap-3">
        <BankLogo bank={bank} size={34} />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">{bankName(bank)}</p>
          <p className="text-xs text-muted-foreground">{files.length} file{files.length === 1 ? '' : 's'}{done && saved && !msg ? ' · opened with your saved password' : ''}</p>
        </div>
        {done && <span className="flex items-center gap-1 rounded-full bg-pos/15 px-2.5 py-1 text-xs font-medium text-pos"><Check className="size-3.5" />Unlocked</span>}
      </div>
      {!done && (
        <form className="mt-3 space-y-2" onSubmit={(e) => { e.preventDefault(); if (pw) submit() }}>
          <div className="flex gap-2">
            <div className="relative min-w-0 flex-1">
              <Input type={show ? 'text' : 'password'} autoComplete="off" value={pw} onChange={(e) => setPw(e.target.value)}
                aria-label={`${bankName(bank)} statement password`} placeholder="Statement password" className="h-11 rounded-full pr-11" />
              <button type="button" onClick={() => setShow((v) => !v)} aria-label={show ? 'Hide password' : 'Show password'}
                className="absolute right-1 top-1/2 grid size-9 -translate-y-1/2 place-items-center rounded-full text-muted-foreground hover:text-foreground">
                {show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
              </button>
            </div>
            <button type="submit" className={primary} disabled={!pw || busy}>{busy ? <Loader2 className="size-4 animate-spin" /> : 'Unlock'}</button>
          </div>
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} className="size-4 accent-[var(--brand)]" />
            Remember on this computer (saved in .env, so updates and Gmail downloads can run on their own)
          </label>
        </form>
      )}
      {msg && <p role="status" className={cn('mt-2 text-xs', msg.ok ? 'text-pos' : 'text-neg')}>{msg.text}</p>}
    </div>
  )
}

function Spending({ plan, setPlan }: { plan: PlanItem[]; setPlan: (p: PlanItem[]) => void }) {
  const [name, setName] = useState('')
  const [amount, setAmount] = useState('')
  const [every, setEvery] = useState<PlanItem['every']>('day')
  const amt = Math.max(0, parseFloat(amount) || 0)
  const month = expectedFor(plan, 30)
  return (
    <Frame title="What do you spend regularly?" sub={<>Optional. Things you pay every day (food, fare) or every month (rent, phone) become the full bar of
      “Spent this month”. You can change them later in the Expected Spending tab.</>}>
      <form className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_7rem_auto_auto]" onSubmit={(e) => {
        e.preventDefault()
        if (!name.trim() || !amt) return
        setPlan([...plan, { id: newId(), name: name.trim(), amount: amt, every }])
        setName(''); setAmount('')
      }}>
        <Input aria-label="What" placeholder="e.g. Lunch, rent" value={name} onChange={(e) => setName(e.target.value)} className="h-10 rounded-full" />
        <Input aria-label="Amount in baht" type="number" inputMode="decimal" min={0} step="any" placeholder="฿" value={amount}
          onChange={(e) => setAmount(e.target.value)} className="num h-10 rounded-full text-right" />
        <Segmented label="How often" value={every} onChange={setEvery} options={[{ value: 'day', label: 'Daily' }, { value: 'month', label: 'Monthly' }]} />
        <button type="submit" className={cn(primary, 'px-4')} disabled={!name.trim() || !amt}><Plus className="size-4" />Add</button>
      </form>
      <ul className="min-h-0 divide-y overflow-y-auto rounded-2xl border" aria-label="Regular spending">
        {!plan.length && <li className="px-4 py-5 text-center text-sm text-muted-foreground">Nothing yet. That's fine: you can skip this step.</li>}
        {plan.map((i) => (
          <li key={i.id} className="flex items-center gap-3 px-3 py-2">
            <span className="min-w-0 flex-1 truncate text-sm" title={i.name}>{i.name}</span>
            <span className="num text-sm">{baht(i.amount)} <span className="text-muted-foreground">/ {i.every === 'day' ? 'day' : 'month'}</span></span>
            <button type="button" aria-label={`Remove ${i.name}`} onClick={() => setPlan(plan.filter((x) => x.id !== i.id))}
              className="grid size-9 place-items-center rounded-full text-muted-foreground transition hover:bg-muted hover:text-neg"><Trash2 className="size-4" /></button>
          </li>
        ))}
      </ul>
      {plan.length > 0 && <p className="text-sm text-muted-foreground">About <b className="num text-foreground">{baht(month)}</b> a month.</p>}
    </Frame>
  )
}

function Finish({ add, settings, building, progress, result, retry, api, st, refresh, onError }: {
  add: boolean; settings: boolean; building: boolean; progress: Progress; result: { ok: boolean; log?: string; dashboard?: string } | null
  retry: () => void; api: Api; st: State | null; refresh: () => Promise<void>; onError: (m: string) => void
}) {
  if (building) {
    return (
      <Frame title={add ? 'Updating your dashboard' : 'Building your dashboard'} sub="">
        <Loader p={progress} />
      </Frame>
    )
  }
  if (result?.ok) {
    return (
      <Frame title="Your dashboard is ready" icon={<Check className="size-5" />}
        sub="It is opening in a new browser tab. You can close this one; the setup server has stopped.">
        <p className="rounded-2xl border bg-muted/40 px-4 py-3 text-sm">
          Next time, open Statement Visualizer again to add new statements. {OPEN_APP}
          The dashboard is the file <code className="num break-all">{result.dashboard}</code>.
        </p>
      </Frame>
    )
  }
  if (result && !result.ok) {
    return (
      <Frame title="The build didn't finish" icon={<CircleAlert className="size-5" />}
        sub="Your choices are saved. Fix the problem below (often a missing password: go Back), then try again.">
        <pre className="num min-h-0 overflow-auto whitespace-pre-wrap rounded-2xl border bg-muted/40 p-3 text-xs">{result.log}</pre>
        <button type="button" className={cn(primary, 'self-start')} onClick={retry}>Try again</button>
      </Frame>
    )
  }
  if (add) {
    return (
      <Frame title="Ready to update" icon={<Check className="size-5" />}
        sub="Reads every statement in Statement/, new ones included, and rebuilds your dashboard.">
        <p className="rounded-2xl border bg-muted/40 px-4 py-3 text-sm text-muted-foreground">
          Tired of adding statements by hand? Statement Visualizer can fetch them from Gmail: the last step of the
          app's Settings shows how.
        </p>
        <p className="text-xs text-muted-foreground">Press “Update my dashboard” when you are ready.</p>
      </Frame>
    )
  }
  return (
    <Frame title={settings ? 'Gmail and your data' : 'Last thing: statements by email'} icon={<Mail className="size-5" />}
      sub="Gmail is optional, and you can set it up any time. Banks email statements; Statement Visualizer can fetch them from Gmail by itself (read-only).">
      <div className="min-h-0 space-y-4 overflow-y-auto">
        <GmailSettings api={api} st={st} refresh={refresh} onError={onError} />
        {settings && st && <YourData api={api} folder={st.folder} onError={onError} />}
      </div>
      <p className="text-xs text-muted-foreground">Press “Build my dashboard” when you are ready.</p>
    </Frame>
  )
}

// Gmail settings, saved into the settings file (welcome.py /api/google). Each field shows what is saved until edited;
// the secret never comes back to the page, a blank one keeps the saved one.
const GMAIL_STEPS: [string, ReactNode][] = [
  ['Google Cloud', <>In <b>console.cloud.google.com</b> create a project and enable the <b>Gmail API</b>.</>],
  ['Consent screen', <>Choose <b>External</b> and add your own Gmail as a test user.</>],
  ['Credentials', <>Create an <b>OAuth client ID</b> of type <b>Desktop app</b>, then paste its ID and secret below and save.</>],
  ['Sign in', <>Press <b>Fetch from Gmail</b> and sign in once. From then on the app checks Gmail each time it opens.</>],
]

function GmailSettings({ api, st, refresh, onError }: {
  api: Api; st: State | null; refresh: () => Promise<void>; onError: (m: string) => void
}) {
  const [typed, setTyped] = useState<Partial<Record<keyof Google, string>>>({})
  const [busy, setBusy] = useState(false)
  const [saved, setSaved] = useState(false)
  const [shown, setShown] = useState(false)
  const value = (k: keyof Google) => typed[k] ?? (k === 'secret' ? '' : st?.google?.[k] || '')
  const field = (k: keyof Google, label: string, placeholder = '') => (
    <label className="block space-y-1">
      <span className="text-xs text-muted-foreground">{label}</span>
      <Input type={k === 'secret' || !shown ? 'password' : 'text'} autoComplete="off" spellCheck={false} value={value(k)} placeholder={placeholder}
        onChange={(e) => { setTyped((t) => ({ ...t, [k]: e.target.value })); setSaved(false) }} className="h-10 rounded-xl" />
    </label>
  )
  const save = async () => {
    setBusy(true)
    try {
      await api('/api/google', Object.fromEntries((['id', 'secret', 'project', 'topic', 'subscription'] as const).map((k) => [k, value(k)])))
      setTyped({})
      setSaved(true)
      await refresh()
    } catch (e) { onError((e as Error).message) }
    setBusy(false)
  }
  return (
    <section className="space-y-3" data-od-id="gmail-settings">
      <ol className="space-y-2">
        {GMAIL_STEPS.map(([t, text], i) => (
          <li key={t} className="flex gap-3 rounded-2xl border px-3 py-2.5">
            <span className="grid size-6 shrink-0 place-items-center rounded-full bg-brand/15 text-xs font-semibold text-brand">{i + 1}</span>
            <p className="text-sm"><b className="font-medium">{t}.</b> <span className="text-muted-foreground">{text}</span></p>
          </li>
        ))}
      </ol>
      <form className="space-y-3 rounded-2xl border p-4" onSubmit={(e) => { e.preventDefault(); save() }}>
        <div className="grid gap-3 sm:grid-cols-2">
          {field('id', 'Client ID', '….apps.googleusercontent.com')}
          {field('secret', 'Client secret', st?.google?.secret ? 'Saved (leave blank to keep it)' : '')}
        </div>
        <details className="group">
          <summary className="cursor-pointer text-xs text-muted-foreground">Real time (optional): new mail within seconds while the app is open</summary>
          <p className="mt-2 text-xs text-muted-foreground">
            Needs a Pub/Sub topic and pull subscription in the same Google Cloud project (README, “Real time”, steps 1–5).
            Leave these blank to keep it off.
          </p>
          <div className="mt-2 grid gap-3 sm:grid-cols-3">
            {field('project', 'Project ID')}
            {field('topic', 'Topic')}
            {field('subscription', 'Subscription')}
          </div>
        </details>
        <div className="flex flex-wrap items-center gap-3">
          <button type="submit" className={ghost} disabled={busy || !value('id')}>
            {busy ? <Loader2 className="size-4 animate-spin" /> : <Check className="size-4" />}Save Gmail settings
          </button>
          {saved && <span role="status" className="text-xs text-pos">Saved.</span>}
          <Reveal what="the Gmail settings" shown={shown} onShown={setShown} />
        </div>
      </form>
      {st?.gmail && <GmailFetch api={api} refresh={refresh} onError={onError} />}
    </section>
  )
}

// Account details (Gmail keys, the folder path, which names the user) show as dots until asked for, and the asking is
// confirmed: Settings may be open while someone else sees the screen.
function Reveal({ what, shown, onShown }: { what: string; shown: boolean; onShown: (v: boolean) => void }) {
  const [asking, setAsking] = useState(false)
  if (shown) return <button type="button" className={ghost} onClick={() => onShown(false)}><EyeOff className="size-4" />Hide</button>
  if (!asking) return <button type="button" className={ghost} onClick={() => setAsking(true)}><Eye className="size-4" />Show</button>
  return (
    <span role="alert" className="flex flex-wrap items-center gap-2 text-xs">
      Show {what} on screen?
      <button type="button" className={cn(ghost, 'py-1.5')} onClick={() => { setAsking(false); onShown(true) }}>Show</button>
      <button type="button" className={cn(ghost, 'py-1.5')} onClick={() => setAsking(false)}>Cancel</button>
    </span>
  )
}

// Settings only: the data folder, and deleting everything (welcome.py /api/clear, launcher.py clear). After a delete
// the app closes (the window, or the browser app's server); this page clears what it saved in the browser itself.
function YourData({ api, folder, onError }: { api: Api; folder: string; onError: (m: string) => void }) {
  const [asking, setAsking] = useState(false)
  const [typed, setTyped] = useState('')
  const [busy, setBusy] = useState(false)
  const [gone, setGone] = useState(false)
  const [shown, setShown] = useState(false)
  const wipe = async () => {
    setBusy(true)
    try {
      await api('/api/clear', { confirm: typed })
      localStorage.clear()   // labels, expected spending, theme, seen rows
      setGone(true)
    } catch (e) { onError((e as Error).message) }
    setBusy(false)
  }
  if (gone) {
    return (
      <p role="status" className="rounded-2xl border bg-muted/40 px-4 py-4 text-sm">
        Everything is deleted. Statement Visualizer closes now; open it again to start fresh.
      </p>
    )
  }
  return (
    <section className="space-y-3 rounded-2xl border p-4" data-od-id="your-data">
      <div>
        <p className="text-sm font-medium">Your data</p>
        <p className="text-xs text-muted-foreground">Statements, ledger and settings stay on this computer, in <span className="num break-all">{shown ? folder : '••••••••••••'}</span></p>
      </div>
      <div className="flex flex-wrap gap-2">
        <button type="button" className={ghost} onClick={() => api('/api/folder', {}).catch((e) => onError(e.message))}>
          <FolderOpen className="size-4" />Open data folder
        </button>
        {!asking && (
          <button type="button" className={cn(ghost, 'text-neg')} onClick={() => setAsking(true)}>
            <Trash2 className="size-4" />Delete all my data…
          </button>
        )}
        <Reveal what="the folder path" shown={shown} onShown={setShown} />
      </div>
      {asking && (
        <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); if (typed === 'DELETE') wipe() }}>
          <p className="text-xs text-neg">
            Deletes your statement PDFs, the ledger, expected spending, labels, saved passwords and the Gmail login. This
            cannot be undone. Type DELETE to confirm.
          </p>
          <div className="flex gap-2">
            <Input value={typed} onChange={(e) => setTyped(e.target.value)} aria-label="Type DELETE to confirm" autoComplete="off"
              className="h-10 min-w-0 flex-1 rounded-xl" />
            <button type="submit" className={cn(primary, 'bg-neg shadow-none')} disabled={typed !== 'DELETE' || busy}>
              {busy ? <Loader2 className="size-4 animate-spin" /> : 'Delete'}
            </button>
            <button type="button" className={ghost} onClick={() => { setAsking(false); setTyped('') }}>Cancel</button>
          </div>
        </form>
      )}
    </section>
  )
}

// What the build is doing, in a word or two. `at` = how full the ring is (reading fills it from 6% to 76% by file).
const STAGES: Record<string, { label: string; icon: LucideIcon; at: number }> = {
  start: { label: 'Starting', icon: Sparkles, at: 0.04 },
  read: { label: 'Reading statements', icon: FileText, at: 0.06 },
  merge: { label: 'Merging', icon: GitMerge, at: 0.84 },
  build: { label: 'Building dashboard', icon: LayoutDashboard, at: 0.94 },
  done: { label: 'Done', icon: Check, at: 1 },
}

// The build's loader: a ring that fills as statements are read, the stage's icon, a short label.
// reducedMotion "never": it is progress feedback, so it moves even when the OS asks for reduced motion.
function Loader({ p }: { p: Progress }) {
  const s = STAGES[p.stage] ?? STAGES.start
  const fill = p.stage === 'read' && p.total ? s.at + 0.7 * (p.done / p.total) : s.at
  const done = p.stage === 'done'
  const Icon = s.icon
  return (
    <MotionConfig reducedMotion="never">
      <div className="flex flex-col items-center gap-5 py-6" role="status" aria-live="polite">
        <div className="relative size-32">
          <svg viewBox="0 0 120 120" className="absolute inset-0 size-full -rotate-90" aria-hidden>
            <circle cx="60" cy="60" r="52" fill="none" stroke="var(--muted)" strokeWidth="6" />
            <motion.circle cx="60" cy="60" r="52" fill="none" strokeWidth="6" strokeLinecap="round"
              className={cn('transition-[stroke] duration-500', done ? 'stroke-pos' : 'stroke-brand')}
              initial={{ pathLength: 0 }} animate={{ pathLength: fill }} transition={{ duration: 0.6, ease: EASE }} />
          </svg>
          {!done && (
            <motion.span className="absolute -inset-2 rounded-full border-2 border-transparent border-t-brand/50" aria-hidden
              animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1.4, ease: 'linear' }} />
          )}
          <AnimatePresence mode="popLayout" initial={false}>
            <motion.span key={p.stage} className="absolute inset-0 grid place-items-center" aria-hidden
              initial={{ opacity: 0, scale: 0.6 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.6 }}
              transition={{ type: 'spring', stiffness: 380, damping: 26 }}>
              <Icon className={cn('size-9', done ? 'text-pos' : 'text-brand')} />
            </motion.span>
          </AnimatePresence>
        </div>
        <div className="h-12 text-center">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div key={s.label} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.2, ease: EASE }}>
              <p className="text-lg font-medium">{s.label}</p>
              {p.stage === 'read' && p.total > 0 && <p className="num text-xs text-muted-foreground">{p.done} / {p.total}</p>}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </MotionConfig>
  )
}
