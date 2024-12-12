// components/AvatarHeyGen.tsx

"use client";

import React, { useRef, useState, useEffect } from "react";
import { LoadingOutlined } from "@ant-design/icons";
import StreamingAvatar, {
  AvatarQuality,
  StreamingEvents,
  TaskMode,
  TaskType,
  VoiceEmotion,
} from "@heygen/streaming-avatar";
import styles from "./index.module.scss"; // Using the existing index.module.scss
import { rtcManager } from "@/manager";
import { ITextItem } from "@/types";
import { useAppDispatch, useAppSelector, useMultibandTrackVolume } from "@/common"

const AvatarHeyGen: React.FC = () => {
  var lastChatTime = 0;
  const options = useAppSelector(state => state.global.options)
  const { userId } = options

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

  useEffect(() => {
    // Ensure the listener is added only once
    // if (avatarRef.current) {
    console.error('adding listener', avatarRef);
    rtcManager.on("textChanged", (textItem: ITextItem) => {
      if (textItem.isFinal && textItem.dataType == "transcribe" && textItem.time != lastChatTime) {
        const isAgent = Number(textItem.uid) != Number(userId);
        if (textItem.text.includes('SSML_CHESSBOARD')) {
          const newText = textItem.text.replace(/SSML_CHESSBOARD/g, '');
          let arr = document.querySelectorAll('iframe');
          if (arr && arr[0] && arr[0].contentWindow) {
            console.error('new positions', newText);
            arr[0].contentWindow.postMessage({ type: 'updateChessboard', fen: newText }, '*');
          }
        }
        else if (!textItem.text.includes('SSML') && isAgent) {
          lastChatTime = textItem.time;
          console.error("SPEAK ", textItem.text);
          //avatarRef.current?.speak({ text: 'ok', taskType: "repeat" });
          avatarRef.current?.interrupt();
          avatarRef.current?.speak({ text: textItem.text, taskMode: TaskMode.ASYNC, taskType: TaskType.REPEAT });
        }
      }
    });
    // }
  }, []);

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

        const urlParams = new URLSearchParams(window.location.search);
        const avatarIdFromURL = urlParams.get('avatarId');
        const finalAvatarId = avatarIdFromURL || process.env.NEXT_PUBLIC_avatarId || 'Wayne_20240711';


        // Create and start the avatar session with updated parameters
        const response = await avatarRef.current.createStartAvatar({
          quality: AvatarQuality.Medium,
          //avatarName: "josh_lite3_20230714", // Updated avatarName
          avatarName: finalAvatarId, // Updated avatarName          
          voice: {
            voiceId: "35f6b6ac010849d38cfc99dc25e0e4b3",
            rate: 1.1, // Updated voice rate
            emotion: VoiceEmotion.FRIENDLY, // Updated voice emotion
          },
          language: "en",
          disableIdleTimeout: false,

        });

        console.log("Avatar Session Started:", response);

        // Start voice chat automatically
        //   await avatarRef.current.startVoiceChat({
        //     useSilencePrompt: false,
        //   });


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
