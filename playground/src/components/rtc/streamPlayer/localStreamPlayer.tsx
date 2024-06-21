"use client"

import {
  ICameraVideoTrack,
  IMicrophoneAudioTrack,
  IRemoteAudioTrack,
  IRemoteVideoTrack,
  VideoPlayerConfig,
} from "agora-rtc-sdk-ng"
import { useRef, useState, useLayoutEffect, forwardRef, useEffect, useMemo } from "react"

import styles from "./index.module.scss"

interface StreamPlayerProps {
  videoTrack?: ICameraVideoTrack
  audioTrack?: IMicrophoneAudioTrack
  style?: React.CSSProperties
  fit?: "cover" | "contain" | "fill"
  onClick?: () => void
  mute?: boolean
}

export const LocalStreamPlayer = forwardRef((props: StreamPlayerProps, ref) => {
  const { videoTrack, audioTrack, mute = false, style = {}, fit = "cover", onClick = () => { } } = props
  const vidDiv = useRef(null)

  useLayoutEffect(() => {
    const config = { fit } as VideoPlayerConfig
    if (mute) {
      videoTrack?.stop()
    } else {
      if (!videoTrack?.isPlaying) {
        videoTrack?.play(vidDiv.current!, config)
      }
    }

    return () => {
      videoTrack?.stop()
    }
  }, [videoTrack, fit, mute])

  // local audio track need not to be played
  // useLayoutEffect(() => {}, [audioTrack, localAudioMute])

  return <div className={styles.streamPlayer} style={style} ref={vidDiv} onClick={onClick}></div>
})
