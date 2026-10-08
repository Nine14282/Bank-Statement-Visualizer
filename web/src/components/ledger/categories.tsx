import { useState } from 'react'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { baht } from '@/lib/ledger'

type Cat = { cat: string; amt: number; n: number }
type Mode = 'amt' | 'n' | 'name'

const SORTS: Record<Mode, (a: Cat, b: Cat) => number> = {
  amt: (a, b) => b.amt - a.amt,
  n: (a, b) => b.n - a.n,
  name: (a, b) => a.cat.localeCompare(b.cat, 'th'),
}

export function CategoryCard({ title, caption, list, color }: { title: string; caption: string; list: Cat[]; color: string }) {
  const [mode, setMode] = useState<Mode>('amt')
  const sorted = [...list].sort(SORTS[mode])
  const total = sorted.reduce((a, c) => a + c.amt, 0)
  const max = Math.max(...sorted.map((c) => c.amt), 1)
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{caption}</CardDescription>
        <CardAction>
          <ToggleGroup size="sm" variant="outline" value={[mode]} onValueChange={(v) => v[0] && setMode(v[0] as Mode)}>
            <ToggleGroupItem value="amt">Amount</ToggleGroupItem>
            <ToggleGroupItem value="n">Count</ToggleGroupItem>
            <ToggleGroupItem value="name">A–Z</ToggleGroupItem>
          </ToggleGroup>
        </CardAction>
      </CardHeader>
      <CardContent className="divide-y">
        {sorted.length === 0 && <p className="py-8 text-center text-sm text-muted-foreground">Nothing in this period.</p>}
        {sorted.map((c, i) => (
          <div key={c.cat} className="space-y-1 py-2">
            <div className="flex items-baseline justify-between gap-3">
              <span className="text-sm font-medium">
                {c.cat}
                <small className="num ml-1.5 text-[11px] font-normal text-muted-foreground">
                  {c.n} · {((c.amt / total) * 100).toFixed(1)}%
                </small>
              </span>
              <span className="num text-sm font-semibold">{baht(c.amt)}</span>
            </div>
            <div className="h-1 overflow-hidden rounded-full bg-muted">
              <div className="h-full origin-left rounded-full transition-transform duration-700"
                style={{ background: color, opacity: 1 - (sorted.length > 1 ? i / (sorted.length - 1) : 0) * 0.62,
                  transform: `scaleX(${c.amt / max})` }} />
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
