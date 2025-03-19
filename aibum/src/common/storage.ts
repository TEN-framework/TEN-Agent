export const OPTIONS_KEY = "__options__";

export interface IOptions {
  channel: string;
  userId: string;
  appId: string;
  token: string;
}

export const DEFAULT_OPTIONS: IOptions = {
  channel: "",
  userId: "",
  appId: "",
  token: "",
};

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