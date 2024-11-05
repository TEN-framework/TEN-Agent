"use client"

import { ReactNode, useEffect } from "react"
import { useAppDispatch, getOptionsFromLocal, getRandomChannel, getRandomUserId, getOverridenPropertiesFromLocal } from "@/common"
import { setOptions, reset, setOverridenProperties } from "@/store/reducers/global"

interface AuthInitializerProps {
  children: ReactNode;
}

const AuthInitializer = (props: AuthInitializerProps) => {
  const { children } = props;
  const dispatch = useAppDispatch()

  useEffect(() => {
    if (typeof window !== "undefined") {
      const options = getOptionsFromLocal()
      const overridenProperties = getOverridenPropertiesFromLocal()
      if (options && options.channel) {
        dispatch(reset())
        dispatch(setOptions(options))
      } else {
        dispatch(reset())
        dispatch(setOptions({
          channel: getRandomChannel(),
          userId: getRandomUserId(),
        }))
      }
      dispatch(setOverridenProperties(overridenProperties))
    }
  }, [dispatch])

  return children
}


export default AuthInitializer;
