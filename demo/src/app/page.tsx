import LoginCard from "@/components/loginCard"
import styles from "./index.module.scss"

export default function Login() {

  return (
    <main className={styles.login}>
      <div className={styles.starts} />
      <div className={styles.starts2} />
      <div className={styles.starts3} />
      <LoginCard />
    </main>
  );
}
