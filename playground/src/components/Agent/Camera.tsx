"use client"

import * as React from "react"
// import CamSelect from "./camSelect"
import { CamIconByStatus } from "@/components/Icon"
import AgoraRTC, { ICameraVideoTrack } from "agora-rtc-sdk-ng"
// import { LocalStreamPlayer } from "../streamPlayer"
// import { useSmallScreen } from "@/common"
import {
  CommonDeviceWrapper,
  TDeviceSelectItem,
  DEFAULT_DEVICE_ITEM,
  DeviceSelect,
} from "@/components/Agent/Microphone"
import { LocalStreamPlayer } from "@/components/Agent/StreamPlayer"

export default function CameraBlock(props: { videoTrack?: ICameraVideoTrack }) {
  const { videoTrack } = props
  const [videoMute, setVideoMute] = React.useState(false)

  React.useEffect(() => {
    videoTrack?.setMuted(videoMute)
  }, [videoTrack, videoMute])

  const onClickMute = () => {
    setVideoMute(!videoMute)
  }

  return (
    <CommonDeviceWrapper
      title="CAMERA"
      Icon={CamIconByStatus}
      onIconClick={onClickMute}
      isActive={!videoMute}
      select={<CamSelect videoTrack={videoTrack} />}
    >
      <div className="mt-3 h-full min-h-28 w-full">
        <LocalStreamPlayer videoTrack={videoTrack} />
      </div>
    </CommonDeviceWrapper>
  )
}

interface SelectItem {
  label: string
  value: string
  deviceId: string
}

const DEFAULT_ITEM: SelectItem = {
  label: "Default",
  value: "default",
  deviceId: "",
}

const CamSelect = (props: { videoTrack?: ICameraVideoTrack }) => {
  const { videoTrack } = props
  const [items, setItems] = React.useState<SelectItem[]>([DEFAULT_ITEM])
  const [value, setValue] = React.useState("default")

  React.useEffect(() => {
    if (videoTrack) {
      const label = videoTrack?.getTrackLabel()
      setValue(label)
      AgoraRTC.getCameras().then((arr) => {
        setItems(
          arr.map((item) => ({
            label: item.label,
            value: item.label,
            deviceId: item.deviceId,
          })),
        )
      })
    }
  }, [videoTrack])

  const onChange = async (value: string) => {
    const target = items.find((item) => item.value === value)
    if (target) {
      setValue(target.value)
      if (videoTrack) {
        await videoTrack.setDevice(target.deviceId)
      }
    }
  }

  return (
    <DeviceSelect
      items={items}
      value={value}
      onChange={onChange}
      placeholder="Select a camera"
    />
  )
}
