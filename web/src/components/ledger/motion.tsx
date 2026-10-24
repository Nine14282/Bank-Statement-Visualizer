import type { ComponentProps } from 'react'
import { motion } from 'motion/react'
import { EASE } from '@/lib/utils'

// Fades and lifts its content in the first time it scrolls into view (`now`: on mount, for above-the-fold cards).
export function Reveal({ delay = 0, now, ...rest }: ComponentProps<typeof motion.div> & { delay?: number; now?: boolean }) {
  const show = { opacity: 1, y: 0 }
  return (
    <motion.div initial={{ opacity: 0, y: 18 }} {...(now ? { animate: show } : { whileInView: show, viewport: { once: true, margin: '-40px' } })}
      transition={{ duration: 0.45, delay, ease: EASE }} {...rest} />
  )
}
