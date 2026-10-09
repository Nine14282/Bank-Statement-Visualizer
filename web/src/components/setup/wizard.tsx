import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import {
  ArrowLeft, ArrowRight, Check, CircleAlert, Eye, EyeOff, FileText, Loader2, LockKeyhole, Mail,
  Plus, ShieldCheck, Trash2, Upload,
} from 'lucide-react'
import { BankLogo, Segmented } from '@/components/ledger/widgets'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { bankName } from '@/lib/banks'
import { baht } from '@/lib/ledger'
import { newId, type PlanItem } from '@/lib/plan'
import { THEMES, type useTheme } from '@/lib/themes'
import { EASE, cn } from '@/lib/utils'

// First-run setup, shown when ./run.sh's local server (workspace/welcome.py) opens the page at /?setup.
// Later runs open the short "add statements" version at /?setup&add (welcome.py --add): no welcome, theme or
// spending steps, and finishing leaves the saved theme and expected spending alone.
// One screen per step, no page scroll. The server already swapped its one-time link token for an HttpOnly cookie
// (sent automatically); every call adds the X-Setup header, which other sites can't send without a CORS preflight.
const ADD = new URLSearchParams(location.search).has('add')
const STEPS = ADD ? ['Statements', 'Passwords', 'Finish'] as const : ['Welcome', 'Statements', 'Passwords', 'Theme', 'Spending', 'Finish'] as const

const api: Api = async (path, body, raw = false) => {
  const r = await fetch(path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { 'X-Setup': '1', ...(body === undefined ? {} : { 'Content-Type': raw ? 'application/pdf' : 'application/json' }) },
    body: body === undefined ? undefined : raw ? (body as Blob) : JSON.stringify(body),
  })
  const j = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(j.error ?? (r.status === 403 ? `This page's session ended. Run ${ADD ? './run.sh' : './run.sh --setup'} again.` : `The setup server answered ${r.status}. Is ./run.sh still running?`))
  return j
}

type BankRow = { id: string; name: string; saved: boolean }
type FileRow = { name: string; bank: string | null; locked: boolean; ok: boolean; uploaded: boolean }
type State = { banks: BankRow[]; files: FileRow[]; theme: string; plan: PlanItem[] }
type Api = (path: string, body?: unknown, raw?: boolean) => Promise<any>   // JSON from welcome.py; each caller reads its own fields


const primary = 'inline-flex items-center justify-center gap-2 rounded-full bg-brand px-5 py-2.5 text-sm font-medium text-white shadow-[0_8px_20px_-8px_var(--brand)] transition hover:brightness-110 active:scale-95 disabled:pointer-events-none disabled:opacity-40 disabled:shadow-none'
const ghost = 'inline-flex items-center justify-center gap-2 rounded-full border px-4 py-2.5 text-sm transition hover:bg-muted active:scale-95 disabled:opacity-40'

