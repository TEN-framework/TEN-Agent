"use client"

import * as React from "react"

import { LoadingButton } from "@/components/Button/LoadingButton"
import { setAgentConnected, setMobileActiveTab } from "@/store/reducers/global"
import {
  useAppDispatch,
  useAppSelector,
  apiPing,
  apiStartService,
  apiStopService,
  MOBILE_ACTIVE_TAB_MAP,
  EMobileActiveTab,
} from "@/common"
import { toast } from "sonner"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { cn } from "@/lib/utils"

let intervalId: NodeJS.Timeout | null = null

export default function Action(props: { className?: string }) {
  const { className } = props
  const dispatch = useAppDispatch()
  const agentConnected = useAppSelector((state) => state.global.agentConnected)
  const channel = useAppSelector((state) => state.global.options.channel)
  const userId = useAppSelector((state) => state.global.options.userId)
  const language = useAppSelector((state) => state.global.language)
  const voiceType = useAppSelector((state) => state.global.voiceType)
  const graphName = useAppSelector((state) => state.global.graphName)
  const agentSettings = useAppSelector((state) => state.global.agentSettings)
  const mobileActiveTab = useAppSelector(
    (state) => state.global.mobileActiveTab,
  )
  const [loading, setLoading] = React.useState(false)

  React.useEffect(() => {
    if (channel) {
      checkAgentConnected()
    }
  }, [channel])

  const checkAgentConnected = async () => {
    const res: any = await apiPing(channel)
    if (res?.code == 0) {
      dispatch(setAgentConnected(true))
    }
  }

  const onClickConnect = async () => {
    if (loading) {
      return
    }
    setLoading(true)
    if (agentConnected) {
      await apiStopService(channel)
      dispatch(setAgentConnected(false))
      toast.success("Agent disconnected")
      stopPing()
    } else {
      const res = await apiStartService({
        channel,
        userId,
        graphName,
        language,
        voiceType,
        greeting: agentSettings.greeting,
        prompt: agentSettings.prompt,
      })
      const { code, msg } = res || {}
      if (code != 0) {
        if (code == "10001") {
          toast.error(
            "The number of users experiencing the program simultaneously has exceeded the limit. Please try again later.",
          )
        } else {
          toast.error(`code:${code},msg:${msg}`)
        }
        setLoading(false)
        throw new Error(msg)
      }
      dispatch(setAgentConnected(true))
      toast.success("Agent connected")
      startPing()
    }
    setLoading(false)
  }

  const startPing = () => {
    if (intervalId) {
      stopPing()
    }
    intervalId = setInterval(() => {
      apiPing(channel)
    }, 3000)
  }

  const stopPing = () => {
    if (intervalId) {
      clearInterval(intervalId)
      intervalId = null
    }
  }

  return (
    <>
      {/* Action Bar */}
      <div
        className={cn(
          "mx-2 mt-2 flex items-center justify-between rounded-t-lg bg-secondary p-2 md:m-2 md:rounded-lg",
          className,
        )}
      >
        {/* -- Description Part */}
        <div className="hidden md:block">
          <span className="text-sm font-bold">Description</span>
          <span className="ml-2 text-xs text-muted-foreground">
            The World's First Multimodal AI Agent with the OpenAI Realtime API
            (Beta)
          </span>
        </div>

        <Tabs defaultValue={mobileActiveTab} className="w-[400px] md:hidden">
          <TabsList>
            {Object.values(EMobileActiveTab).map((tab) => (
              <TabsTrigger key={tab} value={tab} className="w-24 text-sm">
                {MOBILE_ACTIVE_TAB_MAP[tab]}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>

        {/* -- Action Button */}
        <LoadingButton
          variant={!agentConnected ? "default" : "destructive"}
          size="sm"
          className="ml-auto w-fit min-w-24"
          loading={loading}
          svgProps={{ className: "h-4 w-4 text-muted-foreground" }}
        >
          {loading ? "Connecting" : !agentConnected ? "Connect" : "Disconnect"}
        </LoadingButton>
      </div>
    </>
  )
}
