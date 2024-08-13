"use client"

import packageData from "../../../package.json"
import { useRouter } from 'next/navigation'
import { message } from "antd"
import { useState } from "react"
import { GithubIcon, LogoIcon } from "../icons"
import { GITHUB_URL, getRandomUserId, useAppDispatch, getRandomChannel } from "@/common"
import { setOptions } from "@/store/reducers/global"
import styles from "./index.module.scss"


const { version } = packageData

const LoginCard = () => {
  const dispatch = useAppDispatch()
  const router = useRouter()
  const [userName, setUserName] = useState("")

  const onClickGithub = () => {
    if (typeof window !== "undefined") {
      window.open(GITHUB_URL, "_blank")
    }
  }

  const onUserNameChange = (e: any) => {
    let value = e.target.value
    value = value.replace(/\s/g, "");
    setUserName(value)
  }



  const onClickJoin = () => {
    if (!userName) {
      message.error("please input user name")
      return
    }
    const userId = getRandomUserId()
    dispatch(setOptions({
      userName,
      channel: getRandomChannel(),
      userId
    }))
    router.push("/home")
  }


  return <div className={styles.card}>
    <section className={styles.top}>
      <span className={styles.github} onClick={onClickGithub}>
        <GithubIcon></GithubIcon>
        <span className={styles.text}>GitHub</span>
      </span>
    </section>
    <section className={styles.content}>
      <div className={styles.title}>
        <LogoIcon transform="scale(1.2 1.2)"></LogoIcon>
        <span className={styles.text}>Agents Playground</span>
      </div>
      <div className={styles.section}>
        <input placeholder="User Name" value={userName} onChange={onUserNameChange} ></input>
      </div>
      <div className={styles.section}>
        <div className={styles.btn} onClick={onClickJoin}>
          <span className={styles.btnText}>Join</span>
        </div>
      </div>
      <div className={styles.version}>Version {version}</div>
    </section >
  </div >


  return
}

export default LoginCard
