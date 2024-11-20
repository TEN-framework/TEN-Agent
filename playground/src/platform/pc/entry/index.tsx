
import Avatar from "../rtc/avatar"
import Description from "../description"
import Rtc from "../rtc"
import Header from "../header"
import { rtcManager, IRtcUser } from "@/manager"
import { useState, useEffect } from "react"
import styles from "./index.module.scss"
import Chat from "../chat"

let hasInit = false

const PCEntry = () => {


  const [remoteuser, setRemoteUser] = useState<IRtcUser>()

  useEffect(() => {
    if (hasInit) {
      return
    }

    init()

    return () => {
      if (hasInit) {
        destory()
      }
    }
  })

  const onRemoteUserChanged = (user: IRtcUser) => {
    setRemoteUser(user)
  }

  const init = async () => {
    rtcManager.on("remoteUserChanged", onRemoteUserChanged)
    hasInit = true
  }

  const destory = async () => {
    rtcManager.off("remoteUserChanged", onRemoteUserChanged);
    hasInit = false
  }


  return <div className={styles.entry}>
    <Header />
    <div className={styles.content}>
      <Description />
      <div className={styles.body} style={{ display: 'flex', height: '100%' }}>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <Chat />
          <Rtc />
        </div>
        <div style={{ marginLeft: 'auto', flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
          <Avatar audioTrack={remoteuser?.audioTrack} />
        </div>
      </div>
    </div>
  </div>
}


export default PCEntry
/*
  return <div className={styles.entry}>
    <Header></Header>
    <div className={styles.content}>
      <Description></Description>
      <div className={styles.body}>
        <div className={styles.rtc}>
          <Rtc></Rtc>
        </div>
        <div className={styles.chat}>
          <Chat></Chat>
        </div>
      </div>
    </div>
  </div>
  */