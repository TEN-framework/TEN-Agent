import { IAgentSettings, IOptions, ICozeSettings, IDifySettings } from "@/types"
import {
  OPTIONS_KEY,
  DEFAULT_OPTIONS,
  AGENT_SETTINGS_KEY,
  DEFAULT_AGENT_SETTINGS,
  COZE_SETTINGS_KEY,
  DEFAULT_COZE_SETTINGS,
  DIFY_SETTINGS_KEY,
  DEFAULT_DIFY_SETTINGS,
} from "./constant"

export const getOptionsFromLocal = (): {
  options: IOptions
  settings: IAgentSettings
  cozeSettings: ICozeSettings
  difySettings: IDifySettings
} => {
  let data = {
    options: DEFAULT_OPTIONS,
    settings: DEFAULT_AGENT_SETTINGS,
    cozeSettings: DEFAULT_COZE_SETTINGS,
    difySettings: DEFAULT_DIFY_SETTINGS,
  }
  if (typeof window !== "undefined") {
    const options = localStorage.getItem(OPTIONS_KEY)
    if (options) {
      data.options = JSON.parse(options)
    }
    const settings = localStorage.getItem(AGENT_SETTINGS_KEY)
    if (settings) {
      data.settings = JSON.parse(settings)
    }
    const cozeSettings = localStorage.getItem(COZE_SETTINGS_KEY)
    if (cozeSettings) {
      data.cozeSettings = JSON.parse(cozeSettings)
    }
    const difySettings = localStorage.getItem(DIFY_SETTINGS_KEY)
    if (difySettings) {
      data.difySettings = JSON.parse(difySettings)
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

export const setCozeSettingsToLocal = (settings: ICozeSettings) => {
  if (typeof window !== "undefined") {
    localStorage.setItem(COZE_SETTINGS_KEY, JSON.stringify(settings))
  }
}

export const setDifySettingsToLocal = (settings: IDifySettings) => {
  if (typeof window !== "undefined") {
    localStorage.setItem(DIFY_SETTINGS_KEY, JSON.stringify(settings))
  }
}

export const resetSettingsByKeys = (keys: string | string[]) => {
  if (typeof window !== "undefined") {
    if (Array.isArray(keys)) {
      keys.forEach((key) => {
        localStorage.removeItem(key)
      })
    } else {
      localStorage.removeItem(keys)
    }
  }
}

export const resetCozeSettings = () => {
  resetSettingsByKeys(COZE_SETTINGS_KEY)
}

export const resetDifySettings = () => {
  resetSettingsByKeys(DIFY_SETTINGS_KEY)
}
