"use client"

import { ReactElement, useEffect, useRef, useState } from "react"
import ChatItem from "./chatItem"
import {
  genRandomChatList, useAppDispatch, useAutoScroll,
  LANGUAGE_OPTIONS, useAppSelector,
  GRAPH_OPTIONS,
  isRagGraph,
  apiGetGraphs,
  apiGetNodes,
  useGraphExtensions,
  apiGetExtensionMetadata,
  apiReloadGraph,
} from "@/common"
import { setExtensionMetadata, setGraphName, setGraphs, setLanguage, setExtensions, setOverridenPropertiesByGraph, setOverridenProperties } from "@/store/reducers/global"
import { Button, Modal, Select, Tabs, TabsProps, } from 'antd';
import PdfSelect from "@/components/pdfSelect"

import styles from "./index.module.scss"
import { SettingOutlined } from "@ant-design/icons"
import EditableTable from "./table"


const Chat = () => {
  const dispatch = useAppDispatch()
  const graphs = useAppSelector(state => state.global.graphs)
  const extensions = useAppSelector(state => state.global.extensions)
  const graphName = useAppSelector(state => state.global.graphName)
  const chatItems = useAppSelector(state => state.global.chatItems)
  const agentConnected = useAppSelector(state => state.global.agentConnected)
  const [modal2Open, setModal2Open] = useState(false)
  const graphExtensions = useGraphExtensions()
  const extensionMetadata = useAppSelector(state => state.global.extensionMetadata)
  const overridenProperties = useAppSelector(state => state.global.overridenProperties)


  // const chatItems = genRandomChatList(10)
  const chatRef = useRef(null)

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

  useAutoScroll(chatRef)

  const onGraphNameChange = (val: any) => {
    dispatch(setGraphName(val))
  }

  return <section className={styles.chat}>
    <div className={styles.header}>
      <span className={styles.left}>
      </span>
      <span className={styles.right}>
        <Select className={styles.graphName}
          disabled={agentConnected} options={graphs.map((item) => { return { label: item, value: item } })}
          value={graphName} onChange={onGraphNameChange}></Select>
        <Button icon={<SettingOutlined />} type="primary" onClick={() => { setModal2Open(true) }}></Button>
        {isRagGraph(graphName) ? <PdfSelect></PdfSelect> : null}
      </span>
    </div>
    <div className={`${styles.content}`} ref={chatRef}>
      {chatItems.map((item, index) => {
        return <ChatItem data={item} key={index} ></ChatItem>
      })}
    </div>
    <Modal
      title="Properties Override"
      centered
      open={modal2Open}
      onCancel={() => setModal2Open(false)}
      footer={
        <>
          <Button type="default" onClick={() => { dispatch(setOverridenProperties({})) }}>
            Clear Settings
          </Button>
          <Button type="primary" onClick={() => setModal2Open(false)}>
            Close
          </Button>
        </>
      }
    >
      <p>You can adjust extension properties here, the values will be overridden when the agent starts using "Connect." Note that this won't modify the property.json file.</p>
      <Tabs defaultActiveKey="1" items={Object.keys(graphExtensions).map((key) => {
        let node = graphExtensions[key]
        let addon = node["addon"]
        let metadata = extensionMetadata[addon]
        return {
          key: node["name"], label: node["name"], children: <EditableTable
            key={`${graphName}-${node["name"]}`}
            initialData={node["property"] || {}}
            metadata={metadata ? metadata.api.property : {}}
            onUpdate={(data) => {
              // clone the overridenProperties
              let nodesMap = JSON.parse(JSON.stringify(overridenProperties[graphName] || {}))
              nodesMap[key] = data
              dispatch(setOverridenPropertiesByGraph({ graphName, nodesMap }))
            }}
          ></EditableTable>
        }
      })} />
    </Modal>
  </section >
}


export default Chat
