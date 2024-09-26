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
        <Rtc></Rtc>
        <Chat></Chat>
      </div>
    </div>
  </div>
}


export default PCEntry
