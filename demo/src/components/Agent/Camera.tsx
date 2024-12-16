"use client"

import * as React from "react"
// import CamSelect from "./camSelect"
import { CamIconByStatus } from "@/components/Icon"
import AgoraRTC, { ICameraVideoTrack, ILocalVideoTrack } from "agora-rtc-sdk-ng"
// import { LocalStreamPlayer } from "../streamPlayer"
// import { useSmallScreen } from "@/common"
import {
  DeviceSelect,
} from "@/components/Agent/Microphone"
import { LocalStreamPlayer } from "@/components/Agent/StreamPlayer"
import { VIDEO_SOURCE_OPTIONS, VideoSourceType } from "@/common/constant"
import { MonitorIcon, MonitorXIcon } from "lucide-react"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../ui/select"
import { Button } from "../ui/button"


export const ScreenIconByStatus = (
  props: React.SVGProps<SVGSVGElement> & { active?: boolean; color?: string },
) => {
  const { active, color, ...rest } = props
  if (active) {
    return <MonitorIcon color={color || "#3D53F5"} {...rest} />
  }
  return <MonitorXIcon color={color || "#667085"} {...rest} />
}

export function VideoDeviceWrapper(props: {
  children: React.ReactNode
  title: string
  Icon: (
    props: React.SVGProps<SVGSVGElement> & { active?: boolean },
  ) => React.ReactNode
  onIconClick: () => void
  videoSourceType: VideoSourceType
  onVideoSourceChange: (value: VideoSourceType) => void
  isActive: boolean
  select?: React.ReactNode
}) {
  const { Icon, onIconClick, isActive, select, children, onVideoSourceChange, videoSourceType } = props

  return (
    <div className="flex flex-col">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="text-sm font-medium">{props.title}</div>
          <div className="w-[150px]">
            <Select value={videoSourceType} onValueChange={onVideoSourceChange}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {VIDEO_SOURCE_OPTIONS.map((item) => (
                  <SelectItem key={item.value} value={item.value}>
                    {item.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="icon"
            className="border-secondary bg-transparent"
            onClick={onIconClick}
          >
            <Icon className="h-5 w-5" active={isActive} />
          </Button>
          {select}
        </div>
      </div>
      {children}
    </div>
  )
}

export default function VideoBlock(props: {
  videoSourceType:VideoSourceType,
  onVideoSourceChange:(value: VideoSourceType) => void,
  cameraTrack?: ICameraVideoTrack,
  screenTrack?: ILocalVideoTrack
}) {
  const { videoSourceType, cameraTrack, screenTrack, onVideoSourceChange } = props
  const [videoMute, setVideoMute] = React.useState(false)

  React.useEffect(() => {
    cameraTrack?.setMuted(videoMute)
    screenTrack?.setMuted(videoMute)
  }, [cameraTrack, screenTrack, videoMute])

  const onClickMute = () => {
    setVideoMute(!videoMute)
  }

  return (
    <VideoDeviceWrapper
      title="VIDEO"
      Icon={videoSourceType === VideoSourceType.CAMERA ? CamIconByStatus : ScreenIconByStatus}
      onIconClick={onClickMute}
      isActive={!videoMute}
      videoSourceType={videoSourceType}
      onVideoSourceChange={onVideoSourceChange}
      select={videoSourceType === VideoSourceType.CAMERA ? <CamSelect videoTrack={cameraTrack} /> : <div className="w-[180px]" />}
    >
      <div className="my-3 h-52 w-full overflow-hidden rounded-lg">
        <LocalStreamPlayer videoTrack={videoSourceType === VideoSourceType.CAMERA ? cameraTrack : screenTrack} />
      </div>
    </VideoDeviceWrapper>
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
