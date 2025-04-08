import { IOptions, ITrulienceSettings } from "@/types"
import { OPTIONS_KEY, DEFAULT_OPTIONS, TRULIENCE_SETTINGS_KEY, DEFAULT_TRULIENCE_OPTIONS } from "./constant"

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


export const getTrulienceSettingsFromLocal = () => {
  if (typeof window !== "undefined") {
    const data = localStorage.getItem(TRULIENCE_SETTINGS_KEY)
    if (data) {
      return JSON.parse(data)
    }
  }
  return DEFAULT_TRULIENCE_OPTIONS
}

export const setTrulienceSettingsToLocal = (settings: ITrulienceSettings) => {
  if (typeof window !== "undefined") {
    localStorage.setItem(TRULIENCE_SETTINGS_KEY, JSON.stringify(settings))
  }
}