import { IChatItem } from "@/types"
import styles from "./index.module.scss"
import { usePrevious } from "@/common"
import { use, useEffect, useMemo, useState } from "react"

interface ChatItemProps {
  data: IChatItem
}


let flag = false

const ChatItem = (props: ChatItemProps) => {
  const { data } = props
  const { text, type } = data


  const abUserName = useMemo(() => {
    return type == "agent" ? "Ag" : "Yo"
  }, [type])

  const coUserName = useMemo(() => {
    return type == "agent" ? "Agent" : "You"
  }, [type])


  return <div className={styles.chatItem}>
    <span className={styles.left}>
      <span className={styles.text}>{abUserName}</span>
    </span>
    <span className={styles.right}>
      <div className={`${styles.userName} ${type == "agent" ? styles.isAgent : ''}`} >{coUserName}</div>
      <div className={`${styles.text} ${type == "agent" ? styles.isAgent : ''}`} >
        {text}
      </div>
    </span>
  </div >
}


export default ChatItem
