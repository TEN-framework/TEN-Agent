"use client"

import AuthInitializer from "@/components/authInitializer"
import { isMobile } from "@/common"
import dynamic from 'next/dynamic'
import { useEffect, useState } from "react"

const PCEntry = dynamic(() => import('@/platform/pc/entry'), {
  ssr: false,
})

const MobileEntry = dynamic(() => import('@/platform/mobile/entry'), {
  ssr: false,
})

export default function Home() {
  const [mobile, setMobile] = useState<boolean | null>(null);

  useEffect(() => {
    setMobile(isMobile())
  })

  return (
    mobile === null ? <></> :
    <AuthInitializer>
      {mobile ? <MobileEntry></MobileEntry> : <PCEntry></PCEntry>}
    </AuthInitializer >
  );
}



