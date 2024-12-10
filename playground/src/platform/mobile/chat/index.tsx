import { useEffect, useContext } from "react"
import ChatItem from "./chatItem"
import { IChatItem } from "@/types"
import {
  useAppDispatch, LANGUAGE_OPTIONS, useAppSelector, isRagGraph,
  apiGetGraphs,
  apiGetNodes,
  apiGetExtensionMetadata,
  apiReloadGraph,
} from "@/common"
import { setExtensionMetadata, setGraphName, setGraphs, setExtensions, setLanguage } from "@/store/reducers/global"
import { Select, } from 'antd';
import { MenuContext } from "../menu/context"
import PdfSelect from "@/components/pdfSelect"
import styles from "./index.module.scss"

const Chat = () => {
  const extensions = useAppSelector(state => state.global.extensions)
  const chatItems = useAppSelector(state => state.global.chatItems)
  const language = useAppSelector(state => state.global.language)
  const agentConnected = useAppSelector(state => state.global.agentConnected)
  const graphName = useAppSelector(state => state.global.graphName)
  const graphs = useAppSelector(state => state.global.graphs)
  const dispatch = useAppDispatch()
  const context = useContext(MenuContext);

  if (!context) {
    throw new Error("MenuContext is not found")
  }

  const { scrollToBottom } = context;


  useEffect(() => {
    apiReloadGraph().then(() => {
      Promise.all([apiGetGraphs(), apiGetExtensionMetadata()]).then((res: any) => {
        let [graphRes, metadataRes] = res
        let graphs = graphRes["data"].map((item: any) => item["name"])

        let metadata = metadataRes["data"]
        let metadataMap: Record<string, any> = {}
        metadata.forEach((item: any) => {
          metadataMap[item["name"]] = item
        })
        dispatch(setGraphs(graphs))
        dispatch(setExtensionMetadata(metadataMap))
      })
    })
  }, [])

  useEffect(() => {
    if (!extensions[graphName]) {
      apiGetNodes(graphName).then((res: any) => {
        let nodes = res["data"]
        let nodesMap: Record<string, any> = {}
        nodes.forEach((item: any) => {
          nodesMap[item["name"]] = item
        })
        dispatch(setExtensions({ graphName, nodesMap }))
      })
    }
  }, [graphName])

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
        disabled={agentConnected} options={graphs.map((item) => { return { label: item, value: item } })}
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
