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

export const deepMerge = (target: Record<string, any>, source: Record<string, any>): Record<string, any> => {
  for (const key of Object.keys(source)) {
    if (source[key] instanceof Object && key in target) {
      Object.assign(source[key], deepMerge(target[key], source[key]));
    }
  }
  // Merge source into target
  return { ...target, ...source };
}