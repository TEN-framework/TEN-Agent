"use client"

import { ReactNode, useEffect } from "react"
import { useAppDispatch, getOptionsFromLocal } from "@/common"
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
      if (options) {
        dispatch(reset())
        dispatch(setOptions(options))
      }
    }
  }, [dispatch])

  return children
}


export default AuthInitializer;
