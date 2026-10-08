import { useEffect, useRef, type ComponentProps } from 'react'
import { animate, motion, useReducedMotion } from 'motion/react'
import { EASE } from '@/lib/utils'

// A figure that counts from what it showed last to its new value (0 on first paint). The effect owns the text;
// render only seeds it, so re-renders mid-count don't fight the animation.
// `format` must be stable (a module-level function), or every render restarts the count.
export function CountUp({ value, format, className }: { value: number; format: (n: number) => string; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null)
  const shown = useRef(0)
  const still = useReducedMotion()
  useEffect(() => {
    const c = animate(shown.current, value, {
      duration: still ? 0 : 1.1, ease: EASE,
      onUpdate: (v) => { shown.current = v; if (ref.current) ref.current.textContent = format(v) },
    })
    return () => c.stop()
  }, [value, format, still])
  return <span ref={ref} className={className}>{format(0)}</span>
}

// Fades and lifts its content in the first time it scrolls into view (`now`: on mount, for above-the-fold cards).
export function Reveal({ delay = 0, now, ...rest }: ComponentProps<typeof motion.div> & { delay?: number; now?: boolean }) {
  const show = { opacity: 1, y: 0 }
  return (
    <motion.div initial={{ opacity: 0, y: 18 }} {...(now ? { animate: show } : { whileInView: show, viewport: { once: true, margin: '-40px' } })}
      transition={{ duration: 0.45, delay, ease: EASE }} {...rest} />
  )
}
