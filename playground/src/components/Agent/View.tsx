"use client"

import { useMultibandTrackVolume } from "@/common"
import { cn } from "@/lib/utils"
// import AudioVisualizer from "../audioVisualizer"
import { IMicrophoneAudioTrack, IRemoteAudioTrack, IRemoteVideoTrack } from "agora-rtc-sdk-ng"
import AudioVisualizer from "@/components/Agent/AudioVisualizer"
import { useEffect } from "react"

export interface AgentViewProps {
  audioTrack?: IMicrophoneAudioTrack | IRemoteAudioTrack,
  videoTrack?: IRemoteVideoTrack
}

export default function AgentView(props: AgentViewProps) {
  const { audioTrack, videoTrack } = props

  const subscribedVolumes = useMultibandTrackVolume(audioTrack, 12)

  useEffect(() => {
    if (videoTrack) {
      // videoTrack.play("agent-video-player")
      // Check if this is available in your Agora SDK version
      videoTrack.play("agent-video-player", { fit: "contain" });
    }
    return () => {
      if (videoTrack) {
        videoTrack.stop()
      }
    }
  }, [videoTrack])

  return (
    videoTrack ? (
      <div
        className={cn(
          "flex h-full w-full flex-col items-center justify-center",
          "bg-[#0F0F11] bg-gradient-to-br from-[rgba(27,66,166,0.16)] via-[rgba(27,45,140,0.00)] to-[#11174E] shadow-[0px_3.999px_48.988px_0px_rgba(0,7,72,0.12)] backdrop-blur-[7px]",
        )}
      >
        <div id="agent-video-player" className="h-full w-full bg-[#11174E] rounded-lg" />
      </div>
    ) : (
      <div
        className={cn(
          "flex h-full   w-full flex-col items-center justify-center px-4 py-5",
          "bg-[#0F0F11] bg-gradient-to-br from-[rgba(27,66,166,0.16)] via-[rgba(27,45,140,0.00)] to-[#11174E] shadow-[0px_3.999px_48.988px_0px_rgba(0,7,72,0.12)] backdrop-blur-[7px]",
        )}
      >
        <div className="mb-2 text-lg font-semibold text-[#EAECF0]">Agent</div>
        <div className="mt-8 h-14 w-full">
          <AudioVisualizer
            type="agent"
            frequencies={subscribedVolumes}
            barWidth={6}
            minBarHeight={6}
            maxBarHeight={56}
            borderRadius={2}
            gap={6}
          />
        </div>
      </div>
    )
  )
}
