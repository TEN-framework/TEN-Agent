import { ReactElement, useEffect, useContext, useState } from "react"
import ChatItem from "./chatItem"
import { IChatItem } from "@/types"
import { useAppDispatch, useAutoScroll, LANGUAGE_OPTIONS, useAppSelector, GRAPH_OPTIONS, isRagGraph } from "@/common"
import { setGraphName, setLanguage } from "@/store/reducers/global"
import { Select, } from 'antd';
import { MenuContext } from "../menu/context"
import PdfSelect from "@/components/pdfSelect"

import styles from "./index.module.scss"


const Chat = () => {
  const chatItems = useAppSelector(state => state.global.chatItems)
  const language = useAppSelector(state => state.global.language)
  const agentConnected = useAppSelector(state => state.global.agentConnected)
  const graphName = useAppSelector(state => state.global.graphName)
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

  const onGraphNameChange = (val: any) => {
    dispatch(setGraphName(val))
  }


  return <section className={styles.chat}>
    <div className={styles.header}>
      <Select className={styles.graphName}
        disabled={agentConnected} options={GRAPH_OPTIONS}
        value={graphName} onChange={onGraphNameChange}></Select>
      <Select className={styles.languageSelect}
        options={LANGUAGE_OPTIONS}
        disabled={agentConnected}
        value={language} onChange={onLanguageChange}></Select>
      {isRagGraph(graphName) ? <PdfSelect></PdfSelect> : null}
    </div>
    <div className={`${styles.content}`} >
      {chatItems.map((item, index) => {
        return <ChatItem data={item} key={index} ></ChatItem>
      })}
    </div>
  </section >
}


export default Chat
