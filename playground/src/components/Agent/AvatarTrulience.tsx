"use client"

import React, { useEffect, useMemo, useRef, useState } from "react"
import { useAppSelector } from "@/common"
import { TrulienceAvatar } from "trulience-sdk"
import { IMicrophoneAudioTrack } from "agora-rtc-sdk-ng"

interface AvatarProps {
  audioTrack?: IMicrophoneAudioTrack
}

export default function Avatar({ audioTrack }: AvatarProps) {
  const agentConnected = useAppSelector((state) => state.global.agentConnected)
  const trulienceAvatarRef = useRef<TrulienceAvatar>(null)
  
  // Track loading progress
  const [loadProgress, setLoadProgress] = useState(0)

  // Resolve the final avatar ID from URL param or environment variable
  const finalAvatarId = useMemo(() => {
    //const urlParams = new URLSearchParams(window.location.search)
    const avatarIdFromURL = null; //urlParams.get("avatarId")
    return avatarIdFromURL || process.env.NEXT_PUBLIC_trulienceAvatarId || ""
  }, [])

  // Define any event callbacks that you need
  const eventCallbacks = useMemo(() => {
    return {
      "auth-success": (resp: string) => {
        console.log("Trulience Avatar auth-success:", resp)
      },
      "websocket-connect": (resp: string) => {
        console.log("Trulience Avatar websocket-connect:", resp)
      },
      "load-progress": (details: Record<string, any>) => {
        console.log("Trulience Avatar load-progress:", details.progress)
        setLoadProgress(details.progress)
      },
    }
  }, [])

  // Create the Trulience Avatar instance only once
  const trulienceAvatarInstance = useMemo(() => {
    return (
      <TrulienceAvatar
        url={process.env.NEXT_PUBLIC_trulienceSDK}
        ref={trulienceAvatarRef}
        avatarId={finalAvatarId}
        token={process.env.NEXT_PUBLIC_trulienceAvatarToken}
        eventCallbacks={eventCallbacks}
        width="100%"
        height="100%"
      />
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Update the Avatar’s audio stream whenever audioTrack or agentConnected changes
  useEffect(() => {
    if (trulienceAvatarRef.current) {
      if (audioTrack && agentConnected) {
        const stream = new MediaStream([audioTrack.getMediaStreamTrack()])
        trulienceAvatarRef.current.setMediaStream(null)
        trulienceAvatarRef.current.setMediaStream(stream)
        console.warn("[TrulienceAvatar] MediaStream set:", stream)
      } else if (!agentConnected) {
        const trulienceObj = trulienceAvatarRef.current.getTrulienceObject()
        trulienceObj?.sendMessageToAvatar("<trl-stop-background-audio immediate='true' />")
        trulienceObj?.sendMessageToAvatar("<trl-content position='DefaultCenter' />")
      }
    }

    // Cleanup: unset media stream
    return () => {
      trulienceAvatarRef.current?.setMediaStream(null)
    }
  }, [audioTrack, agentConnected])

  return (
    <div className="overflow-hidden rounded-lg h-full w-full">
      {/* Render the TrulienceAvatar */}
      {trulienceAvatarInstance}

      {/* Show a loader overlay while progress < 1 */}
      {loadProgress < 1 && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-black bg-opacity-80">
          {/* a simple Tailwind spinner */}
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
        </div>
      )}
    </div>
  )
}