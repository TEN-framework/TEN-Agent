"use client"

import { ReactNode, useEffect } from "react"
import { useAppDispatch, getOptionsFromLocal, getRandomChannel, getRandomUserId } from "@/common"
import { setOptions, reset } from "@/store/reducers/global"

interface AuthInitializerProps {
  children: ReactNode;
}

const AuthInitializer = (props: AuthInitializerProps) => {
  const { children } = props;
  const dispatch = useAppDispatch()

  useEffect(() => {
    if (typeof window !== "undefined") {
      const options = getOptionsFromLocal()
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
    }
  }, [dispatch])

  return children
}


export default AuthInitializer;