export function Wizard({ theme: [theme, pickTheme] }: { theme: ReturnType<typeof useTheme> }) {
  const [step, setStep] = useState(0)
  const [st, setSt] = useState<State | null>(null)
  const [error, setError] = useState('')
  const [plan, setPlan] = useState<PlanItem[]>([])
  const [result, setResult] = useState<{ ok: boolean; log?: string; dashboard?: string } | null>(null)
  const [building, setBuilding] = useState(false)

  const refresh = useCallback(() => api('/api/state').then((s: State) => setSt(s)).catch((e) => setError(e.message)), [])
  useEffect(() => {
    api('/api/state').then((s: State) => { setSt(s); setPlan(s.plan ?? []) }).catch((e) => setError(e.message))
  }, [])

  const files = st?.files ?? []
  const lockedBanks = [...new Set(files.filter((f) => f.locked && f.bank).map((f) => f.bank!))]
  const [uploading, setUploading] = useState(0)
  const name = STEPS[step]
  // A bank is only needed to route a password: an unrecognised file that opens without one (e.g. a non-statement
  // PDF from a statement email) doesn't block, and the build just reads nothing from it.
  const canNext = name === 'Statements' ? files.length > 0 && files.every((f) => f.bank || f.ok) && !uploading
    : name === 'Passwords' ? files.every((f) => f.ok) : true
  const hint = name === 'Statements' ? (!files.length ? 'Add at least one statement to continue' : files.some((f) => !f.bank && !f.ok) ? 'Pick the bank for each locked file' : '')
    : name === 'Passwords' ? (files.some((f) => !f.ok) ? 'Unlock every bank to continue' : '')
    : name === 'Spending' ? 'Optional: you can skip this' : ''

  const go = (d: number) => { setError(''); setStep((s) => s + d) }
  const finish = async () => {
    setBuilding(true)
    setResult(null)
    try { setResult(await api('/api/finish', ADD ? {} : { theme: theme.id, plan })) }
    catch (e) { setResult({ ok: false, log: (e as Error).message }) }
    setBuilding(false)
  }

  const body: ReactNode = {
    Welcome: null,   // the full-screen Hero, rendered below
    Statements: <Statements key="s" api={api} st={st} refresh={refresh} onError={setError} onBusy={setUploading} />,
    Passwords: <Passwords key="p" api={api} st={st} banks={lockedBanks} refresh={refresh} />,
    Theme: <ThemeStep key="t" current={theme.id} pick={pickTheme} />,
    Spending: <Spending key="e" plan={plan} setPlan={setPlan} />,
    Finish: <Finish key="f" building={building} result={result} retry={finish} />,
  }[name]

  if (name === 'Welcome') return <Hero onStart={() => go(1)} />

  return (
    <div className="relative flex h-dvh flex-col overflow-hidden" data-od-id="setup-wizard">
      <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
        <span className="glow -top-24 left-1/4 size-96 bg-brand" />
        <span className="glow bottom-0 right-0 size-80 bg-expense" />
      </div>

      <header className="relative flex items-center gap-3 px-4 pt-4 sm:px-8">
        <span className="grid size-10 shrink-0 place-items-center rounded-full bg-foreground text-lg text-background" aria-hidden>฿</span>
        <div className="min-w-0">
          <p className="text-sm font-medium">Statement Visualizer</p>
          <p className="text-xs text-muted-foreground">{ADD ? 'Add statements' : 'Setup'} · step {step + 1} of {STEPS.length}</p>
        </div>
        <ol className="ml-auto hidden items-center gap-1 rounded-full border bg-card p-1 md:flex" aria-label="Setup steps">
          {STEPS.map((s, i) => (
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

      {!result?.ok && (
        <footer className="relative flex items-center gap-3 border-t bg-background/80 px-4 py-3 backdrop-blur sm:px-8">
          <button type="button" className={ghost} onClick={() => go(-1)} disabled={step === 0 || building}>
            <ArrowLeft className="size-4" />Back
          </button>
          <span className="min-w-0 flex-1 truncate text-center text-xs text-muted-foreground">{hint}</span>
          {step < STEPS.length - 1 ? (
            <button type="button" className={primary} disabled={!canNext} onClick={() => go(1)}>
              {name === 'Spending' && !plan.length ? 'Skip' : 'Next'}<ArrowRight className="size-4" />
            </button>
          ) : (
            <button type="button" className={primary} disabled={building} onClick={finish}>
              {building ? <><Loader2 className="size-4 animate-spin" />Building…</> : <>{ADD ? 'Update my dashboard' : 'Build my dashboard'}<ArrowRight className="size-4" /></>}
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

function Statements({ api, st, refresh, onError, onBusy }: {
  api: Api; st: State | null; refresh: () => Promise<void>; onError: (m: string) => void; onBusy: (n: number) => void
}) {
  const [over, setOver] = useState(false)
  const [busy, setBusy] = useState<string[]>([])
  const add = async (list: FileList | null) => {
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
  // The add page lists only what's new or needs a bank picked; older files are summed up in one line.
  const all = st?.files ?? []
  const files = ADD ? all.filter((f) => f.uploaded || !f.bank) : all
  const older = all.length - files.length
  return (
    <Frame title={ADD ? 'Add new statements' : 'Add your statements'} icon={<Upload className="size-5" />}
      sub={ADD ? <>Drop the PDFs your bank sent since last time. Supported: {(st?.banks ?? []).map((b) => b.name).join(', ') || '…'}.</>
        : <>PDF statements from your bank, as many as you have. Supported: {(st?.banks ?? []).map((b) => b.name).join(', ') || '…'}.</>}>
      <label onDragOver={(e) => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); add(e.dataTransfer.files) }}
        className={cn('flex cursor-pointer flex-col items-center gap-1.5 rounded-2xl border-2 border-dashed px-4 py-6 text-center transition-colors focus-within:ring-2 focus-within:ring-ring/40',
          over ? 'border-brand bg-brand/10' : 'hover:bg-muted/50')}>
        <Upload className="size-6 text-brand" />
        <span className="text-sm font-medium">Drop PDFs here, or click to choose</span>
        <span className="text-xs text-muted-foreground">They are copied into the Statement/ folder</span>
        <input type="file" accept="application/pdf,.pdf" multiple className="sr-only" onChange={(e) => { add(e.target.files); e.target.value = '' }} />
      </label>
      <ul className="min-h-0 divide-y overflow-y-auto rounded-2xl border" aria-label="Statements">
        {!files.length && !busy.length && <li className="px-4 py-5 text-center text-sm text-muted-foreground">{ADD ? 'No new statements yet.' : 'No statements yet.'}</li>}
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
            {f.uploaded && (
              <button type="button" aria-label={`Remove ${f.name}`} className="grid size-9 place-items-center rounded-full text-muted-foreground transition hover:bg-muted hover:text-neg"
                onClick={async () => { await api('/api/remove', { name: f.name }).catch((x) => onError(x.message)); refresh() }}>
                <Trash2 className="size-4" />
              </button>
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
          <Check className="size-3.5 text-pos" />{older} statement{older === 1 ? '' : 's'} already in Statement/ will be read again too.
        </p>
      )}
    </Frame>
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

function ThemeStep({ current, pick }: { current: string; pick: (id: string) => void }) {
  return (
    <Frame title="Pick a look" sub="Change it any time with the sun / moon button at the top of the dashboard.">
      <div className="grid min-h-0 grid-cols-2 gap-3 overflow-y-auto" role="radiogroup" aria-label="Theme">
        {THEMES.map((t) => {
          const on = t.id === current
          return (
            <button key={t.id} type="button" role="radio" aria-checked={on} onClick={() => pick(t.id)}
              className={cn('rounded-3xl border p-2 text-left transition hover:shadow-md', on && 'ring-2 ring-brand')}>
              {/* a tiny dashboard drawn with the theme's own tokens */}
              <div className={cn(t.mode, 'rounded-2xl bg-background p-3')} data-theme={t.id} aria-hidden>
                <div className="flex gap-2">
                  <div className="flex-1 rounded-xl bg-card p-2 ring-1 ring-foreground/10">
                    <div className="h-1.5 w-10 rounded bg-muted-foreground/50" />
                    <div className="mt-2 h-3 w-16 rounded bg-foreground/80" />
                  </div>
                  <div className="w-9 rounded-xl bg-brand" />
                </div>
                <div className="mt-2 flex h-9 items-end gap-1">
                  {[40, 70, 35, 90, 55, 65, 30].map((h, i) => <span key={i} className="flex-1 rounded-sm bg-expense/70" style={{ height: `${h}%` }} />)}
                </div>
              </div>
              <div className="flex items-start justify-between gap-2 px-1.5 pt-2">
                <div><p className="text-sm font-medium">{t.label}</p><p className="text-xs text-muted-foreground">{t.note}</p></div>
                {on && <Check className="mt-0.5 size-4 shrink-0 text-brand" />}
              </div>
            </button>
          )
        })}
      </div>
    </Frame>
  )
}

function Spending({ plan, setPlan }: { plan: PlanItem[]; setPlan: (p: PlanItem[]) => void }) {
  const [name, setName] = useState('')
  const [amount, setAmount] = useState('')
  const [every, setEvery] = useState<PlanItem['every']>('day')
  const amt = Math.max(0, parseFloat(amount) || 0)
  const month = plan.reduce((a, i) => a + (i.every === 'day' ? i.amount * 30 : i.amount), 0)
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
        <Segmented id="setup-every" label="How often" value={every} onChange={setEvery} options={[{ value: 'day', label: 'Daily' }, { value: 'month', label: 'Monthly' }]} />
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

function Finish({ building, result, retry }: { building: boolean; result: { ok: boolean; log?: string; dashboard?: string } | null; retry: () => void }) {
  if (result?.ok) {
    return (
      <Frame title="Your dashboard is ready" icon={<Check className="size-5" />}
        sub="It is opening in a new browser tab. You can close this one; the setup server has stopped.">
        <p className="rounded-2xl border bg-muted/40 px-4 py-3 text-sm">
          Next time, run <code className="num">./run.sh</code> to add new statements (or <code className="num">./run.sh --setup</code> to see this again).
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
  if (ADD) {
    return (
      <Frame title="Ready to update" icon={<Check className="size-5" />}
        sub="Reads every statement in Statement/, new ones included, and rebuilds your dashboard.">
        <p className="rounded-2xl border bg-muted/40 px-4 py-3 text-sm text-muted-foreground">
          Tired of adding statements by hand? <code className="num">./gmail.sh</code> can fetch them from Gmail by itself
          (README, “Option 2”).
        </p>
        <p className="text-xs text-muted-foreground">{building ? 'Reading your statements and building the dashboard…' : 'Press “Update my dashboard” when you are ready.'}</p>
      </Frame>
    )
  }
  const steps: [string, ReactNode][] = [
    ['Google Cloud', <>In console.cloud.google.com create a project and enable the <b>Gmail API</b>.</>],
    ['Consent screen', <>Choose <b>External</b> and add your own Gmail as a test user.</>],
    ['Credentials', <>Create an <b>OAuth client ID</b> of type <b>Desktop app</b>; put its ID and secret in <code className="num">.env</code> as <code className="num">GOOGLE_CLIENT_ID</code> / <code className="num">GOOGLE_CLIENT_SECRET</code>.</>],
    ['First run', <>Run <code className="num">./gmail.sh</code> and sign in once. It downloads new statements and rebuilds the dashboard.</>],
    ['Every day', <>Optional: <code className="num">crontab -e</code> → <code className="num">0 8 * * * cd {'<project folder>'} && ./gmail.sh</code> (needs remembered passwords).</>],
  ]
  return (
    <Frame title="Last thing: statements by email" icon={<Mail className="size-5" />}
      sub="Optional, and you can do it any time. Banks email statements; Statement Visualizer can fetch them from Gmail by itself (read-only).">
      <ol className="min-h-0 space-y-2 overflow-y-auto">
        {steps.map(([t, text], i) => (
          <li key={t} className="flex gap-3 rounded-2xl border px-3 py-2.5">
            <span className="grid size-6 shrink-0 place-items-center rounded-full bg-brand/15 text-xs font-semibold text-brand">{i + 1}</span>
            <p className="text-sm"><b className="font-medium">{t}.</b> <span className="text-muted-foreground">{text}</span></p>
          </li>
        ))}
      </ol>
      <p className="text-xs text-muted-foreground">Full guide: README.md, “Option 2: fetch from Gmail automatically”. {building ? 'Reading your statements and building the dashboard…' : 'Press “Build my dashboard” when you are ready.'}</p>
    </Frame>
  )
}
