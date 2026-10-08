import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// Shared ease-out curve for motion animations (fast start, long settle).
export const EASE = [0.16, 1, 0.3, 1] as const
