"use client"

import { ReactNode, useEffect } from "react"
import {
  useAppDispatch,
  getOptionsFromLocal,
  getRandomUserId,
  getRandomChannel,
  genRandomString,
} from "@/common"
import {
  setOptions,
  reset,
  setAgentSettings,
  setCozeSettings,
  setDifySettings,
} from "@/store/reducers/global"

interface AuthInitializerProps {
  children: ReactNode
}

const AuthInitializer = (props: AuthInitializerProps) => {
  const { children } = props
  const dispatch = useAppDispatch()

  useEffect(() => {
    if (typeof window !== "undefined") {
      const data = getOptionsFromLocal()
      if (data && data?.options?.channel) {
        dispatch(reset())
        dispatch(setOptions(data.options))
        dispatch(setAgentSettings(data.settings))
        dispatch(setCozeSettings(data.cozeSettings))
        dispatch(setDifySettings(data.difySettings))
      } else {
        const newOptions = {
          userName: genRandomString(8),
          channel: getRandomChannel(),
          userId: getRandomUserId(),
        }
        dispatch(setOptions(newOptions))
      }
    }
  }, [dispatch])

  return children
}

export default AuthInitializer
