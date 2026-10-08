import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

// Hairline-divided stat cells: 1px gaps over a border-coloured backdrop draw the grid lines.
export function KpiGrid({ children, className, ...rest }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn('grid grid-cols-2 gap-px overflow-hidden rounded-xl border bg-border lg:grid-cols-4', className)} {...rest}>
      {children}
    </div>
  )
}

export function Kpi({ label, value, sub, dot, valueClass, className }: {
  label: string; value: ReactNode; sub?: ReactNode; dot?: string; valueClass?: string; className?: string
}) {
  return (
    <div className={cn('space-y-3 bg-card p-4 md:p-5', className)}>
      <div className="eyebrow flex items-center gap-2">
        <span className="size-1.5 rounded-full" style={{ background: dot ?? 'var(--muted-foreground)' }} />
        {label}
      </div>
      <div className={cn('display text-3xl md:text-4xl', valueClass)}>{value}</div>
      {sub && <span className="pill">{sub}</span>}
    </div>
  )
}
