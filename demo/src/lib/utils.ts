import * as React from "react"
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function useIsMobileScreen(breakpoint?: string) {
  const [isMobileScreen, setIsMobileScreen] = React.useState(false)

  React.useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${breakpoint ?? "768px"})`)
    setIsMobileScreen(mql.matches)
    const listener = () => setIsMobileScreen(mql.matches)
    mql.addEventListener("change", listener)

    return () => mql.removeEventListener("change", listener)
  }, [breakpoint])

  return isMobileScreen
}

export function formatNumber(num: number, decimals: number = 1): string {
  if (num === 0) return "0"

  const k = 1000
  const sizes = ["", "K", "M", "B", "T"]

  const i = Math.floor(Math.log(Math.abs(num)) / Math.log(k))

  if (i === 0) return num.toString()

  const scaled = num / Math.pow(k, i)
  return `${scaled.toFixed(decimals)}${sizes[i]}`
}
