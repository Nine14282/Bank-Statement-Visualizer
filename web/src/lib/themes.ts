import { useEffect, useState } from 'react'
import { useColorScheme } from '@mui/material/styles'
import { META } from '@/lib/ledger'

// Theme registry. A theme = light or dark base tokens (index.css :root/.light and .dark) plus, optionally, its own
// [data-theme="<id>"] block in index.css overriding any of them. Adding a theme = one entry here (+ that CSS block).
export type ThemeDef = { id: string; label: string; mode: 'light' | 'dark'; note: string }

export const THEMES: ThemeDef[] = [
  { id: 'midnight', label: 'Midnight', mode: 'dark', note: 'Dark and calm, easy on the eyes at night' },
  { id: 'daylight', label: 'Daylight', mode: 'light', note: 'Bright and crisp, like paper' },
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
    // before this registry the toggle only stored MUI's light/dark: keep that choice unless the wizard picked one
    const legacy = localStorage.getItem('mui-mode')
    if (!BASE && (legacy === 'light' || legacy === 'dark')) return THEMES.find((t) => t.mode === legacy) ?? THEMES[0]
  } catch { /* unreadable: use the default */ }
  return themeById(BASE)
}

// Current theme + a setter; applies data-theme and the MUI light/dark mode (which drives the .dark class).
export function useTheme() {
  const { setMode } = useColorScheme()
  const [id, setId] = useState(() => initialTheme().id)
  const theme = themeById(id)
  useEffect(() => {
    document.documentElement.dataset.theme = theme.id
    setMode(theme.mode)
  }, [theme, setMode])
  const pick = (next: string) => {
    try { localStorage.setItem(STORE, JSON.stringify({ id: next, base: BASE })) } catch { /* storage blocked */ }
    setId(next)
  }
  return [theme, pick] as const
}
