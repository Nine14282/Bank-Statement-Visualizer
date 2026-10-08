import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { StyledEngineProvider, ThemeProvider } from '@mui/material/styles'
import './index.css'
import App from './App.tsx'
import { TooltipProvider } from '@/components/ui/tooltip'
import { theme } from '@/lib/mui-theme'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {/* enableCssLayer: MUI styles go in @layer mui (ordered in index.css) so Tailwind classes override them */}
    <StyledEngineProvider enableCssLayer>
      <ThemeProvider theme={theme} defaultMode="dark">
        <TooltipProvider>
          <App />
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
