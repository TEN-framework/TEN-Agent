import { IOptions } from "@/types"
import { OPTIONS_KEY, DEFAULT_OPTIONS } from "./constant"

export const getOptionsFromLocal = () => {
  if (typeof window !== "undefined") {
    const data = localStorage.getItem(OPTIONS_KEY)
    if (data) {
      return JSON.parse(data)
    }
  }
  return DEFAULT_OPTIONS
}

export const setOptionsToLocal = (options: IOptions) => {
  if (typeof window !== "undefined") {
    localStorage.setItem(OPTIONS_KEY, JSON.stringify(options))
  }
}