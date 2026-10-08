import type { ReactNode } from 'react'
import MuiTooltip from '@mui/material/Tooltip'
import { CircleHelp } from 'lucide-react'

// A "?" beside a term: hover, keyboard focus or tap shows what it means. The popup is portaled and flips to stay on screen.
export function InfoTip({ children, label = 'What does this mean?' }: { children: ReactNode; label?: string }) {
  return (
    <MuiTooltip arrow placement="top" enterTouchDelay={0} leaveTouchDelay={5000}
      title={<span className="block max-w-64 text-xs leading-relaxed">{children}</span>}>
      <button type="button" aria-label={label}
        className="relative inline-grid size-5 place-items-center rounded-full align-middle text-muted-foreground transition-colors hover:text-foreground after:absolute after:-inset-2.5">
        <CircleHelp className="size-3.5" />
      </button>
    </MuiTooltip>
  )
}
