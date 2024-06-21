"use client"

import { useEffect, useMemo, useState } from "react"
import { useMultibandTrackVolume, useSmallScreen } from "@/common"
import AudioVisualizer from "../audioVisualizer"
import { MicIcon } from "@/components/icons"
import styles from "./index.module.scss"
import { IMicrophoneAudioTrack } from 'agora-rtc-sdk-ng';
import MicSelect from "./micSelect";

interface MicSectionProps {
  audioTrack?: IMicrophoneAudioTrack
}

const MicSection = (props: MicSectionProps) => {
  const { audioTrack } = props
  const [audioMute, setAudioMute] = useState(false)
  const [mediaStreamTrack, setMediaStreamTrack] = useState<MediaStreamTrack>()
  const { xs } = useSmallScreen()

  const MicText = useMemo(() => { 
    return xs ? "MIC" : "MICROPHONE"
  }, [xs])

  useEffect(() => {
    audioTrack?.on("track-updated", onAudioTrackupdated)
    if (audioTrack) {
      setMediaStreamTrack(audioTrack.getMediaStreamTrack())
    }

    return () => {
      audioTrack?.off("track-updated", onAudioTrackupdated)
    }
  }, [audioTrack])

  useEffect(() => {
    audioTrack?.setMuted(audioMute)
  }, [audioTrack, audioMute])

  const subscribedVolumes = useMultibandTrackVolume(mediaStreamTrack, 20);

  const onAudioTrackupdated = (track: MediaStreamTrack) => {
    console.log("[test] audio track updated", track)
    setMediaStreamTrack(track)
  }

  const onClickMute = () => {
    setAudioMute(!audioMute)
  }

  return <div className={styles.microphone}>
    <div className={styles.select}>
      <span className={styles.text}>{MicText}</span>
      <span className={styles.iconWrapper} onClick={onClickMute}>
        <MicIcon active={!audioMute} width={20} height={20} viewBox="0 0 24 24"></MicIcon>
      </span>
      <MicSelect audioTrack={audioTrack}></MicSelect>
    </div>
    <div className={styles.view}>
      <AudioVisualizer
        type="user"
        barWidth={4}
        minBarHeight={2}
        maxBarHeight={50}
        frequencies={subscribedVolumes}
        borderRadius={2}
        gap={4}></AudioVisualizer>
    </div>
  </div>
}


export default MicSection;
