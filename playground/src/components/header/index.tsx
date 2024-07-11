"use client"

import { useAppSelector, GITHUB_URL, useSmallScreen } from "@/common"
import Network from "./network"
import { GithubIcon, LogoIcon } from "@/components/icons"

import styles from "./index.module.scss"
import { useMemo } from "react"

const Header = () => {
  const options = useAppSelector(state => state.global.options)
  const { channel } = options
  const { isSmallScreen } = useSmallScreen()

  const channelNameText = useMemo(() => {
    return !isSmallScreen ? `Channel Name：${channel}` : channel
  }, [isSmallScreen, channel])

  const onClickGithub = () => {
    if (typeof window !== "undefined") {
      window.open(GITHUB_URL, "_blank")
    }
  }

  return <div className={styles.header}>
    <span className={styles.logoWrapper}>
      <LogoIcon ></LogoIcon>
    </span>
    <span className={styles.content}>{channelNameText}</span>
    <span onClick={onClickGithub} className={styles.githubWrapper}>
      <GithubIcon ></GithubIcon>
    </span>
    <Network></Network>
  </div>
}


export default Header
