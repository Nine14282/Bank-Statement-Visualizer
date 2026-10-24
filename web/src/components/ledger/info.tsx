import type { ReactElement, ReactNode } from 'react'
import { CircleHelp } from 'lucide-react'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

// A label for an icon-only control: hover or keyboard focus shows it. `children` is the control itself (one element
// that takes a ref, e.g. a <button>); the tooltip merges its props into it.
export const Tip = ({ label, side = 'bottom', children }: { label: ReactNode; side?: 'top' | 'right' | 'bottom' | 'left'; children: ReactElement }) => (
  <Tooltip>
    <TooltipTrigger render={children} />
    <TooltipContent side={side}>{label}</TooltipContent>
  </Tooltip>
)

// A "?" beside a term: hover, keyboard focus or tap shows what it means. A popover, not a tooltip: Base UI tooltips
// never open on touch. The popup is portaled and flips to stay on screen.
export function InfoTip({ children, label = 'What does this mean?' }: { children: ReactNode; label?: string }) {
  return (
    <Popover>
      <PopoverTrigger openOnHover delay={100} aria-label={label}
        className="relative inline-grid size-5 place-items-center rounded-full align-middle text-muted-foreground transition-colors hover:text-foreground after:absolute after:-inset-2.5">
        <CircleHelp className="size-3.5" />
      </PopoverTrigger>
      <PopoverContent side="top" className="block w-auto max-w-64 rounded-md bg-foreground px-3 py-1.5 text-xs leading-relaxed text-background ring-0">
        {children}
      </PopoverContent>
    </Popover>
  )
}
