"use client"

import { version } from "../../../package.json"
import { useRouter } from 'next/navigation'
import { message } from "antd"
import { ChangeEvent, InputHTMLAttributes, useState } from "react"
import { GithubIcon } from "../icons"
import Logo from "@/components/logo"
import { GITHUB_URL, getRandomUserId, useAppDispatch, getRandomChannel } from "@/common"
import { setOptions } from "@/store/reducers/global"
import styles from "./index.module.scss"

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
        <Logo width={64} height={64}></Logo>
        <span className={styles.text}>ASTRA.ai Agents Playground</span>
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
}

export default LoginCard
