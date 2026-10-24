import { useEffect, useState } from 'react'
import { META } from '@/lib/ledger'
import { APP, bridge } from '@/lib/utils'

// Theme registry. A theme = light or dark base tokens (index.css :root/.light and .dark) plus, optionally, its own
// [data-theme="<id>"] block in index.css overriding any of them. Adding a theme = one entry here (+ that CSS block).
export type ThemeDef = { id: string; label: string; mode: 'light' | 'dark'; note: string }

// The first is the default (no THEME setting, nothing picked in this browser).
export const THEMES: ThemeDef[] = [
  { id: 'daylight', label: 'Daylight', mode: 'light', note: 'Bright and crisp, like paper' },
  { id: 'midnight', label: 'Midnight', mode: 'dark', note: 'Dark and calm, easy on the eyes at night' },
]

export const themeById = (id?: string) => THEMES.find((t) => t.id === id) ?? THEMES[0]

// The setup wizard's pick (THEME setting, in the ledger data) is the default; a pick made in the dashboard is kept
// in this browser and wins until the wizard picks again (`base` remembers which default it was made on).
const STORE = 'ledger-theme'
const BASE = META.theme ?? ''

export function initialTheme(): ThemeDef {
  try {
    const s = JSON.parse(localStorage.getItem(STORE) ?? 'null')
    if (s?.base === BASE) return themeById(s.id)
    // before this registry the toggle only stored a light/dark mode (`mui-mode`, from when MUI kept it): keep that choice unless the wizard picked one
    const legacy = localStorage.getItem('mui-mode')
    if (!BASE && (legacy === 'light' || legacy === 'dark')) return THEMES.find((t) => t.mode === legacy) ?? THEMES[0]
  } catch { /* unreadable: use the default */ }
  return themeById(BASE)
}

// The light/dark base: the .dark or .light class on <html> (index.css tokens, Tailwind's dark: variant).
export function applyTheme(t: ThemeDef) {
  const root = document.documentElement
  root.dataset.theme = t.id
  root.classList.toggle('dark', t.mode === 'dark')
  root.classList.toggle('light', t.mode === 'light')
}

// Current theme + a setter; applies it to the page.
export function useTheme() {
  const [id, setId] = useState(() => initialTheme().id)
  const theme = themeById(id)
  useEffect(() => {
    applyTheme(theme)
    if (APP) void bridge().then((b) => b.theme(theme.mode))   // the window starts in this colour next time (app.py)
  }, [theme])
  const pick = (next: string) => {
    try { localStorage.setItem(STORE, JSON.stringify({ id: next, base: BASE })) } catch { /* storage blocked */ }
    setId(next)
  }
  return [theme, pick] as const
}
