import { IChatItem } from "@/types"
import styles from "./index.module.scss"
import { usePrevious } from "@/common"
import { use, useEffect, useMemo, useState } from "react"

interface ChatItemProps {
  data: IChatItem
}


const AgentChatItem = (props: ChatItemProps) => {
  const { data } = props
  const { text } = data

  return <div className={`${styles.agentChatItem} ${styles.chatItem}`}>
    <span className={styles.left}>
      <span className={styles.userName}>Ag</span>
    </span>
    <span className={styles.right}>
      <div className={`${styles.userName} ${styles.agent}`}>Agent</div>
      <div className={`${styles.text} ${styles.agent}`}>
        {text}
      </div>
    </span>
  </div >
}

const UserChatItem = (props: ChatItemProps) => {
  const { data } = props
  const { text } = data

  return <div className={`${styles.userChatItem} ${styles.chatItem} `}>
    <div className={styles.userName}>You</div>
    <div className={styles.text}>{text}</div>
  </div>
}


const ChatItem = (props: ChatItemProps) => {
  const { data } = props


  return (
    data.type === "agent" ? <AgentChatItem {...props} /> : <UserChatItem {...props} />
  );


}


export default ChatItem
