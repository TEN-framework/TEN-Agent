"use client"

import { ReactNode, useEffect } from "react"
import { useAppDispatch, getOptionsFromLocal } from "@/common"
import { setOptions, reset, setAgentSettings } from "@/store/reducers/global"

interface AuthInitializerProps {
  children: ReactNode;
}

const AuthInitializer = (props: AuthInitializerProps) => {
  const { children } = props;
  const dispatch = useAppDispatch()

  useEffect(() => {
    if (typeof window !== "undefined") {
      const data = getOptionsFromLocal()
      if (data) {
        dispatch(reset())
        dispatch(setOptions(data.options))
        dispatch(setAgentSettings(data.settings))
      }
    }
  }, [dispatch])

  return children
}


export default AuthInitializer;
