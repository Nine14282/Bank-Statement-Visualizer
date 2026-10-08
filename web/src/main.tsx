import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { StyledEngineProvider, ThemeProvider } from '@mui/material/styles'
import { MotionConfig } from 'motion/react'
import './index.css'
import App from './App.tsx'
import { TooltipProvider } from '@/components/ui/tooltip'
import { theme } from '@/lib/mui-theme'
import { initialTheme } from '@/lib/themes'

const start = initialTheme()
document.documentElement.dataset.theme = start.id   // before the first paint: no flash of the wrong theme

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {/* enableCssLayer: MUI styles go in @layer mui (ordered in index.css) so Tailwind classes override them */}
    <StyledEngineProvider enableCssLayer>
      <ThemeProvider theme={theme} defaultMode={start.mode}>
        <TooltipProvider>
          {/* "user": animations shrink to fades when the OS asks for reduced motion */}
          <MotionConfig reducedMotion="user">
            <App />
          </MotionConfig>
        </TooltipProvider>
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
    if (built && v && v !== built) location.reload()
    built = v ?? built
    s.remove()
  }
  s.onerror = () => s.remove()  // mid-rebuild or missing: try again next tick
  document.head.append(s)
}
poll()  // baseline now, so a rebuild right after load is not missed
setInterval(poll, 10_000)
