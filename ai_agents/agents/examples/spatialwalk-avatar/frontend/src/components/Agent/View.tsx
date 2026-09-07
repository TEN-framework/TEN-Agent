"use client";

// import AudioVisualizer from "../audioVisualizer"
import type { IMicrophoneAudioTrack, IRemoteAudioTrack, IRemoteVideoTrack } from "agora-rtc-sdk-ng";
import { useEffect } from "react";
import { useMultibandTrackVolume } from "@/common";
import AudioVisualizer from "@/components/Agent/AudioVisualizer";
import { cn } from "@/lib/utils";

export interface AgentViewProps {
  audioTrack?: IRemoteAudioTrack;
  videoTrack?: IRemoteVideoTrack;
}

export default function AgentView(props: AgentViewProps) {
  const { audioTrack, videoTrack } = props;

  const subscribedVolumes = useMultibandTrackVolume(audioTrack, 12);

  useEffect(() => {
    if (videoTrack) {
      const currentTrack = videoTrack;
      currentTrack.play(`remote-video-${currentTrack.getUserId()}`, { fit: "cover" });

      return () => {
        currentTrack.stop();
      };
    }
  }, [videoTrack?.getUserId()]);

  return (
    videoTrack ? (
      <div
        id={`remote-video-${videoTrack.getUserId()}`}
        className="relative w-full overflow-hidden bg-[#0F0F11]"
        style={{ minHeight: '240px', height: '240px', position: 'relative' }}
      >
      </div>
    ) : (
      <div
        className={cn(
          "flex w-full flex-col items-center justify-center px-4",
          "bg-[#0F0F11] bg-linear-to-br from-[rgba(27,66,166,0.16)] via-[rgba(27,45,140,0.00)] to-[#11174E] shadow-[0px_3.999px_48.988px_0px_rgba(0,7,72,0.12)] backdrop-blur-[7px]"
        )}
        style={{ minHeight: '240px', height: '240px' }}
      >
        <div className="mb-4 font-semibold text-[#EAECF0] text-lg">Agent</div>
        <div className="h-20 w-full">
          <AudioVisualizer
            type="agent"
            frequencies={subscribedVolumes}
            barWidth={6}
            minBarHeight={6}
            maxBarHeight={80}
            borderRadius={2}
            gap={6}
          />
        </div>
      </div>
    )
  );
}
