"use client"

import { ReactNode, useEffect } from "react"
import { useAppDispatch, getOptionsFromLocal, getRandomChannel, getRandomUserId, useAppSelector } from "@/common"
import { setOptions, reset, fetchGraphDetails } from "@/store/reducers/global"
import { useGraphManager } from "@/common/graph";

interface AuthInitializerProps {
  children: ReactNode;
}

const AuthInitializer = (props: AuthInitializerProps) => {
  const { children } = props;
  const dispatch = useAppDispatch()
  const {initialize} = useGraphManager()
  const selectedGraphId = useAppSelector((state) => state.global.selectedGraphId)

  useEffect(() => {
    if (typeof window !== "undefined") {
      const options = getOptionsFromLocal()
      initialize()
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

  useEffect(() => {
    if (selectedGraphId) {
      dispatch(fetchGraphDetails(selectedGraphId));
    }
  }, [selectedGraphId, dispatch]); // Automatically fetch details when `selectedGraphId` changes

  return children
}


export default AuthInitializer;
