"use client"

import { useAppSelector, useMultibandTrackVolume } from "@/common"
import AudioVisualizer from "../audioVisualizer"
import { IMicrophoneAudioTrack } from 'agora-rtc-sdk-ng';
import styles from "./index.module.scss"

interface AgentProps {
  audioTrack?: IMicrophoneAudioTrack
}

const Agent = (props: AgentProps) => {
  const { audioTrack } = props

  const subscribedVolumes = useMultibandTrackVolume(audioTrack, 12);

  return <div className={styles.agent}>
    <div className={styles.view}>
      <AudioVisualizer
        type="agent"
        frequencies={subscribedVolumes}
        barWidth={6}
        minBarHeight={6}
        maxBarHeight={56}
        borderRadius={2}
        gap={6}></AudioVisualizer>
    </div>
  </div>

}


export default Agent;
