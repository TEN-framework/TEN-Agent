"use client"

import { ReactNode, useEffect } from "react"
import { useAppDispatch, getOptionsFromLocal, getRandomChannel, getRandomUserId, useAppSelector, getTrulienceSettingsFromLocal } from "@/common"
import { setOptions, reset, fetchGraphDetails, setTrulienceSettings } from "@/store/reducers/global"
import { useGraphs } from "@/common/hooks";

interface AuthInitializerProps {
  children: ReactNode;
}

const AuthInitializer = (props: AuthInitializerProps) => {
  const { children } = props;
  const dispatch = useAppDispatch()
  const { initialize } = useGraphs()
  const selectedGraphId = useAppSelector((state) => state.global.selectedGraphId)
  const graphList = useAppSelector((state) => state.global.graphList)

  useEffect(() => {
    if (typeof window !== "undefined") {
      const options = getOptionsFromLocal()
      const trulienceSettings = getTrulienceSettingsFromLocal()
      initialize()
      if (options && options.channel) {
        dispatch(reset())
        dispatch(setOptions(options))
        dispatch(setTrulienceSettings(trulienceSettings))
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
      const graph = graphList.find((g) => g.uuid === selectedGraphId)
      if (!graph) {
        return
      }
      dispatch(fetchGraphDetails(graph));
    }
  }, [selectedGraphId, graphList, dispatch]); // Automatically fetch details when `selectedGraphId` changes

  return children
}


export default AuthInitializer;
