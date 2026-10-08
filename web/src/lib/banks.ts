import kbank from '@/assets/kbank.webp'
import krungthai from '@/assets/krungthai.webp'

// Bank display info: the dashboard's name, card colour and logo for each bank id (the ledger's Bank column).
// Adding a bank = one entry here; reading its statements is the BANKS registry in workspace/extract_ledger.py.
// Card colours are deep enough for white text (>= 4.5:1); `full`: the logo is already a round badge.
export type BankInfo = { name: string; skin?: string; img?: string; badge?: string; full?: boolean }

export const BANKS: Record<string, BankInfo> = {
  KTB: { name: 'Krungthai', skin: 'linear-gradient(120deg, #0b6fb3, #075a94)', img: krungthai, badge: '#0b6fb3' },
  KBANK: { name: 'KBank', skin: 'linear-gradient(120deg, #0f7a3a, #0a5f2d)', img: kbank, full: true },
  Manual: { name: 'Manual entry' },
}

export const bankName = (b: string) => BANKS[b]?.name ?? b
