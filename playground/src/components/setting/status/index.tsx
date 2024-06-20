import { useMemo } from "react"
import { useAppSelector } from "@/common"
import styles from "./index.module.scss"

const Status = () => {
  const roomConnected = useAppSelector(state => state.global.roomConnected)
  const agentConnected = useAppSelector(state => state.global.agentConnected)

  const roomConnectedText = useMemo(() => {
    return roomConnected ? "TRUE" : "FALSE"
  }, [roomConnected])

  const agentConnectedText = useMemo(() => {
    return agentConnected ? "TRUE" : "FALSE"
  }, [agentConnected])

  return <div className={styles.status}>
    <div className={styles.title}>STATUS</div>
    <div className={styles.item}>
      <div className={styles.title}>Room connected</div>
      <div className={styles.content}>{roomConnectedText}</div>
    </div>
    <div className={styles.item}>
      <div className={styles.title}>Agent connected</div>
      <div className={styles.content}>{agentConnectedText}</div>
    </div>
  </div>
}


export default Status
