import { useAppSelector } from "@/common"

import styles from "./index.module.scss"

const Info = () => {
  const options = useAppSelector(state => state.global.options)
  const { channel, userId } = options

  return <section className={styles.info}>
    <div className={styles.title}>INFO</div>
    <div className={styles.item}>
      <span className={styles.title}>Room</span>
      <span className={styles.content}>{channel}</span>
    </div>
    <div className={styles.item}>
      <span className={styles.title}>Participant</span>
      <span className={styles.content}>{userId}</span>
    </div>
  </section>
}

export default Info
