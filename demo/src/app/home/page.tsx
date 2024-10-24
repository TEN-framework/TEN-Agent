"use client"

import { useAppSelector, EMobileActiveTab } from "@/common"
import dynamic from "next/dynamic"

import Header from "@/components/Layout/Header"
import Action from "@/components/Layout/Action"
// import RTCCard from "@/components/Dynamic/RTCCard"
import ChatCard from "@/components/Chat/ChatCard"
import { cn } from "@/lib/utils"
import FormModal from "@/components/settings"

const DynamicRTCCard = dynamic(() => import("@/components/Dynamic/RTCCard"), {
  ssr: false,
})

export default function Home() {
  const mobileActiveTab = useAppSelector(
    (state) => state.global.mobileActiveTab,
  )

  return (
    <>
      <div className="relative mx-auto flex h-full min-h-screen flex-col md:h-screen">
        <Header className="h-[60px]" />
        <Action className="h-[48px]" />
        <div className="mx-2 mb-2 flex h-full max-h-[calc(100vh-108px-24px)] flex-col md:flex-row md:gap-2">
          <DynamicRTCCard
            className={cn(
              "m-0 w-full rounded-b-lg bg-[#181a1d] md:w-[480px] md:rounded-lg",
              {
                ["hidden md:block"]: mobileActiveTab === EMobileActiveTab.CHAT,
              },
            )}
          />
          <ChatCard
            className={cn(
              "m-0 w-full rounded-b-lg bg-[#181a1d] md:rounded-lg",
              {
                ["hidden md:block"]: mobileActiveTab === EMobileActiveTab.AGENT,
              },
            )}
          />
        </div>
        <FormModal />
      </div>
    </>
  )
}
