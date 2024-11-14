"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { LanguageSelect, GraphSelect } from "@/components/Chat/ChatCfgSelect"
import PdfSelect from "@/components/Chat/PdfSelect"
import { useAppDispatch, useAppSelector, isRagGraph } from "@/common"
import { setRtmConnected, addChatItem } from "@/store/reducers/global"
import MessageList from "@/components/Chat/MessageList"
import { Button } from "@/components/ui/button"
import { Send } from "lucide-react"
import { rtmManager } from "@/manager/rtm"
import { type IRTMTextItem, EMessageType, ERTMTextType } from "@/types"

let hasInit: boolean = false

export default function ChatCard(props: { className?: string }) {
  const { className } = props
  const [inputValue, setInputValue] = React.useState("")

  const graphName = useAppSelector((state) => state.global.graphName)
  const rtmConnected = useAppSelector((state) => state.global.rtmConnected)
  const options = useAppSelector((state) => state.global.options)
  const agentConnected = useAppSelector((state) => state.global.agentConnected)
  const dispatch = useAppDispatch()

  const disableInputMemo = React.useMemo(() => {
    return (
      !options.channel ||
      !options.userId ||
      !options.appId ||
      !options.token ||
      !rtmConnected ||
      !agentConnected
    )
  }, [
    options.channel,
    options.userId,
    options.appId,
    options.token,
    rtmConnected,
    agentConnected,
  ])

  React.useEffect(() => {
    if (
      !options.channel ||
      !options.userId ||
      !options.appId ||
      !options.token
    ) {
      return
    }
    if (hasInit) {
      return
    }

    init()

    return () => {
      // if (hasInit) {
      //   destory()
      // }
    }
  }, [options.channel, options.userId, options.appId, options.token])

  const init = async () => {
    console.log("[rtm] init")
    await rtmManager.init({
      channel: options.channel,
      userId: options.userId,
      appId: options.appId,
      token: options.token,
    })
    dispatch(setRtmConnected(true))
    rtmManager.on("rtmMessage", onTextChanged)
    hasInit = true
  }
  const destory = async () => {
    console.log("[rtm] destory")
    rtmManager.off("rtmMessage", onTextChanged)
    await rtmManager.destroy()
    dispatch(setRtmConnected(false))
    hasInit = false
  }

  const onTextChanged = (text: IRTMTextItem) => {
    console.log("[rtm] onTextChanged", text)
    if (text.type == ERTMTextType.TRANSCRIBE) {
      // const isAgent = Number(text.uid) != Number(options.userId)
      dispatch(
        addChatItem({
          userId: options.userId,
          text: text.text,
          type: `${text.stream_id}` === "0" ? EMessageType.AGENT : EMessageType.USER,
          isFinal: text.is_final,
          time: text.ts,
        }),
      )
    }
    if (text.type == ERTMTextType.INPUT_TEXT) {
      dispatch(
        addChatItem({
          userId: options.userId,
          text: text.text,
          type: EMessageType.USER,
          isFinal: true,
          time: text.ts,
        }),
      )
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(e.target.value)
  }

  const handleInputSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    if (!inputValue || disableInputMemo) {
      return
    }
    rtmManager.sendText(inputValue)
    setInputValue("")
  }

  return (
    <>
      {/* Chat Card */}
      <div className={cn("flex-grow", className)}>
        <div className="flex h-full w-full flex-col p-4">
          {/* Action Bar */}
          <div className="flex w-full flex-wrap items-center justify-end gap-x-4 gap-y-2">
            <GraphSelect />
            <LanguageSelect />
            {isRagGraph(graphName) && <PdfSelect />}
          </div>
          {/* Chat messages would go here */}
          <MessageList />
          <div
            className={cn("border-t pt-4", {
              ["hidden"]: !graphName.includes("rtm"), // TODO: TMP use rtm key word
            })}
          >
            <form
              onSubmit={handleInputSubmit}
              className="flex items-center space-x-2"
            >
              <input
                type="text"
                disabled={disableInputMemo}
                placeholder="Type a message..."
                value={inputValue}
                onChange={handleInputChange}
                className={cn(
                  "flex-grow rounded-md border bg-background p-1.5 focus:outline-none focus:ring-1 focus:ring-ring",
                  {
                    ["cursor-not-allowed"]: disableInputMemo,
                  },
                )}
              />
              <Button
                type="submit"
                disabled={disableInputMemo || inputValue.length == 0}
                size="icon"
                variant="outline"
                className={cn("bg-transparent", {
                  ["opacity-50"]: disableInputMemo || inputValue.length == 0,
                  ["cursor-not-allowed"]: disableInputMemo,
                })}
              >
                <Send className="h-4 w-4" />
                <span className="sr-only">Send message</span>
              </Button>
            </form>
          </div>
        </div>
      </div>
    </>
  )
}
