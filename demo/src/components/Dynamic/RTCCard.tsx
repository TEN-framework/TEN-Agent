"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { ICameraVideoTrack, ILocalVideoTrack, IMicrophoneAudioTrack } from "agora-rtc-sdk-ng"
import { useAppSelector, useAppDispatch } from "@/common/hooks"
import { isVoiceGenderSupported, VideoSourceType } from "@/common/constant"
import { ITextItem, EMessageType } from "@/types"
import { rtcManager, IUserTracks, IRtcUser } from "@/manager"
import {
  setRoomConnected,
  addChatItem,
  setVoiceType,
  setOptions,
} from "@/store/reducers/global"
import AgentVoicePresetSelect from "@/components/Agent/VoicePresetSelect"
import AgentView from "@/components/Agent/View"
import MicrophoneBlock from "@/components/Agent/Microphone"
import CameraBlock from "@/components/Agent/Camera"
import VideoBlock from "@/components/Agent/Camera"

let hasInit: boolean = false

export default function RTCCard(props: { className?: string }) {
  const { className } = props

  const dispatch = useAppDispatch()
  const options = useAppSelector((state) => state.global.options)
  const voiceType = useAppSelector((state) => state.global.voiceType)
  const selectedGraphId = useAppSelector((state) => state.global.graphName)
  const { userId, channel } = options
  const [videoTrack, setVideoTrack] = React.useState<ICameraVideoTrack>()
  const [audioTrack, setAudioTrack] = React.useState<IMicrophoneAudioTrack>()
  const [screenTrack, setScreenTrack] = React.useState<ILocalVideoTrack>()
  const [remoteuser, setRemoteUser] = React.useState<IRtcUser>()
  const [videoSourceType, setVideoSourceType] = React.useState<VideoSourceType>(VideoSourceType.CAMERA)

  React.useEffect(() => {
    if (!options.channel) {
      return
    }
    if (hasInit) {
      return
    }

    init()

    return () => {
      if (hasInit) {
        destory()
      }
    }
  }, [options.channel])

  const init = async () => {
    console.log("[rtc] init")
    rtcManager.on("localTracksChanged", onLocalTracksChanged)
    rtcManager.on("textChanged", onTextChanged)
    rtcManager.on("remoteUserChanged", onRemoteUserChanged)
    await rtcManager.createCameraTracks()
    await rtcManager.createMicrophoneTracks()
    await rtcManager.join({
      channel,
      userId,
    })
    dispatch(
      setOptions({
        ...options,
        appId: rtcManager.appId ?? "",
        token: rtcManager.token ?? "",
      }),
    )
    await rtcManager.publish()
    dispatch(setRoomConnected(true))
    hasInit = true
  }

  const destory = async () => {
    console.log("[rtc] destory")
    rtcManager.off("textChanged", onTextChanged)
    rtcManager.off("localTracksChanged", onLocalTracksChanged)
    rtcManager.off("remoteUserChanged", onRemoteUserChanged)
    await rtcManager.destroy()
    dispatch(setRoomConnected(false))
    hasInit = false
  }

  const onRemoteUserChanged = (user: IRtcUser) => {
    console.log("[rtc] onRemoteUserChanged", user)
    setRemoteUser(user)
  }

  const onLocalTracksChanged = (tracks: IUserTracks) => {
    console.log("[rtc] onLocalTracksChanged", tracks)
    const { videoTrack, audioTrack, screenTrack } = tracks
    setVideoTrack(videoTrack)
    setScreenTrack(screenTrack)
    if (audioTrack) {
      setAudioTrack(audioTrack)
    }
  }

  const onTextChanged = (text: ITextItem) => {
    console.log("[rtc] onTextChanged", text)
    if (text.dataType == "transcribe") {
      const isAgent = Number(text.uid) != Number(userId)
      dispatch(
        addChatItem({
          userId: text.uid,
          text: text.text,
          type: isAgent ? EMessageType.AGENT : EMessageType.USER,
          isFinal: text.isFinal,
          time: text.time,
        }),
      )
    }
  }

  const onVoiceChange = (value: any) => {
    dispatch(setVoiceType(value))
  }

  const onVideoSourceTypeChange = async (value: VideoSourceType) => {
    await rtcManager.switchVideoSource(value)
    setVideoSourceType(value)
  }

  return (
    <>
      <div className={cn("flex-shrink-0", "overflow-y-auto", className)}>
        <div className="flex h-full w-full flex-col">
          {/* -- Agent */}
          <div className="w-full">
            <div className="flex w-full items-center justify-between p-2">
              <h2 className="mb-2 text-xl font-semibold">Audio & Video</h2>
              {
                isVoiceGenderSupported(selectedGraphId) ?
                <AgentVoicePresetSelect /> :
                null}
            </div>
            <AgentView audioTrack={remoteuser?.audioTrack} />
          </div>

          {/* -- You */}
          <div className="w-full space-y-2 px-2">
            <MicrophoneBlock audioTrack={audioTrack} />
            <VideoBlock 
              cameraTrack={videoTrack}
              screenTrack={screenTrack}
              videoSourceType={videoSourceType}
              onVideoSourceChange={onVideoSourceTypeChange}
            />
          </div>
        </div>
      </div>
    </>
  )
}
