import { setAgentConnected } from "@/store/reducers/global"
import { setExtensionMetadata, setGraphName, setGraphs, setLanguage, setExtensions, setOverridenPropertiesByGraph, setOverridenProperties } from "@/store/reducers/global"
import {
  useAppDispatch, useAppSelector, apiPing, genUUID,
  apiStartService, apiStopService,
  isRagGraph,
  apiGetGraphs,
  apiGetNodes,
  useGraphExtensions,
  apiGetExtensionMetadata,
  apiReloadGraph,
} from "@/common"
import { message, Upload } from "antd"
import { useEffect, useState, MouseEventHandler } from "react"
import { LoadingOutlined, UploadOutlined } from "@ant-design/icons"
import styles from "./index.module.scss"
import PdfSelect from "@/components/pdfSelect"
import { SettingOutlined } from "@ant-design/icons"
import { Button, ConfigProvider, Modal, Select, Tabs, TabsProps, theme, } from 'antd';
import EditableTable from "../chat/table"
let intervalId: any

const Description = () => {
  const dispatch = useAppDispatch()
  const agentConnected = useAppSelector(state => state.global.agentConnected)
  const channel = useAppSelector(state => state.global.options.channel)
  const userId = useAppSelector(state => state.global.options.userId)
  const language = useAppSelector(state => state.global.language)
  const voiceType = useAppSelector(state => state.global.voiceType)
  const [loading, setLoading] = useState(false)
  const graphName = useAppSelector(state => state.global.graphName)
  const overridenProperties = useAppSelector(state => state.global.overridenProperties)
  const [modal2Open, setModal2Open] = useState(false)
  const graphExtensions = useGraphExtensions()
  const extensionMetadata = useAppSelector(state => state.global.extensionMetadata)
  const graphs = useAppSelector(state => state.global.graphs)

  useEffect(() => {
    if (channel) {
      checkAgentConnected()
    }
  }, [channel])


  const checkAgentConnected = async () => {
    const res: any = await apiPing(channel)
    if (res?.code == 0) {
      dispatch(setAgentConnected(true))
    }
  }

  const onClickConnect = async () => {
    if (loading) {
      return
    }
    setLoading(true)
    if (agentConnected) {
      await apiStopService(channel)
      dispatch(setAgentConnected(false))
      message.success("Agent disconnected")
      stopPing()
    } else {
      let properties: Record<string, any> = overridenProperties[graphName] || {}
      const res = await apiStartService({
        channel,
        userId,
        graphName,
        language,
        voiceType,
        properties
      })
      const { code, msg } = res || {}
      if (code != 0) {
        if (code == "10001") {
          message.error("The number of users experiencing the program simultaneously has exceeded the limit. Please try again later.")
        } else {
          message.error(`code:${code},msg:${msg}`)
        }
        setLoading(false)
        throw new Error(msg)
      }
      dispatch(setAgentConnected(true))
      message.success("Agent connected")
      startPing()
    }
    setLoading(false)
  }

  const startPing = () => {
    if (intervalId) {
      stopPing()
    }
    intervalId = setInterval(() => {
      apiPing(channel)
    }, 3000)
  }

  const stopPing = () => {
    if (intervalId) {
      clearInterval(intervalId)
      intervalId = null
    }
  }

  const onGraphNameChange = (val: any) => {
    dispatch(setGraphName(val))
  }


  return <div className={styles.description}>
    <span className={styles.title}>Description</span>
    <span className={styles.text}>TEN Agent is a real-time multimodal AI agent that can speak, see, and access a knowledge base.</span>


      <span className={styles.right}>
        <Select className={styles.graphName}
          disabled={agentConnected} options={graphs.map((item) => { return { label: item, value: item } })}
          value={graphName} onChange={onGraphNameChange}></Select>
        <Button icon={<SettingOutlined />} type="primary" onClick={() => { setModal2Open(true) }}></Button>
        {isRagGraph(graphName) ? <PdfSelect></PdfSelect> : null}
      </span>
    
    <span className={`${styles.btnConnect} ${agentConnected ? styles.disconnect : ''}`} onClick={onClickConnect}>
      <span className={`${styles.btnText} ${agentConnected ? styles.disconnect : ''}`}>
        {!agentConnected ? "Connect" : "Disconnect"}
        {loading ? <LoadingOutlined className={styles.loading}></LoadingOutlined> : null}
      </span>
    </span>

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
  </div>





}


export default Description
