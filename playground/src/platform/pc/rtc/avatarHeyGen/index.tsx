// components/AvatarHeyGen.tsx

"use client";

import React, { useRef, useState, useEffect } from "react";
import { LoadingOutlined } from "@ant-design/icons";
import StreamingAvatar, {
  AvatarQuality,
  StreamingEvents,
  VoiceEmotion,
} from "@heygen/streaming-avatar";
import styles from "./index.module.scss"; // Using the existing index.module.scss

const AvatarHeyGen: React.FC = () => {
  const [isLoading, setIsLoading] = useState(true);
  const [stream, setStream] = useState<MediaStream | undefined>(undefined);
  const [isUserTalking, setIsUserTalking] = useState(false);
  const [debug, setDebug] = useState<string | undefined>(undefined);

  const mediaStreamRef = useRef<HTMLVideoElement>(null);
  const avatarRef = useRef<StreamingAvatar | null>(null);

  // Fetch Access Token from the integrated API route
  const fetchAccessToken = async (): Promise<string | null> => {
    try {
      const response = await fetch("/api/get-heygen-access-token", {
        method: "POST",
      });

      if (!response.ok) {
        const errorData = await response.json();
        console.error("Error fetching access token:", errorData);
        setDebug("Failed to fetch access token.");
        return null;
      }

      const data = await response.json();
      return data.accessToken;
    } catch (error: any) {
      console.error("Error fetching access token:", error);
      setDebug("An error occurred while fetching access token.");
      return null;
    }
  };

  // Initialize HeyGen Avatar on component mount
  useEffect(() => {
    const initializeAvatar = async () => {
      try {
        const accessToken = await fetchAccessToken();

        if (!accessToken) {
          setIsLoading(false);
          return;
        }

        // Initialize StreamingAvatar with the fetched access token
        avatarRef.current = new StreamingAvatar({
          token: accessToken,
        });

        // Event Handlers
        avatarRef.current.on(StreamingEvents.AVATAR_START_TALKING, (e) => {
          console.log("Avatar started talking", e);
        });

        avatarRef.current.on(StreamingEvents.AVATAR_STOP_TALKING, (e) => {
          console.log("Avatar stopped talking", e);
        });

        avatarRef.current.on(StreamingEvents.STREAM_READY, (event) => {
          console.log(">>>>> Stream ready:", event.detail);
          setStream(event.detail);
          setIsLoading(false);
        });

        avatarRef.current.on(StreamingEvents.STREAM_DISCONNECTED, () => {
          console.log("Stream disconnected");
          endSession();
        });

        avatarRef.current.on(StreamingEvents.USER_START, () => {
          console.log(">>>>> User started talking");
          setIsUserTalking(true);
        });

        avatarRef.current.on(StreamingEvents.USER_STOP, () => {
          console.log(">>>>> User stopped talking");
          setIsUserTalking(false);
        });

        // Create and start the avatar session with updated parameters
        const response = await avatarRef.current.createStartAvatar({
          quality: AvatarQuality.High,
          avatarName: "josh_lite3_20230714", // Updated avatarName
          knowledgeId: "", // Updated knowledgeId to empty string
          voice: {
            voiceId: "42d598350e7a4d339a3875eb1b0169fd",
            rate: 1.0, // Updated voice rate
            emotion: VoiceEmotion.SERIOUS, // Updated voice emotion
          },
          language: "en", // Language code
          disableIdleTimeout: true,

        });

        console.log("Avatar Session Started:", response);

        // Start voice chat automatically
        //   await avatarRef.current.startVoiceChat({
        //     useSilencePrompt: false,
        //   });

        window.avatarRef = avatarRef.current;
      } catch (error: any) {
        console.error("Error initializing HeyGen avatar:", error);
        setDebug(error.message);
        setIsLoading(false);
      }
    };

    initializeAvatar();

    // Cleanup on component unmount
    return () => {
      endSession();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Empty dependency array ensures this runs once on mount

  // Handle MediaStream for video playback
  useEffect(() => {
    if (stream && mediaStreamRef.current) {
      mediaStreamRef.current.srcObject = stream;
      mediaStreamRef.current.onloadedmetadata = () => {
        mediaStreamRef.current!.play();
        console.log("Playing avatar stream");
      };
    }
  }, [stream]);

  // Function to end the avatar session
  const endSession = async () => {
    try {
      if (avatarRef.current) {
        await avatarRef.current.stopAvatar();
        setStream(undefined);
        console.log("Avatar session ended");
      }
    } catch (error: any) {
      console.error("Error ending avatar session:", error);
      setDebug(error.message);
    }
  };

  return (
    <div className={styles.avatar}>
      {isLoading && (
        <div className={styles.loader}>
          <LoadingOutlined style={{ fontSize: 28 }} />
        </div>
      )}
      {stream && (
        <div className={styles.view}>
          <video
            ref={mediaStreamRef}
            autoPlay
            playsInline
            className={styles.avatarVideo}
          >
            <track kind="captions" />
          </video>
        </div>
      )}
      {debug && <div className={styles.debugInfo}>{debug}</div>}
    </div>
  );
};

export default React.memo(AvatarHeyGen);
