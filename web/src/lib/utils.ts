import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import { MotionGlobalConfig, useReducedMotion } from "motion/react"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// Shared ease-out curve for motion animations (fast start, long settle).
export const EASE = [0.16, 1, 0.3, 1] as const

// Shown in the desktop app window (workspace/app.py opens the page with ?app), not a browser tab.
export const APP = new URLSearchParams(location.search).has('app')

// The app window's bridge to workspace/app.py's Api (pywebview): call = the setup/add page's requests (wizard.tsx),
// save = Export CSV through a save dialog (shell.tsx), theme = the theme mode shown, for the next start's window colour
// (themes.ts). pywebview creates its api object empty and fills it in just
// before pywebviewready, so wait for the method itself.
export type Bridge = {
  call: (path: string, name: string, data: unknown) => Promise<any>
  save: (name: string, text: string) => Promise<boolean>
  theme: (mode: 'light' | 'dark') => Promise<void>
}
export const bridge = () => new Promise<Bridge>((ok) => {
  const w = window as unknown as { pywebview?: { api?: Partial<Bridge> } }
  if (w.pywebview?.api?.call) ok(w.pywebview.api as Bridge)
  else window.addEventListener('pywebviewready', () => ok(w.pywebview!.api as Bridge), { once: true })
})

// The app window's one entrance: back from an update (wizard.tsx reloads with ?app&updated), the dashboard animates in
// (cards, charts, count-ups, ticks) for ARRIVE_MS after it mounts (App.tsx), then goes still again like the rest of the
// window (main.tsx starts it).
export const ARRIVE = APP && new URLSearchParams(location.search).has('updated')
export const ARRIVE_MS = 3000
let arriving = ARRIVE
export function endArrival() {
  arriving = false
  MotionGlobalConfig.skipAnimations = true
  document.documentElement.classList.remove('arriving')
}

// Reduced motion, as the OS asks. The app window always asks (app.py), except during its entrance after an update.
export function useStill() {
  return (useReducedMotion() ?? false) && !arriving
}
