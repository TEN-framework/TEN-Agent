"use client";

import dynamic from "next/dynamic";

import AuthInitializer from "@/components/authInitializer";
import { useAppSelector, EMobileActiveTab, useIsCompactLayout } from "@/common";
import Header from "@/components/Layout/Header";
import Action from "@/components/Layout/Action";
import { cn } from "@/lib/utils";
import Avatar from "@/components/Agent/AvatarTrulience";
import React from "react";
import { IRtcUser, IUserTracks } from "@/manager";
import { IAgoraRTCRemoteUser, IMicrophoneAudioTrack } from "agora-rtc-sdk-ng";

const DynamicRTCCard = dynamic(() => import("@/components/Dynamic/RTCCard"), {
  ssr: false,
});
const DynamicChatCard = dynamic(() => import("@/components/Chat/ChatCard"), {
  ssr: false,
});

export default function Home() {
  const mobileActiveTab = useAppSelector(
    (state) => state.global.mobileActiveTab
  );
  const trulienceSettings = useAppSelector((state) => state.global.trulienceSettings);

  const isCompactLayout = useIsCompactLayout();
  const useTrulienceAvatar = trulienceSettings.enabled;
  const avatarInLargeWindow = trulienceSettings.avatarDesktopLargeWindow;
  const [remoteuser, setRemoteUser] = React.useState<IAgoraRTCRemoteUser>()

  React.useEffect(() => {
    const { rtcManager } = require("../manager/rtc/rtc");
    rtcManager.on("remoteUserChanged", onRemoteUserChanged);
    return () => {
      rtcManager.off("remoteUserChanged", onRemoteUserChanged);
    };
  }, []);

  const onRemoteUserChanged = (user: IAgoraRTCRemoteUser) => {
    if (useTrulienceAvatar) {
      user.audioTrack?.stop();
    }
    if (user.audioTrack) {
      setRemoteUser(user)
    }
  }

  return (
    <AuthInitializer>
      <div className="relative mx-auto flex flex-1 min-h-screen flex-col md:h-screen">
        <Header className="h-[60px]" />
        <Action />
        <div className={cn(
          "mx-2 mb-2 flex h-full max-h-[calc(100vh-108px-24px)] flex-col md:flex-row md:gap-2 flex-1",
          {
            ["flex-col-reverse"]: avatarInLargeWindow && isCompactLayout
          }
        )}>
          <DynamicRTCCard
            className={cn(
              "m-0 w-full rounded-b-lg bg-[#181a1d] md:w-[480px] md:rounded-lg flex-1 flex",
              {
                ["hidden md:flex"]: mobileActiveTab === EMobileActiveTab.CHAT,
              }
            )}
          />

          {(!useTrulienceAvatar || isCompactLayout || !avatarInLargeWindow) && (
            <DynamicChatCard
              className={cn(
                "m-0 w-full rounded-b-lg bg-[#181a1d] md:rounded-lg flex-auto",
                {
                  ["hidden md:flex"]: mobileActiveTab === EMobileActiveTab.AGENT,
                }
              )}
            />
          )}

          {(useTrulienceAvatar && avatarInLargeWindow) && (
            <div className={cn(
              "w-full",
              {
                ["h-60 flex-auto p-1 bg-[#181a1d]"]: isCompactLayout,
                ["hidden md:block"]: mobileActiveTab === EMobileActiveTab.CHAT,
              }
            )}>
              <Avatar audioTrack={remoteuser?.audioTrack} />
            </div>
          )}

        </div>
      </div>
    </AuthInitializer>
  );
}
