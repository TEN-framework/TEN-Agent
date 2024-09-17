import Chat from "../chat"
import Description from "../description"
import Rtc from "../rtc"
import Header from "../header"

import styles from "./index.module.scss"

const PCEntry = () => {
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
}


export default PCEntry
