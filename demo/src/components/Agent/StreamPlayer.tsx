"use client"

import * as React from "react"
import {
  ICameraVideoTrack,
  ILocalVideoTrack,
  IMicrophoneAudioTrack,
  VideoPlayerConfig,
} from "agora-rtc-sdk-ng"

export interface StreamPlayerProps {
  videoTrack?: ICameraVideoTrack | ILocalVideoTrack
  audioTrack?: IMicrophoneAudioTrack
  style?: React.CSSProperties
  fit?: "cover" | "contain" | "fill"
  onClick?: () => void
  mute?: boolean
}

export const LocalStreamPlayer = React.forwardRef(
  (props: StreamPlayerProps, ref) => {
    const {
      videoTrack,
      audioTrack,
      mute = false,
      style = {},
      fit = "cover",
      onClick = () => {},
    } = props
    const vidDiv = React.useRef(null)

    React.useLayoutEffect(() => {
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

    return (
      <div
        className="relative h-full w-full overflow-hidden"
        style={style}
        ref={vidDiv}
        onClick={onClick}
      />
    )
  },
)
