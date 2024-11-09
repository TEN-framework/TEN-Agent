import LoginCard from "@/components/Card/Login"
import styles from "./index.module.css"

export default function Login() {
  return (
    <main className={styles.login}>
      <div className={styles.starts} />
      <div className={styles.starts2} />
      <div className={styles.starts3} />
      <LoginCard />
    </main>
  )
}
