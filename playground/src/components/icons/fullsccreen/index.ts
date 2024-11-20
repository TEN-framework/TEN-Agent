import { IconProps } from "../types"
import fullscreenSvg from "@/assets/fullscreen.svg"
import fullscreenExitSvg from "@/assets/fullscreen-exit.svg"

interface IFullScreenIconProps extends IconProps {
  active?: boolean
}

export const FullScreenIcon = (props: IFullScreenIconProps) => {
  const { active, color, ...rest } = props

  if (active) {
    return fullscreenExitSvg({
      color: color || "#FFFFFF",
      ...rest,
    })
  } else {
    return fullscreenSvg({
      color: color || "#FFFFFF",
      ...rest,
    })
  }
}