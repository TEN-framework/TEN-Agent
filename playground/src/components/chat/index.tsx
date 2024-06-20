"use client"

import { useEffect, useRef } from "react"
import ChatItem from "./chatItem"
import { TranscriptionIcon } from "@/components/icons"
import { genRandomChatList, useSmallScreen, useAutoScroll, useAppSelector } from "@/common"
import styles from "./index.module.scss"

const MOCK_CHAT_LIST = genRandomChatList(10)

const Chat = () => {
  const chatItems = useAppSelector(state => state.global.chatItems)
  // const chatItems = MOCK_CHAT_LIST
  const chatRef = useRef(null)
  const { isSmallScreen } = useSmallScreen()
  useAutoScroll(chatRef)

  return <section className={styles.chat}>
    <div className={styles.header}>
      <TranscriptionIcon></TranscriptionIcon>
      <span className={styles.text}>Chat</span>
    </div>
    <div className={`${styles.content} ${isSmallScreen ? styles.small : ''}`} ref={chatRef}>
      {chatItems.map((item, index) => {
        return <ChatItem data={item} key={index} ></ChatItem>
      })}
    </div>
  </section >
}


export default Chat
