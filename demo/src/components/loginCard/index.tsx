"use client"

import type React from 'react';
import { useRouter } from 'next/navigation'
import { message } from "antd"
import { useState, useEffect } from "react"
import { GITHUB_URL, getRandomUserId, useAppDispatch, getRandomChannel } from "@/common"
import { setAgentSettings, setOptions } from "@/store/reducers/global"
import styles from "./index.module.scss"

import { GithubIcon } from "../icons"
import packageData from "../../../package.json"

const { version } = packageData

const LoginCard = () => {
  const dispatch = useAppDispatch()
  const router = useRouter()
  const [userName, setUserName] = useState("")
  const [isLoadingSuccess, setIsLoadingSuccess] = useState(false);

  const onClickGithub = () => {
    if (typeof window !== "undefined") {
      window.open(GITHUB_URL, "_blank")
    }
  }

  const onUserNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    let value = e.target.value
    value = value.replace(/\s/g, "");
    setUserName(value)
  }

  useEffect(() => {
    const onPageLoad = () => {
      setIsLoadingSuccess(true);
    };

    if (document.readyState === 'complete') {
      onPageLoad();
    } else {
      window.addEventListener('load', onPageLoad, false);
      return () => window.removeEventListener('load', onPageLoad);
    }
  }, []);

  const onClickJoin = () => {
    if (!userName) {
      message.error("please enter a user name")
      return
    }

    if (userName !== "agora.io") {
      message.error("this is a internal environment protected by password, please contact the administrator");
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
      <span
        className={styles.github}
        onClick={onClickGithub}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            onClickGithub();
          }
        }}
        role="button"
        tabIndex={0}
      >
        <GithubIcon />
        <span className={styles.text}>GitHub</span>
      </span>
    </section>
    <section className={styles.content}>
      <div className={styles.title}>
        <span className={styles.title}>TEN Agent</span>
        <span className={styles.text}>The World's First Multimodal AI Agent with the OpenAI Realtime API (Beta)</span>
      </div>
      <div className={styles.section}>
        <input placeholder="User Name" value={userName} onChange={onUserNameChange} />
      </div>
      <div className={styles.section}>
        <div
          className={`${styles.btn} ${!isLoadingSuccess && styles.btnLoadingBg}`}
          onClick={onClickJoin}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              onClickJoin();
            }
          }}
          role="button"
          tabIndex={0}
        >
          <div className={styles.btnText}>
            {isLoadingSuccess ? "Join" : <div><span>Loading</span><span className={styles.dotting} /></div>}
          </div>
        </div>
      </div>
      <div className={styles.version}>Version {version}</div>
    </section >
  </div >
}

export default LoginCard
