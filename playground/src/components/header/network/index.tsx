"use client";

import { rtcManager } from "@/manager"
import { NetworkQuality } from "agora-rtc-sdk-ng"
import { useEffect, useState } from "react"
import { NetworkIcon } from "@/components/icons"

const NetWork = () => {
  const [networkQuality, setNetworkQuality] = useState<NetworkQuality>()

  useEffect(() => {
    rtcManager.on("networkQuality", onNetworkQuality)

    return () => {
      rtcManager.off("networkQuality", onNetworkQuality)
    }
  }, [])

  const onNetworkQuality = (quality: NetworkQuality) => {
    setNetworkQuality(quality)
  }

  return (
    <span>
      <NetworkIcon level={networkQuality?.uplinkNetworkQuality}></NetworkIcon>
    </span>
  )
}

export default NetWork
