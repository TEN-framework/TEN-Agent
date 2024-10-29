import { IOptions } from "@/types"
import { OPTIONS_KEY, DEFAULT_OPTIONS, OVERRIDEN_PROPERTIES_KEY } from "./constant"

export const getOptionsFromLocal = () => {
  if (typeof window !== "undefined") {
    const data = localStorage.getItem(OPTIONS_KEY)
    if (data) {
      return JSON.parse(data)
    }
  }
  return DEFAULT_OPTIONS
}

export const getOverridenPropertiesFromLocal = () => {
  if (typeof window !== "undefined") {
    const data = localStorage.getItem(OVERRIDEN_PROPERTIES_KEY)
    if (data) {
      return JSON.parse(data)
    }
  }
  return {}
}

export const setOptionsToLocal = (options: IOptions) => {
  if (typeof window !== "undefined") {
    localStorage.setItem(OPTIONS_KEY, JSON.stringify(options))
  }
}

export const setOverridenPropertiesToLocal = (properties: Record<string, any>) => {
  if (typeof window !== "undefined") {
    localStorage.setItem(OVERRIDEN_PROPERTIES_KEY, JSON.stringify(properties))
  }
}
