"use client"

import CamSelect from "./camSelect"
import { CamIcon } from "@/components/icons"
import styles from "./index.module.scss"
import { ICameraVideoTrack } from 'agora-rtc-sdk-ng';
import { LocalStreamPlayer } from "../streamPlayer"
import { useState, useEffect, useMemo } from 'react';
import { useSmallScreen } from "@/common"

interface CamSectionProps {
  videoTrack?: ICameraVideoTrack
}

const CamSection = (props: CamSectionProps) => {
  const { videoTrack } = props
  const [videoMute, setVideoMute] = useState(false)
  const { xs } = useSmallScreen()

  const CamText = useMemo(() => {
    return xs ? "CAM" : "CAMERA"
  }, [xs])

  useEffect(() => {
    videoTrack?.setMuted(videoMute)
  }, [videoTrack, videoMute])

  const onClickMute = () => {
    setVideoMute(!videoMute)
  }

  return <div className={styles.camera}>
    <div className={styles.select}>
      <span className={styles.text}>{CamText}</span>
      <span className={styles.iconWrapper} onClick={onClickMute}>
        <CamIcon active={!videoMute} width={20} height={20} viewBox="0 0 24 24"></CamIcon>
      </span>
      <CamSelect videoTrack={videoTrack}></CamSelect>
    </div>
    <div className={styles.view}>
      <LocalStreamPlayer videoTrack={videoTrack}></LocalStreamPlayer>
    </div>
  </div>
}


export default CamSection;
