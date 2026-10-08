import { useState } from 'react'
import { META } from '@/lib/ledger'

// Expected spending: things the user says they spend every day (food, fare) or every month (rent, phone).
// `key` links an item to a payee in the ledger (so its real payments can be told apart); hand-added items have none.
export type PlanItem = { id: string; name: string; amount: number; every: 'day' | 'month'; key?: string }

const STORE = 'ledger-expected-spending'
// The setup wizard's list (in the ledger data) seeds it; edits made here are kept in this browser and win until
// the wizard is run again with a different list (`base` remembers which seed they were made on).
const SEED = META.plan ?? []
const BASE = JSON.stringify(SEED)
const load = (): PlanItem[] => {
  try {
    const s = JSON.parse(localStorage.getItem(STORE) ?? 'null')
    if (Array.isArray(s)) return SEED.length ? SEED : s   // saved before the wizard existed
    if (s?.base === BASE) return s.items
  } catch { /* unreadable: start from the seed */ }
  return SEED
}

// Kept in this browser like the label rules; unlike them it needs no reload, nothing else is derived from it.
export function usePlan() {
  const [plan, setPlan] = useState(load)
  const save = (p: PlanItem[]) => {
    setPlan(p)
    try { localStorage.setItem(STORE, JSON.stringify({ base: BASE, items: p })) } catch { /* storage blocked: kept for this visit only */ }
  }
  return [plan, save] as const
}

export const newId = () => `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`
export const perMonth = (i: PlanItem, days: number) => (i.every === 'day' ? i.amount * days : i.amount)
// Expected spending for a month of `days` days: every daily item × days, plus every monthly item once.
export const expectedFor = (plan: PlanItem[], days: number) => plan.reduce((a, i) => a + perMonth(i, days), 0)
