"use client";

import React from "react";
import { rtcManager } from "@/manager"
import { NetworkQuality } from "agora-rtc-sdk-ng"
import { useEffect, useState } from "react"
import { NetworkIcon } from "@/components/icons"

interface NetworkProps {
  style?: React.CSSProperties
}

const NetWork = (props: NetworkProps) => {
  const { style } = props

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
    <span style={style}>
      <NetworkIcon level={networkQuality?.uplinkNetworkQuality}></NetworkIcon>
    </span>
  )
}

export default NetWork
