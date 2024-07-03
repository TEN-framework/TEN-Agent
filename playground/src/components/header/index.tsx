"use client"

import { useAppSelector, GITHUB_URL,useSmallScreen} from "@/common"
import Logo from "@/components/logo"
import Network from "./network"
import { GithubIcon } from "@/components/icons"

import styles from "./index.module.scss"
import { useMemo } from "react"

const Header = () => {
  const options = useAppSelector(state => state.global.options)
  const { channel } = options
  const {isSmallScreen} = useSmallScreen()

  const channelNameText = useMemo(()=>{
    return !isSmallScreen ? `Channel Name：${channel}` : channel
  },[isSmallScreen,channel])

  const onClickGithub = () => {
    if (typeof window !== "undefined") {
      window.open(GITHUB_URL, "_blank")
    }
  }

  return <div className={styles.header}>
    <span className={styles.logoWrapper}>
      <Logo width={24} height={24}></Logo>
      <span className={styles.text}>ASTRA</span>
    </span>
    <span className={styles.content}>{channelNameText}</span>
    <span onClick={onClickGithub} className={styles.githubWrapper}>
      <GithubIcon ></GithubIcon>
    </span>
    <Network></Network>
  </div>
}


export default Header
