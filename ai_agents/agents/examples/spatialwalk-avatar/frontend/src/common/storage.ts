import type { IOptions, ISpatialwalkSettings } from "@/types";
import {
  DEFAULT_OPTIONS,
  OPTIONS_KEY,
  DEFAULT_SPATIALWALK_OPTIONS,
  SPATIALWALK_SETTINGS_KEY,
} from "./constant";

export const getOptionsFromLocal = () => {
  if (typeof window !== "undefined") {
    const data = localStorage.getItem(OPTIONS_KEY);
    if (data) {
      return JSON.parse(data);
    }
  }
  return DEFAULT_OPTIONS;
};

export const setOptionsToLocal = (options: IOptions) => {
  if (typeof window !== "undefined") {
    localStorage.setItem(OPTIONS_KEY, JSON.stringify(options));
  }
};

export const getSpatialwalkSettingsFromLocal = () => {
  if (typeof window !== "undefined") {
    const data = localStorage.getItem(SPATIALWALK_SETTINGS_KEY);
    if (data) {
      const parsed = JSON.parse(data) as Partial<ISpatialwalkSettings>;
      const merged = {
        ...DEFAULT_SPATIALWALK_OPTIONS,
        ...parsed,
      };
      // Large-window mode is always enabled in this app variant.
      merged.avatarDesktopLargeWindow = true;
      localStorage.setItem(SPATIALWALK_SETTINGS_KEY, JSON.stringify(merged));

      return merged;
    }
  }
  return DEFAULT_SPATIALWALK_OPTIONS;
};

export const setSpatialwalkSettingsToLocal = (
  settings: ISpatialwalkSettings
) => {
  if (typeof window !== "undefined") {
    localStorage.setItem(SPATIALWALK_SETTINGS_KEY, JSON.stringify(settings));
  }
};
