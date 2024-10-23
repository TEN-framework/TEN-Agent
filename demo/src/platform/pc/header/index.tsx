"use client"

import { useAppSelector, GITHUB_URL, useSmallScreen } from "@/common"
import Network from "./network"
import InfoPopover from "./infoPopover"
import StylePopover from "./stylePopover"
import { GithubIcon, LogoIcon, InfoIcon, ColorPickerIcon } from "@/components/icons"
import cnLogoSrc from "../../../assets/cnlogo.png"
import Image from 'next/image'
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
      {/* <LogoIcon></LogoIcon> */}
      <Image src={cnLogoSrc} width={52} height={30} alt="logo"></Image>
      {/* <span className={styles.title} >TEN Agent</span> */}
    </span>
    <InfoPopover>
      <span className={styles.content}>
        <InfoIcon></InfoIcon>
        <span className={styles.text}>Channel Name: {channel}</span>
      </span>
    </InfoPopover>
    <div className={styles.links}>
      <span onClick={onClickGithub} className={styles.githubWrapper}>
        <GithubIcon></GithubIcon>
      </span>
      <StylePopover>
        <ColorPickerIcon color={themeColor} ></ColorPickerIcon>
      </StylePopover>
      <Network></Network>
    </div>
  </div>
}


export default Header
