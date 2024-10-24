"use client"

import AuthInitializer from "@/components/authInitializer"
import {
  getBrowserLanguage,
  isMobile,
  useAppDispatch,
  useAppSelector,
  EMobileActiveTab,
} from "@/common"
import dynamic from "next/dynamic"
import { useEffect, useState } from "react"
import { setLanguage } from "@/store/reducers/global"

import Header from "@/components/Layout/Header"
import Action from "@/components/Layout/Action"
// import RTCCard from "@/components/Dynamic/RTCCard"
import ChatCard from "@/components/Chat/ChatCard"
import { cn } from "@/lib/utils"

// const PCEntry = dynamic(() => import("@/platform/pc/entry"), {
//   ssr: false,
// })

// const MobileEntry = dynamic(() => import("@/platform/mobile/entry"), {
//   ssr: false,
// })
const DynamicRTCCard = dynamic(() => import("@/components/Dynamic/RTCCard"), {
  ssr: false,
})

export default function Home() {
  const [mobile, setMobile] = useState<boolean | null>(null)
  const dispatch = useAppDispatch()
  const mobileActiveTab = useAppSelector(
    (state) => state.global.mobileActiveTab,
  )

  //   useEffect(() => {
  //     setMobile(isMobile())
  //     dispatch(setLanguage(getBrowserLanguage().value))
  //   })

  //   return mobile === null ? (
  //     <></>
  //   ) : (
  //     <AuthInitializer>
  //       {mobile ? <MobileEntry></MobileEntry> : <PCEntry></PCEntry>}
  //     </AuthInitializer>
  //   )

  return (
    <>
      <div className="mx-auto flex h-full min-h-screen flex-col md:h-screen">
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
      </div>
    </>
  )
}
