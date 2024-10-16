import { LanguageOptionItem } from "@/types"

export const genRandomString = (length: number = 10) => {
  let result = '';
  const characters = 'abcdefghijklmnopqrstuvwxyz0123456789';
  const charactersLength = characters.length;

  for (let i = 0; i < length; i++) {
    result += characters.charAt(Math.floor(Math.random() * charactersLength));
  }

  return result;
}


export const getRandomUserId = (): number => {
  return Math.floor(Math.random() * 99999) + 100000
}

export const getRandomChannel = (number = 6) => {
  return "agora_" + genRandomString(number)
}


export const sleep = (ms: number) => {
  return new Promise(resolve => setTimeout(resolve, ms));
}


export const normalizeFrequencies = (frequencies: Float32Array) => {
  const normalizeDb = (value: number) => {
    const minDb = -100;
    const maxDb = -10;
    let db = 1 - (Math.max(minDb, Math.min(maxDb, value)) * -1) / 100;
    db = Math.sqrt(db);

    return db;
  };

  // Normalize all frequency values
  return frequencies.map((value) => {
    if (value === -Infinity) {
      return 0;
    }
    return normalizeDb(value);
  });
};


export const genUUID = () => {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0
    const v = c === "x" ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}


export const isMobile = () => {
  return /Mobile|iPhone|iPad|Android|Windows Phone/i.test(navigator.userAgent)
}


export const getBrowserLanguage = (): LanguageOptionItem => {
  const lang = navigator.language;

  switch (true) {
    case lang.startsWith("zh"):
      return {
        label: "Chinese",
        value: "zh-CN"
      };
    case lang.startsWith("ko"):
      return {
        label: "Korean",
        value: "ko-KR"
      };
    case lang.startsWith("ja"):
      return {
        label: "Japanese",
        value: "ja-JP"
      };
    default:
      return {
        label: "English",
        value: "en-US"
      };
  }
};