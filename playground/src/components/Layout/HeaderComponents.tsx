"use client"

import * as React from "react"
import NextLink from "next/link"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { InfoIcon, GitHubIcon, PaletteIcon } from "@/components/Icon"
import {
  useAppSelector,
  useAppDispatch,
  GITHUB_URL,
  COLOR_LIST,
} from "@/common"
import { setThemeColor } from "@/store/reducers/global"
import { cn } from "@/lib/utils"
import { HexColorPicker } from "react-colorful"
import dynamic from "next/dynamic"

import styles from "./Header.module.css"

export function HeaderRoomInfo() {
  const options = useAppSelector((state) => state.global.options)
  const { channel, userId } = options

  const roomConnected = useAppSelector((state) => state.global.roomConnected)
  const agentConnected = useAppSelector((state) => state.global.agentConnected)

  const roomConnectedText = React.useMemo(() => {
    return roomConnected ? "TRUE" : "FALSE"
  }, [roomConnected])

  const agentConnectedText = React.useMemo(() => {
    return agentConnected ? "TRUE" : "FALSE"
  }, [agentConnected])

  return (
    <>
      <TooltipProvider delayDuration={200}>
        <Tooltip>
          <TooltipTrigger className="flex items-center space-x-2 text-lg font-semibold">
            <InfoIcon className="h-4 w-4 md:h-5 md:w-5" />
            <span className="hidden text-sm md:inline-block">
              Channel Name:{" "}
            </span>
            <span className="max-w-24 text-sm md:text-base">
              {channel}
            </span>
          </TooltipTrigger>
          <TooltipContent className="bg-[var(--background-color,#1C1E22)] text-gray-600">
            <table className="border-collapse">
              <tbody>
                <tr>
                  <td className="pr-2 font-bold text-primary">INFO</td>
                  <td></td>
                </tr>
                <tr>
                  <td className="pr-2">Room:</td>
                  <td className="text-[#0888FF]">{channel}</td>
                </tr>
                <tr>
                  <td className="pr-2">Participant:</td>
                  <td className="text-[#0888FF]">{userId}</td>
                </tr>
                <tr>
                  <td colSpan={2}>
                    <hr className="my-2 border-t border-gray-600" />
                  </td>
                </tr>
                <tr>
                  <td className="pr-2 font-bold text-primary" colSpan={2}>
                    STATUS
                  </td>
                </tr>
                <tr>
                  <td className="pr-2">Room connected:</td>
                  <td className="text-[#0888FF]">{roomConnectedText}</td>
                </tr>
                <tr>
                  <td className="pr-2">Agent connected:</td>
                  <td className="text-[#0888FF]">{agentConnectedText}</td>
                </tr>
              </tbody>
            </table>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    </>
  )
}

export function HeaderActions() {
  return (
    <div className="flex space-x-2 md:space-x-4">
      <NextLink href={GITHUB_URL} target="_blank">
        <GitHubIcon className="h-4 w-4 md:h-5 md:w-5" />
        <span className="sr-only">GitHub</span>
      </NextLink>
      <ThemePalettePopover />
      <NetworkIndicator />
    </div>
  )
}

export const ThemePalettePopover = () => {
  const themeColor = useAppSelector((state) => state.global.themeColor)
  const dispatch = useAppDispatch()

  const onMainClickSelect = (index: number) => {
    const target = COLOR_LIST[index]
    if (target.active !== themeColor) {
      dispatch(setThemeColor(target.active))
    }
  }

  const onColorSliderChange = (color: string) => {
    console.log(color)
    dispatch(setThemeColor(color))
  }

  return (
    <>
      <Popover>
        <PopoverTrigger>
          <PaletteIcon className="h-4 w-4 md:h-5 md:w-5" color={themeColor} />
        </PopoverTrigger>
        <PopoverContent className="space-y-2 border-none bg-[var(--background-color,#1C1E22)]">
          <div className="text-sm font-semibold text-[var(--Grey-300,#EAECF0)]">
            STYLE
          </div>
          <div className="mt-4 flex gap-3">
            {COLOR_LIST.map((item, index) => {
              const isSelected = item.active === themeColor
              return (
                <button
                  onClick={() => onMainClickSelect(index)}
                  className={cn(
                    "relative h-7 w-7 rounded-full",
                    {
                      "ring-2 ring-offset-2": isSelected,
                    },
                    "transition-all duration-200 ease-in-out",
                  )}
                  style={{
                    backgroundColor: item.default,
                    ...(isSelected && { ringColor: item.active }),
                  }}
                  key={index}
                >
                  <span
                    className="absolute inset-1 rounded-full"
                    style={{
                      backgroundColor: item.active,
                    }}
                  ></span>
                </button>
              )
            })}
          </div>
          <div className={cn("flex h-6 items-center", styles.colorPicker)}>
            <HexColorPicker color={themeColor} onChange={onColorSliderChange} />
          </div>
        </PopoverContent>
      </Popover>
    </>
  )
}

// export const Network = () => {
//   const [networkQuality, setNetworkQuality] = React.useState<NetworkQuality>()

//   React.useEffect(() => {
//     rtcManager.on("networkQuality", onNetworkQuality)

//     return () => {
//       rtcManager.off("networkQuality", onNetworkQuality)
//     }
//   }, [])

//   const onNetworkQuality = (quality: NetworkQuality) => {
//     setNetworkQuality(quality)
//   }

//   return (
//     <NetworkIconByLevel
//       level={networkQuality?.uplinkNetworkQuality}
//       className="h-5 w-5"
//     />
//   )
// }

const NetworkIndicator = dynamic(
  () => import("@/components/Dynamic/NetworkIndicator"),
  {
    ssr: false,
  },
)
