// https://doc.shengwang.cn/api-ref/rtc/javascript/interfaces/networkquality

import averageSvg from "@/assets/network/average.svg"
import goodSvg from "@/assets/network/good.svg"
import poorSvg from "@/assets/network/poor.svg"
import disconnectedSvg from "@/assets/network/disconnected.svg"
import excellentSvg from "@/assets/network/excellent.svg"

import { IconProps } from "../types"

interface INetworkIconProps extends IconProps {
  level?: number
}

export const NetworkIcon = (props: INetworkIconProps) => {
  const { level, ...rest } = props
  switch (level) {
    case 0:
      return disconnectedSvg(rest)
    case 1:
      return excellentSvg(rest)
    case 2:
      return goodSvg(rest)
    case 3:
      return averageSvg(rest)
    case 4:
      return averageSvg(rest)
    case 5:
      return poorSvg(rest)
    case 6:
      return disconnectedSvg(rest)
    default:
      return disconnectedSvg(rest)
  }
}
