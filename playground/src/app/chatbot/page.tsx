"use client";

import dynamic from "next/dynamic";
import AuthInitializer from "@/components/authInitializer";
import { useAppSelector, EMobileActiveTab } from "@/common";
import Header from "@/components/Layout/Header";
import Action from "@/components/Layout/Action";
import { cn } from "@/lib/utils";

const DynamicRTCCard = dynamic(() => import("@/components/Dynamic/RTCCard"), {
  ssr: false,
});
const DynamicChatCard = dynamic(() => import("@/components/Chat/ChatCard"), {
  ssr: false,
});

export default function Chatbot() {
  const mobileActiveTab = useAppSelector(
    (state) => state.global.mobileActiveTab
  );

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
          <DynamicChatCard
            className={cn(
              "m-0 w-full rounded-b-lg bg-[#181a1d] md:rounded-lg",
              {
                ["hidden md:block"]: mobileActiveTab === EMobileActiveTab.AGENT,
              }
            )}
          />
        </div>
      </div>
    </AuthInitializer>
  );
}