import { IAgentSettings, IOptions } from "@/types"
import { OPTIONS_KEY, DEFAULT_OPTIONS, AGENT_SETTINGS_KEY, DEFAULT_AGENT_SETTINGS } from "./constant"

export const getOptionsFromLocal = (): {options:IOptions, settings: IAgentSettings} => {
  let data = {options: DEFAULT_OPTIONS, settings: DEFAULT_AGENT_SETTINGS}
  if (typeof window !== "undefined") {
    const options = localStorage.getItem(OPTIONS_KEY)
    if (options) {
      data.options = JSON.parse(options)
    }
    const settings = localStorage.getItem(AGENT_SETTINGS_KEY)
    if (settings) {
      data.settings = JSON.parse(settings)
    }
  }
  return data
}


export const setOptionsToLocal = (options: IOptions) => {
  if (typeof window !== "undefined") {
    localStorage.setItem(OPTIONS_KEY, JSON.stringify(options))
  }
}

export const setAgentSettingsToLocal = (settings: IAgentSettings) => {
  if (typeof window !== "undefined") {
    localStorage.setItem(AGENT_SETTINGS_KEY, JSON.stringify(settings))
  }
}
