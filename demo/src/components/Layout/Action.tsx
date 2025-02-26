"use client"

import * as React from "react"

import { LoadingButton } from "@/components/Button/LoadingButton"
import {
  setAgentConnected,
  setMobileActiveTab,
  setGlobalSettingsDialog,
} from "@/store/reducers/global"
import {
  useAppDispatch,
  useAppSelector,
  apiPing,
  apiStartService,
  apiStopService,
  MOBILE_ACTIVE_TAB_MAP,
  EMobileActiveTab,
  type StartRequestConfig,
} from "@/common"
import { toast } from "sonner"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { cn } from "@/lib/utils"
import SettingsDialog, {
  isCozeGraph,
  cozeSettingsFormSchema,
  isDifyGraph,
  difySettingsFormSchema,
} from "@/components/Dialog/Settings"

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
  const cozeSettings = useAppSelector((state) => state.global.cozeSettings)
  const difySettings = useAppSelector((state) => state.global.difySettings)
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
    try {
      if (agentConnected) {
        // handle disconnect
        await apiStopService(channel)
        dispatch(setAgentConnected(false))
        toast.success("Agent disconnected")
        stopPing()
      } else {
        // handle connect
        // prepare start service payload
        const startServicePayload: StartRequestConfig = {
          channel,
          userId,
          graphName,
          language,
          voiceType,
          greeting: agentSettings.greeting,
          prompt: agentSettings.prompt,
        }
        // check graph ---
        if (isCozeGraph(graphName)) {
          // check coze settings
          const cozeSettingsResult =
            cozeSettingsFormSchema.safeParse(cozeSettings)
          if (!cozeSettingsResult.success) {
            dispatch(
              setGlobalSettingsDialog({
                open: true,
                tab: "coze",
              }),
            )
            throw new Error(
              "Invalid Coze settings. Please check your settings.",
            )
          }
          startServicePayload.coze_token = cozeSettingsResult.data.token
          startServicePayload.coze_bot_id = cozeSettingsResult.data.bot_id
          startServicePayload.coze_base_url = cozeSettingsResult.data.base_url
        } else if (isDifyGraph(graphName)) {
          const difySettingsResult = difySettingsFormSchema.safeParse(difySettings)
          if (!difySettingsResult.success) {
            dispatch(
              setGlobalSettingsDialog({
                open: true,
                tab: "dify",
              }),
            )
            throw new Error(
              "Invalid Dify settings. Please check your settings.",
            )
          }
          startServicePayload.dify_api_key = difySettingsResult.data.api_key
        }
        // common -- start service
        const res = await apiStartService(startServicePayload)
        const { code, msg } = res || {}
        if (code != 0) {
          if (code == "10001") {
            toast.error(
              "The number of users experiencing the program simultaneously has exceeded the limit. Please try again later.",
            )
          } else {
            toast.error(`code:${code},msg:${msg}`)
          }
          throw new Error(msg)
        }
        dispatch(setAgentConnected(true))
        toast.success("Agent connected")
        startPing()
      }
    } catch (error) {
      console.error(error)
      toast.error("Failed to connect/disconnect agent", {
        description: (error as Error)?.message,
      })
    } finally {
      setLoading(false)
    }
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

  const onChangeMobileActiveTab = (tab: string) => {
    dispatch(setMobileActiveTab(tab as EMobileActiveTab))
  }

  return (
    <>
      {/* Action Bar */}
      <div
        className={cn(
          "mx-2 mt-2 flex items-center justify-between rounded-t-lg bg-[#181a1d] p-2 md:m-2 md:rounded-lg",
          className,
        )}
      >
        {/* -- Description Part */}
        <div className="hidden md:block">
          <span className="text-sm font-bold">Description</span>
          <span className="ml-2 text-xs text-muted-foreground">
            A Realtime Conversational AI Agent powered by TEN
          </span>
        </div>

        <Tabs
          defaultValue={mobileActiveTab}
          className="w-[400px] md:hidden"
          onValueChange={onChangeMobileActiveTab}
        >
          <TabsList>
            {Object.values(EMobileActiveTab).map((tab) => (
              <TabsTrigger key={tab} value={tab} className="w-24 text-sm">
                {MOBILE_ACTIVE_TAB_MAP[tab]}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>

        {/* -- Action Button */}
        <div className="ml-auto flex items-center gap-2">
          <SettingsDialog />
          <LoadingButton
            onClick={onClickConnect}
            variant={!agentConnected ? "default" : "destructive"}
            size="sm"
            className="w-fit min-w-24"
            loading={loading}
            svgProps={{ className: "h-4 w-4 text-muted-foreground" }}
          >
            {loading
              ? "Connecting"
              : !agentConnected
                ? "Connect"
                : "Disconnect"}
          </LoadingButton>
        </div>
      </div>
    </>
  )
}
