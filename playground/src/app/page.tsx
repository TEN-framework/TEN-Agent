"use client";

import dynamic from "next/dynamic";

import AuthInitializer from "@/components/authInitializer";
import { useAppSelector, EMobileActiveTab, useIsCompactLayout } from "@/common";
import Header from "@/components/Layout/Header";
import Action from "@/components/Layout/Action";
import { cn } from "@/lib/utils";
import Avatar from "@/components/Agent/AvatarTrulience";
import React from "react";
import { IRtcUser } from "@/manager";

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

  const isCompactLayout = useIsCompactLayout();
  const useTrulienceAvatar = Boolean(process.env.NEXT_PUBLIC_trulienceAvatarId)
  const avatarInLargeWindow = process.env.NEXT_PUBLIC_AVATAR_DESKTOP_LARGE_WINDOW?.toLowerCase() === "true";
 const [remoteuser, setRemoteUser] = React.useState<IRtcUser>()
 

 React.useEffect(() => {
  // Only runs on the client
  const { rtcManager } = require("../manager/rtc/rtc"); 
  rtcManager.on("remoteUserChanged", onRemoteUserChanged);

  return () => {
    rtcManager.off("remoteUserChanged", onRemoteUserChanged);
  };
}, []);

  //React.useEffect(() => {
  //  rtcManager.on("remoteUserChanged", onRemoteUserChanged) 
  // }, [])
 
  const onRemoteUserChanged = (user: IRtcUser) => {
    if (useTrulienceAvatar) {
      user.audioTrack?.stop();
    }
    setRemoteUser(user)
  }

  return (
    <AuthInitializer>
      <div className="relative mx-auto flex h-full min-h-screen flex-col md:h-screen">
        <Header className="h-[60px]" />
        <Action className="h-[48px]" />
        <div className="mx-2 mb-2 flex h-full max-h-[calc(100vh-108px-24px)] flex-col md:flex-row md:gap-2">
          <DynamicRTCCard
            className={cn(
              "m-0 w-full rounded-b-lg bg-[#181a1d] md:w-[480px] md:rounded-lg",
              {
                ["hidden md:block"]: mobileActiveTab === EMobileActiveTab.CHAT,
              }
            )}
          />
          {(!useTrulienceAvatar || isCompactLayout || !avatarInLargeWindow) ? (
              <DynamicChatCard
              className={cn(
                "m-0 w-full rounded-b-lg bg-[#181a1d] md:rounded-lg",
                {
                  ["hidden md:block"]: mobileActiveTab === EMobileActiveTab.AGENT,
                }
              )}
            />
          ) : (
          <Avatar audioTrack={remoteuser?.audioTrack} />
          )}
        </div>
      </div>
    </AuthInitializer>
  );
}
