"use client"

import AuthInitializer from "@/components/authInitializer"
import { getBrowserLanguage, isMobile, useAppDispatch } from "@/common"
import dynamic from "next/dynamic"
import { useEffect, useState } from "react"
import { setLanguage } from "@/store/reducers/global"

import Header from "@/components/Layout/Header"
import Action from "@/components/Layout/Action"
// import RTCCard from "@/components/Dynamic/RTCCard"
import ChatCard from "@/components/Chat/ChatCard"

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
      <div className="mx-auto flex h-screen flex-col">
        <Header />
        <Action className="" />
        <div className="mx-2 mb-2 flex h-full flex-col md:flex-row md:gap-2">
          <DynamicRTCCard className="m-0 w-full rounded-b-lg bg-secondary p-4 md:w-[480px] md:rounded-lg" />
          <ChatCard className="m-0 w-full rounded-b-lg bg-secondary p-4 md:rounded-lg" />
        </div>
      </div>
    </>
  )
}
