"use client"

import { ReactElement, useEffect, useRef, useState } from "react"
import ChatItem from "./chatItem"
import {
  genRandomChatList, useAppDispatch, useAutoScroll,
  LANGUAGE_OPTIONS, useAppSelector,
} from "@/common"
import { setLanguage } from "@/store/reducers/global"
import { Select, } from 'antd';
import PdfSelect from "@/components/pdfSelect"

import styles from "./index.module.scss"




const Chat = () => {
  const dispatch = useAppDispatch()
  const chatItems = useAppSelector(state => state.global.chatItems)
  const language = useAppSelector(state => state.global.language)
  const agentConnected = useAppSelector(state => state.global.agentConnected)

  // const chatItems = genRandomChatList(10)
  const chatRef = useRef(null)


  useAutoScroll(chatRef)


  const onLanguageChange = (val: any) => {
    dispatch(setLanguage(val))
  }




  return <section className={styles.chat}>
    <div className={styles.header}>
      <span className={styles.left}>
        <span className={styles.text}>Chat</span>
        <Select className={styles.languageSelect}
          disabled={agentConnected} options={LANGUAGE_OPTIONS}
          value={language} onChange={onLanguageChange}></Select>
      </span>
      <span className={styles.right}>
        <PdfSelect></PdfSelect>
      </span>
    </div>
    <div className={`${styles.content}`} ref={chatRef}>
      {chatItems.map((item, index) => {
        return <ChatItem data={item} key={index} ></ChatItem>
      })}
    </div>
  </section >
}


export default Chat
