/**
 * 视频源类型
 */
export enum VideoSourceType {
  CAMERA = 'camera',
  SCREEN = 'screen'
}

/**
 * 合法用户映射
 */
export const VALID_USERS: { [key: string]: number } = {
  "pudgeli": 10001,
  "ben": 10002,
  "spirit": 10003,
  "jerry": 10004,
  "tongtong": 10005,
  "sam": 10006,
  "ruobin": 10007
} as const;

/**
 * 检查用户名是否合法
 */
export const isValidUser = (username: string): boolean => {
  return username in VALID_USERS;
}

/**
 * 获取用户ID
 */
export const getUserId = (username: string): number | undefined => {
  return VALID_USERS[username];
} 
