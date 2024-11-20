"use client"

import { ICameraVideoTrack, IMicrophoneAudioTrack } from "agora-rtc-sdk-ng"
import { useAppSelector, useAppDispatch, VOICE_OPTIONS } from "@/common"
import { ITextItem } from "@/types"
import { rtcManager, IUserTracks, IRtcUser } from "@/manager"
import { setRoomConnected, addChatItem, setVoiceType } from "@/store/reducers/global"
import MicSection from "./micSection"
import CamSection from "./camSection"
import Avatar from "./avatar"
import styles from "./index.module.scss"
import { useRef, useEffect, useState, Fragment } from "react"
//import { Avatar } from "antd"

let hasInit = false

const Rtc = () => {
  const dispatch = useAppDispatch()
  const options = useAppSelector(state => state.global.options)
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
    if (text.dataType == "transcribe" && text.text.indexOf('SSML_')==-1) { 
      const isAgent = Number(text.uid) != Number(userId)
      dispatch(addChatItem({
        userId: text.uid,
        text: text.text.replace(/\bSSML_\w*\b/g, '').replace(/\s+/g, ' ').trim(),
        type: isAgent ? "agent" : "user",
        isFinal: text.isFinal,
        time: text.time
      }))
    }
  }


  return <section className={styles.rtc}>

    {/* you */}
    <div className={styles.you}>
      {/* microphone */}
      <MicSection audioTrack={audioTrack}></MicSection>
      {/* camera */}
      <CamSection videoTrack={videoTrack}></CamSection>
    </div>
  </section>
}


export default Rtc;
