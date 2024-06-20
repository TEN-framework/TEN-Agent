import { IconProps } from "../types"
import LogoSvg from "@/assets/logo.svg"
import LogoSmallSvg from "@/assets/logo_small.svg"

interface LogoIconProps extends IconProps {
  size?: "small" | "normal"
}

export const LogoIcon = (props: LogoIconProps) => {
  const { size, ...others } = props
  return size == "normal" ? <LogoSvg {...others}></LogoSvg> : <LogoSmallSvg  {...others}></LogoSmallSvg>
}
