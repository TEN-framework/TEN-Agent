"use client"

import { ICameraVideoTrack, IMicrophoneAudioTrack } from "agora-rtc-sdk-ng"
import { useAppSelector, useAppDispatch, VOICE_OPTIONS } from "@/common"
import { ITextItem, EMessageType } from "@/types"
import { rtcManager, IUserTracks, IRtcUser } from "@/manager"
import { setRoomConnected, addChatItem, setVoiceType } from "@/store/reducers/global"
import MicSection from "./micSection"
import CamSection from "./camSection"
import Agent from "./agent"
import styles from "./index.module.scss"
import { useRef, useEffect, useState, Fragment } from "react"
import { VoiceIcon } from "@/components/icons"
import CustomSelect from "@/components/customSelect"

let hasInit = false

const Rtc = () => {
  const dispatch = useAppDispatch()
  const options = useAppSelector(state => state.global.options)
  const voiceType = useAppSelector(state => state.global.voiceType)
  const agentConnected = useAppSelector(state => state.global.agentConnected)
  const { userId, channel } = options
  const [videoTrack, setVideoTrack] = useState<ICameraVideoTrack>()
  const [audioTrack, setAudioTrack] = useState<IMicrophoneAudioTrack>()
  const [remoteuser, setRemoteUser] = useState<IRtcUser>()

  useEffect(() => {
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
    console.log("[test] init")
    rtcManager.on("localTracksChanged", onLocalTracksChanged)
    rtcManager.on("textChanged", onTextChanged)
    rtcManager.on("remoteUserChanged", onRemoteUserChanged)
    await rtcManager.createTracks()
    await rtcManager.join({
      channel,
      userId
    })
    await rtcManager.publish()
    dispatch(setRoomConnected(true))
    hasInit = true
  }

  const destory = async () => {
    console.log("[test] destory")
    rtcManager.off("textChanged", onTextChanged)
    rtcManager.off("localTracksChanged", onLocalTracksChanged)
    rtcManager.off("remoteUserChanged", onRemoteUserChanged)
    await rtcManager.destroy()
    dispatch(setRoomConnected(false))
    hasInit = false
  }

  const onRemoteUserChanged = (user: IRtcUser) => {
    console.log("[test] onRemoteUserChanged", user)
    setRemoteUser(user)
  }

  const onLocalTracksChanged = (tracks: IUserTracks) => {
    console.log("[test] onLocalTracksChanged", tracks)
    const { videoTrack, audioTrack } = tracks
    if (videoTrack) {
      setVideoTrack(videoTrack)
    }
    if (audioTrack) {
      setAudioTrack(audioTrack)
    }
  }

  const onTextChanged = (text: ITextItem) => {
    if (text.dataType == "transcribe") {
      const isAgent = Number(text.uid) != Number(userId)
      dispatch(addChatItem({
        userId: text.uid,
        text: text.text,
        type: isAgent ? EMessageType.AGENT : EMessageType.USER,
        isFinal: text.isFinal,
        time: text.time
      }))
    }
  }

  const onVoiceChange = (value: any) => {
    dispatch(setVoiceType(value))
  }


  return <section className={styles.rtc}>
    <div className={styles.header}>
      <span className={styles.text}>Audio & Video</span>
      <CustomSelect className={styles.voiceSelect}
        disabled={agentConnected}
        value={voiceType}
        prefixIcon={<VoiceIcon></VoiceIcon>}
        options={VOICE_OPTIONS} onChange={onVoiceChange}></CustomSelect>
    </div>
    {/* agent */}
    <Agent audioTrack={remoteuser?.audioTrack}></Agent>
    {/* you */}
    <div className={styles.you}>
      <div className={styles.title}>You</div>
      {/* microphone */}
      <MicSection audioTrack={audioTrack}></MicSection>
      {/* camera */}
      <CamSection videoTrack={videoTrack}></CamSection>
    </div>
  </section>
}


export default Rtc;
