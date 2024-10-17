"use client"

import AuthInitializer from "@/components/authInitializer"
import { getBrowserLanguage, isMobile, useAppDispatch } from "@/common"
import dynamic from 'next/dynamic'
import { useEffect, useState } from "react"
import { setLanguage } from "@/store/reducers/global"

const PCEntry = dynamic(() => import('@/platform/pc/entry'), {
  ssr: false,
})

const MobileEntry = dynamic(() => import('@/platform/mobile/entry'), {
  ssr: false,
})

export default function Home() {
  const [mobile, setMobile] = useState<boolean | null>(null);
  const dispatch = useAppDispatch()


  useEffect(() => {
    setMobile(isMobile())
    dispatch(setLanguage(getBrowserLanguage().value))
  })

  return (
    mobile === null ? <></> :
      <AuthInitializer>
        {mobile ? <MobileEntry></MobileEntry> : <PCEntry></PCEntry>}
      </AuthInitializer >
  );
}



