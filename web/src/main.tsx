import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import GlobalStyles from '@mui/material/GlobalStyles'
import { StyledEngineProvider, ThemeProvider } from '@mui/material/styles'
import { MotionConfig, MotionGlobalConfig } from 'motion/react'
import './index.css'
import App from './App.tsx'
import { theme } from '@/lib/mui-theme'
import { META, setData } from '@/lib/ledger'
import { initialTheme } from '@/lib/themes'
import { APP, ARRIVE } from '@/lib/utils'

const start = initialTheme()
document.documentElement.dataset.theme = start.id   // before the first paint: no flash of the wrong theme
// The desktop app window skips every Motion animation (chosen under WebKitGTK, the window's engine before Qt, which
// stuttered on them: first scroll 24 slow frames -> 9). The browser keeps them. One exception: the dashboard's entrance
// after an update (ARRIVE); then still again.
if (APP) MotionGlobalConfig.skipAnimations = !ARRIVE
if (ARRIVE) document.documentElement.classList.add('arriving')   // CSS animations play too (index.css); ends: App.tsx
// The app window reports reduced motion because app.py asks its web view for it, not because the user asked:
// the new-row animations (index.css .tx-new, tx-table.tsx) check this class to play there anyway.
if (APP) document.documentElement.classList.add('in-app')
// A file dropped outside a drop zone would replace this page with the file (the app window has no Back button; a tab
// loses the dashboard). Drop zones (wizard.tsx) handle theirs first; everywhere else shows "no drop" and ignores it.
for (const type of ['dragover', 'drop'] as const) {
  window.addEventListener(type, (e) => {
    if (e.defaultPrevented) return
    e.preventDefault()
    if (e.dataTransfer) e.dataTransfer.dropEffect = 'none'
  })
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {/* enableCssLayer: MUI styles go in @layer mui, so Tailwind utilities override them. MUI's sheet lands first in
        <head>, ahead of Tailwind's, so the layer order must be declared here, before any layer opens (MUI's Tailwind v4
        guide). `properties` is Tailwind's own @property layer. */}
    <StyledEngineProvider enableCssLayer>
      <GlobalStyles styles="@layer properties, theme, base, mui, components, utilities;" />
      {/* noSsr: the .dark class is set on the first render, not a render late. storageManager={null}: `ledger-theme`
          (themes.ts) is the only place the theme is kept, MUI keeps no second copy (mui-mode) that could disagree. */}
      <ThemeProvider theme={theme} defaultMode={start.mode} noSsr storageManager={null}>
        {/* "user": animations shrink to fades when the OS asks for reduced motion (not in the entrance after an update) */}
        <MotionConfig reducedMotion={ARRIVE ? 'never' : 'user'}>
          <App />
        </MotionConfig>
      </ThemeProvider>
    </StyledEngineProvider>
  </StrictMode>,
)

// Live update, pushed (no polling): each build writes dist/version.js (window.__BUILD = its stamp) and dist/data.js
// (window.__LEDGER = the same data as the page's ledger-data tag). In the app window, app.py calls
// window.__ledgerUpdate() when its Gmail listener reports a finished fetch; this loads those two files by <script> tag
// (which works from file://, where fetch doesn't) and swaps the new data in place (setData): no reload, no blank page,
// scroll position and open panels kept. A browser tab gets no pushes: reload it to see a rebuild.
const win = window as unknown as {
  __BUILD?: number; __PAGE?: string; __LEDGER?: Parameters<typeof setData>[0]; __LEDGER_BUILD?: number
  __ledgerUpdate?: () => void
}
const PAGE = META.page   // the app build this page runs; a rebuild for a newer one reloads instead of swapping
const load = (file: string, then: () => void, failed = () => {}) => {
  const s = document.createElement('script')
  s.src = `${file}?${Date.now()}`
  s.onload = () => { s.remove(); then() }
  s.onerror = () => { s.remove(); failed() }
  document.head.append(s)
}
let built = META.build   // the build this page was written by
let loading = false
win.__ledgerUpdate = () => load('version.js', () => {
  const v = win.__BUILD
  // The add page open over the dashboard (app window): it reloads by itself once its update is done, and closing it
  // without one calls this again (App.tsx).
  // v <= built: nothing newer than what's shown (built can be ahead: a newer data.js was swapped in, see below)
  if (!v || (built && v <= built) || loading || document.querySelector('[data-od-id="setup-wizard"]')) return
  // The app itself was updated (new prebuilt page): reload to run the new code. Rare; data-only rebuilds swap below.
  if (PAGE && win.__PAGE && win.__PAGE !== PAGE) return location.reload()
  loading = true
  load('data.js', () => {
    loading = false
    // Older than the version.js just read (left by a builder that doesn't write data.js): the page itself is current,
    // reload. Newer (another rebuild landed while this loaded): it's the latest data, swap it in like an equal one.
    const got = win.__LEDGER_BUILD
    if (!got || got < v) return location.reload()
    built = got
    if (win.__LEDGER !== undefined) setData(win.__LEDGER)
    win.__LEDGER = undefined   // the whole ledger: don't keep a second copy around
  }, () => location.reload())   // no data.js (a build from before live updates): reload
})
