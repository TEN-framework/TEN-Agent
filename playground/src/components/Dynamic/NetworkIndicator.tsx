"use client"

import * as React from "react"
import { NetworkQuality } from "agora-rtc-sdk-ng"
import { rtcManager } from "@/manager"
import { NetworkIconByLevel } from "@/components/Icon"

export default function NetworkIndicator() {
  const [networkQuality, setNetworkQuality] = React.useState<NetworkQuality>()

  React.useEffect(() => {
    rtcManager.on("networkQuality", onNetworkQuality)

    return () => {
      rtcManager.off("networkQuality", onNetworkQuality)
    }
  }, [])

  const onNetworkQuality = (quality: NetworkQuality) => {
    setNetworkQuality(quality)
  }

  return (
    <NetworkIconByLevel
      level={networkQuality?.uplinkNetworkQuality}
      className="h-4 w-4 md:h-5 md:w-5"
    />
  )
}
