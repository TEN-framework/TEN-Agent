import { ReactElement, useEffect, useContext, useState } from "react"
import ChatItem from "./chatItem"
import { IChatItem } from "@/types"
import { useAppDispatch, useAutoScroll, LANGUAGE_OPTIONS, useAppSelector } from "@/common"
import { setLanguage } from "@/store/reducers/global"
import { Select, } from 'antd';
import { MenuContext } from "../menu/context"
import PdfSelect from "@/components/pdfSelect"

import styles from "./index.module.scss"


const Chat = () => {
  const chatItems = useAppSelector(state => state.global.chatItems)
  const language = useAppSelector(state => state.global.language)
  const agentConnected = useAppSelector(state => state.global.agentConnected)
  const dispatch = useAppDispatch()
  // genRandomChatList
  // const [chatItems, setChatItems] = useState<IChatItem[]>([])
  const context = useContext(MenuContext);

  if (!context) {
    throw new Error("MenuContext is not found")
  }

  const { scrollToBottom } = context;


  useEffect(() => {
    scrollToBottom()
  }, [chatItems, scrollToBottom])



  const onLanguageChange = (val: any) => {
    dispatch(setLanguage(val))
  }



  return <section className={styles.chat}>
    <div className={styles.header}>
      <div>
        <Select className={styles.languageSelect}
          options={LANGUAGE_OPTIONS}
          disabled={agentConnected}
          value={language} onChange={onLanguageChange}></Select>
      </div>
      <div style={{
        marginTop: "12px"
      }}>
        <PdfSelect></PdfSelect>
      </div>
    </div>
    <div className={`${styles.content}`} >
      {chatItems.map((item, index) => {
        return <ChatItem data={item} key={index} ></ChatItem>
      })}
    </div>
  </section >
}


export default Chat
