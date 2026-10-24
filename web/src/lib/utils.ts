import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// Shared ease-out curve for motion animations (fast start, long settle).
export const EASE = [0.16, 1, 0.3, 1] as const

// Shown in the desktop app window (workspace/app.py opens the page with ?app), not a browser tab.
export const APP = new URLSearchParams(location.search).has('app')
// The same app in a browser tab, for computers with no app window: served by workspace/welcome.py at ?web, which
// answers the Add statements and Settings pages over HTTP (wizard.tsx's api) instead of the window's bridge.
export const WEB = new URLSearchParams(location.search).has('web')
// Either: Add statements and Settings work in this page.
export const HOSTED = APP || WEB

// Where people open the app after installing (never a terminal command): the launchers launcher.py and the Windows
// Setup create.
export const OPEN_APP = 'Open Statement Visualizer: the Start Menu on Windows, your app menu on Linux, or “Statement Visualizer.command” in its folder on a Mac.'

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
