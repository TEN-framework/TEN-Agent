"use client"

import AuthInitializer from "@/components/authInitializer"
import { isMobile } from "@/common"
import dynamic from 'next/dynamic'

const PCEntry = dynamic(() => import('@/platform/pc/entry'), {
  ssr: false,
})

const MobileEntry = dynamic(() => import('@/platform/mobile/entry'), {
  ssr: false,
})

export default function Home() {

  return (
    <AuthInitializer>
      {isMobile() ? <MobileEntry></MobileEntry> : <PCEntry></PCEntry>}
    </AuthInitializer >
  );
}



