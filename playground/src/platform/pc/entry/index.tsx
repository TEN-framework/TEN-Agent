// src/apis/PCEntry.tsx

import Avatar from "../rtc/avatar";
import Description from "../description";
import { ICameraVideoTrack, IMicrophoneAudioTrack } from "agora-rtc-sdk-ng";
import Rtc from "../rtc";
import Header from "../header";
import { rtcManager, IUserTracks, IRtcUser } from "@/manager";
import { useState, useEffect, useRef } from "react";
import CamSection from "../rtc/camSection";
import styles from "./index.module.scss";
import Chat from "../chat";
import AvatarHeyGen from "../rtc/avatarHeyGen";

let hasInit = false;

const PCEntry = () => {
  const [remoteuser, setRemoteUser] = useState<IRtcUser | null>(null);
  const lastChatTimeRef = useRef<number | null>(null); // To track last chat time
  const [videoTrack, setVideoTrack] = useState<ICameraVideoTrack>();

  useEffect(() => {
    if (hasInit) {
      return;
    }

    init();

    return () => {
      if (hasInit) {
        destroy();
      }
    };
  }, []); // Empty dependency array ensures this runs once on mount

  const onLocalTracksChanged = (tracks: IUserTracks) => {
    console.log("[test] onLocalTracksChanged", tracks);
    const { videoTrack } = tracks;
    if (videoTrack) {
      setVideoTrack(videoTrack);
    }
  };

  const onRemoteUserChanged = (user: IRtcUser) => {
    setRemoteUser(user);
  };

  const init = async () => {
    rtcManager.on("remoteUserChanged", onRemoteUserChanged);
    rtcManager.on("localTracksChanged", onLocalTracksChanged);
    hasInit = true;
  };

  const destroy = async () => {
    rtcManager.off("remoteUserChanged", onRemoteUserChanged);
    hasInit = false;
  };

  return (
    <div
      className={styles.entry}
      style={{
        height: '100vh', // Occupy full viewport height
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <Header />
      <div
        className={styles.content}
        style={{
          flex: 1, // Allow content to grow and fill available space
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <Description />
        <div
          className={styles.body}
          style={{
            display: 'flex',
            flex: 1, // Allow body to grow and fill available space
            height: '100%', // Ensure it takes full height
          }}
        >
          {/* Left Column: Chat and Rtc */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              flex: 1, // Occupy available width
            }}
          >
            <Rtc />
            <Chat />
          </div>

          {/* Right Column: Iframe and AvatarHeyGen Side by Side */}
          <div
            style={{
              marginLeft: 'auto',
              flexGrow: 1,
              display: 'flex',
              flexDirection: 'row', // Changed from 'column' to 'row'
              alignItems: 'stretch', // Stretch to fill the container height
              justifyContent: 'space-between', // Space between iframe and AvatarHeyGen
              padding: '16px', // Optional: Add some padding
              gap: '16px', // Optional: Add space between the two elements
              height: '100%', // Ensure the right column occupies full height
              width: '100%', // Ensure it takes full width
            }}
          >
            {/* Container for Iframe */}
            <div
              style={{
                flex: 1, // Occupy equal space
                display: 'flex',
                flexDirection: 'column',
              }}
            >
              <iframe
                src="https://sa-utils.agora.io/svg/fen.html?fen=rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR" // Replace with your desired URL
                title="Chess Board Visualization" // Provide a meaningful title for accessibility
                style={{
                  width: '100%', // Occupy full width of the parent container
                  height: '100%', // Occupy full height of the parent container
                  border: 'none', // Remove default border
                  borderRadius: '8px', // Optional: Rounded corners
                  boxShadow: '0px 4px 12px rgba(0, 0, 0, 0.1)', // Optional: Add subtle shadow
                }}
                allowFullScreen // Optional: Allow fullscreen if needed
              />
            </div>

            {/* Container for CamSection and AvatarHeyGen */}
            <div
              style={{
                flex: 1, // Occupy equal space
                display: 'flex',
                flexDirection: 'column', // Stack vertically
                height: '100%', // Ensure it takes full height
              }}
            >
              {/* Wrapper for CamSection */}
              <div
                style={{
                  flex: 1, // Occupy half of the container
                  display: 'flex',
                  flexDirection: 'column',
                }}
              >
                <CamSection
                  videoTrack={videoTrack}

                />
              </div>

              {/* Wrapper for AvatarHeyGen */}
              <div
                style={{
                  flex: 1, // Occupy half of the container
                  display: 'flex',
                  flexDirection: 'column',
                }}
              >
                <AvatarHeyGen
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PCEntry;
