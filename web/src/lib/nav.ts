import { useEffect, useState } from 'react'
import { Hourglass, LayoutDashboard, ListOrdered, PieChart, TrendingUp } from 'lucide-react'

// One page, sections in this order; the nav rail and the scroll-spy read this list.
export const SECTIONS = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'categories', label: 'Categories', icon: PieChart },
  { id: 'spend-rate', label: 'Spend rate', icon: TrendingUp },
  { id: 'predict', label: 'Predict', icon: Hourglass },
  { id: 'transactions', label: 'Transactions', icon: ListOrdered },
]
export type Tab = 'dashboard' | 'plan' | 'custom'
export const goTo = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })

// The section crossing a band 30-40% down the viewport; the last one stays lit while scrolling through gaps.
export function useActiveSection() {
  const [active, setActive] = useState(SECTIONS[0].id)
  useEffect(() => {
    const io = new IntersectionObserver((es) => es.forEach((e) => e.isIntersecting && setActive(e.target.id)),
      { rootMargin: '-30% 0px -60% 0px' })
    SECTIONS.forEach((s) => { const el = document.getElementById(s.id); if (el) io.observe(el) })
    return () => io.disconnect()
  }, [])
  return active
}
