import * as React from "react";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function useIsMobileScreen(breakpoint?: string) {
  const [isMobileScreen, setIsMobileScreen] = React.useState(false);

  React.useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${breakpoint ?? "768px"})`);
    setIsMobileScreen(mql.matches);
    const listener = () => setIsMobileScreen(mql.matches);
    mql.addEventListener("change", listener);

    return () => mql.removeEventListener("change", listener);
  }, [breakpoint]);

  return isMobileScreen;
}
