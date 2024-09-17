import { IconProps } from "../types"
import micMuteSvg from "@/assets/mic_mute.svg"
import micUnMuteSvg from "@/assets/mic_unmute.svg"

interface IMicIconProps extends IconProps {
  active?: boolean
}

export const MicIcon = (props: IMicIconProps) => {
  const { active, color, ...rest } = props

  if (active) {
    return micUnMuteSvg({
      color: color || "#3D53F5",
      ...rest,
    })
  } else {
    return micMuteSvg({
      color: color || "#667085",
      ...rest,
    })
  }
}
