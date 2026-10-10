import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import GlobalStyles from '@mui/material/GlobalStyles'
import { StyledEngineProvider, ThemeProvider } from '@mui/material/styles'
import { MotionConfig, MotionGlobalConfig } from 'motion/react'
import './index.css'
import App from './App.tsx'
import { theme } from '@/lib/mui-theme'
import { initialTheme } from '@/lib/themes'
import { APP, ARRIVE } from '@/lib/utils'

const start = initialTheme()
document.documentElement.dataset.theme = start.id   // before the first paint: no flash of the wrong theme
// The desktop app window skips every Motion animation: WebKitGTK stutters on them (first scroll: 24 slow frames -> 9).
// The browser keeps them. One exception: the dashboard's entrance after an update (ARRIVE); then still again.
if (APP) MotionGlobalConfig.skipAnimations = !ARRIVE
if (ARRIVE) document.documentElement.classList.add('arriving')   // CSS animations play too (index.css); ends: App.tsx

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

// Hot reload: each build also writes dist/version.js (window.__BUILD = timestamp). A <script> tag can load it even
// from file://, where fetch cannot, so the page just opened from disk still notices a rebuild and reloads.
let built: number | undefined
const poll = () => {
  const s = document.createElement('script')
  s.src = `version.js?${Date.now()}`
  s.onload = () => {
    const v = (window as unknown as { __BUILD?: number }).__BUILD
    const changed = built && v && v !== built
    // Not while the add page is open over the dashboard (app window): it reloads by itself once its update is done.
    if (changed && !document.querySelector('[data-od-id="setup-wizard"]')) location.reload()
    if (!changed) built = v ?? built
    s.remove()
  }
  s.onerror = () => s.remove()  // mid-rebuild or missing: try again next tick
  document.head.append(s)
}
// Not on the browser's setup/add page (welcome.py serves it and opens the dashboard itself when done).
if (!new URLSearchParams(location.search).has('setup')) {
  poll()  // baseline now, so a rebuild right after load is not missed
  setInterval(poll, 10_000)
}
