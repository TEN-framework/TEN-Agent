import { useMemo } from "react"
import { useAppSelector } from "@/common"
import { Popover } from 'antd';


import styles from "./index.module.scss"

interface InfoPopoverProps {
  children?: React.ReactNode
}

const InfoPopover = (props: InfoPopoverProps) => {
  const { children } = props
  const options = useAppSelector(state => state.global.options)
  const { channel, userId } = options

  const roomConnected = useAppSelector(state => state.global.roomConnected)
  const agentConnected = useAppSelector(state => state.global.agentConnected)

  const roomConnectedText = useMemo(() => {
    return roomConnected ? "TRUE" : "FALSE"
  }, [roomConnected])

  const agentConnectedText = useMemo(() => {
    return agentConnected ? "TRUE" : "FALSE"
  }, [agentConnected])



  const content = <section className={styles.info}>
    <div className={styles.title}>INFO</div>
    <div className={styles.item}>
      <span className={styles.title}>Room</span>
      <span className={styles.content}>{channel}</span>
    </div>
    <div className={styles.item}>
      <span className={styles.title}>Participant</span>
      <span className={styles.content}>{userId}</span>
    </div>
    <div className={styles.slider}></div>
    <div className={styles.title}>STATUS</div>
    <div className={styles.item}>
      <div className={styles.title}>Room connected</div>
      <div className={styles.content}>{roomConnectedText}</div>
    </div>
    <div className={styles.item}>
      <div className={styles.title}>Agent connected</div>
      <div className={styles.content}>{agentConnectedText}</div>
    </div>
  </section>


  return <Popover content={content} arrow={false}>{children}</Popover>

}

export default InfoPopover
