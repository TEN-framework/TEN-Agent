"use client"

import { ReactElement, useEffect, useRef, useState } from "react"
import ChatItem from "./chatItem"
import {
  genRandomChatList, useAppDispatch, useAutoScroll,
  LANGUAGE_OPTIONS, useAppSelector,
  GRAPH_OPTIONS,
  isRagGraph,
} from "@/common"
import { setGraphName, setLanguage } from "@/store/reducers/global"
import { Select, } from 'antd';
import PdfSelect from "@/components/pdfSelect"

import styles from "./index.module.scss"




const Chat = () => {
  const dispatch = useAppDispatch()
  const chatItems = useAppSelector(state => state.global.chatItems)
  const language = useAppSelector(state => state.global.language)
  const graphName = useAppSelector(state => state.global.graphName)
  const agentConnected = useAppSelector(state => state.global.agentConnected)

  // const chatItems = genRandomChatList(10)
  const chatRef = useRef(null)


  useAutoScroll(chatRef)


  const onLanguageChange = (val: any) => {
    dispatch(setLanguage(val))
  }

  const onGraphNameChange = (val: any) => {
    dispatch(setGraphName(val))
  }


  return <section className={styles.chat}>
    <div className={styles.header}>
      <span className={styles.left}>
      </span>
      <span className={styles.right}>
        <Select className={styles.graphName}
          disabled={agentConnected} options={GRAPH_OPTIONS}
          value={graphName} onChange={onGraphNameChange}></Select>
        <Select className={styles.languageSelect}
          disabled={agentConnected} options={LANGUAGE_OPTIONS}
          value={language} onChange={onLanguageChange}></Select>
        {isRagGraph(graphName) ? <PdfSelect></PdfSelect> : null}
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
