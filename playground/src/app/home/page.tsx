"use client"

import { useMemo, useState, useRef, useEffect } from "react"
import dynamic from "next/dynamic";
import Chat from "@/components/chat"
import Setting from "@/components/setting"
import AuthInitializer from "@/components/authInitializer"
import Menu from "@/components/menu"
const Rtc = dynamic(() => import("@/components/rtc"), {
  ssr: false,
});
const Header = dynamic(() => import("@/components/header"), {
  ssr: false,
});
import { useSmallScreen, useAppSelector } from "@/common"
import styles from "./index.module.scss"

export default function Home() {
  const chatItems = useAppSelector(state => state.global.chatItems)
  const wrapperRef = useRef<HTMLDivElement | null>(null)
  const [activeMenu, setActiveMenu] = useState("Agent")
  const { isSmallScreen } = useSmallScreen()

  useEffect(() => {
    if (!wrapperRef.current) {
      return
    }
    if (!isSmallScreen) {
      return
    }
    wrapperRef.current.scrollTop = wrapperRef.current.scrollHeight
  }, [isSmallScreen, chatItems])

  const onMenuChange = (item: string) => {
    setActiveMenu(item)
  }

  return (
    <AuthInitializer>
      <main className={styles.home} style={{
        minHeight: isSmallScreen ? "auto" : "830px"
      }}>
        <Header></Header>
        {isSmallScreen ?
          <div className={styles.smallScreen}>
            <div className={styles.menuWrapper}>
              <Menu onChange={onMenuChange}></Menu>
            </div>
            <div className={styles.bodyWrapper}>
              <div className={styles.item} style={{
                visibility: activeMenu == "Agent" ? "visible" : "hidden",
                zIndex: activeMenu == "Agent" ? 1 : -1
              }}>
                <Rtc></Rtc>
              </div>
              <div className={styles.item}
                ref={wrapperRef}
                style={{
                  visibility: activeMenu == "Chat" ? "visible" : "hidden",
                  zIndex: activeMenu == "Chat" ? 1 : -1
                }}>
                <Chat></Chat>
              </div>
              <div className={styles.item} style={{
                visibility: activeMenu == "Settings" ? "visible" : "hidden",
                zIndex: activeMenu == "Settings" ? 1 : -1
              }}>
                <Setting></Setting>
              </div>
            </div>
          </div>
          :
          <div className={styles.content} suppressHydrationWarning={true}>
            <Rtc></Rtc>
            <Chat></Chat>
            <Setting></Setting>
          </div>
        }
      </main>
    </AuthInitializer >

  );
}



