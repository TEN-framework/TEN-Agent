import { IconProps } from "../types"
import LogoSvg from "@/assets/logo.svg"
import SmallLogoSvg from "@/assets/logo_small.svg"

export const LogoIcon = (props: IconProps) => {
  const { size = "default" } = props
  return size == "small" ? <SmallLogoSvg {...props}></SmallLogoSvg> : <LogoSvg {...props}></LogoSvg>
}
