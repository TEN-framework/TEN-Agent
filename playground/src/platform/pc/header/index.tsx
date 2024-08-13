"use client"

import { useAppSelector, GITHUB_URL, useSmallScreen } from "@/common"
import Network from "./network"
import InfoPopover from "./infoPopover"
import StylePopover from "./stylePopover"
import { GithubIcon, LogoIcon, InfoIcon, ColorPickerIcon } from "@/components/icons"

import styles from "./index.module.scss"

const Header = () => {
  const themeColor = useAppSelector(state => state.global.themeColor)
  const options = useAppSelector(state => state.global.options)
  const { channel } = options


  const onClickGithub = () => {
    if (typeof window !== "undefined") {
      window.open(GITHUB_URL, "_blank")
    }
  }



  return <div className={styles.header}>
    <span className={styles.logoWrapper}>
      <LogoIcon></LogoIcon>
    </span>
    <InfoPopover>
      <span className={styles.content}>
        <InfoIcon></InfoIcon>
        <span className={styles.text}>Channel Name: {channel}</span>
      </span>
    </InfoPopover>
    <span onClick={onClickGithub} className={styles.githubWrapper}>
      <GithubIcon></GithubIcon>
    </span>
    <StylePopover>
      <ColorPickerIcon color={themeColor} ></ColorPickerIcon>
    </StylePopover>
    <Network style={{ marginLeft: 12 }}></Network>
  </div>
}


export default Header
