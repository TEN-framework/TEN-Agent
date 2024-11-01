"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { LanguageSelect, GraphSelect } from "@/components/Chat/ChatCfgSelect"
import PdfSelect from "@/components/pdfSelect"
import {
  useAppDispatch,
  useAutoScroll,
  LANGUAGE_OPTIONS,
  useAppSelector,
  GRAPH_OPTIONS,
  isRagGraph,
} from "@/common"
import {
  setGraphName,
  setLanguage,
  setRtmConnected,
  addChatItem,
} from "@/store/reducers/global"
import MessageList from "@/components/Chat/MessageList"
import { Button } from "@/components/ui/button"
import { Send } from "lucide-react"
import { rtmManager } from "@/manager/rtm"
import {
  ITextItem,
  type IRTMTextItem,
  EMessageType,
  ERTMTextType,
} from "@/types"

let hasInit: boolean = false

export default function ChatCard(props: { className?: string }) {
  const { className } = props
  const [inputValue, setInputValue] = React.useState("")

  const graphName = useAppSelector((state) => state.global.graphName)
  const chatItems = useAppSelector((state) => state.global.chatItems)
  const rtmConnected = useAppSelector((state) => state.global.rtmConnected)
  const options = useAppSelector((state) => state.global.options)
  const dispatch = useAppDispatch()

  const disableInputMemo = React.useMemo(() => {
    return (
      !options.channel ||
      !options.userId ||
      !options.appId ||
      !options.token ||
      !rtmConnected
    )
  }, [
    options.channel,
    options.userId,
    options.appId,
    options.token,
    rtmConnected,
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
      if (hasInit) {
        destory()
      }
    }
  }, [options.channel, options.userId, options.appId, options.token])

  const init = async () => {
    console.log("[ChatCard] init")
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
    console.log("[ChatCard] destory")
    rtmManager.off("rtmMessage", onTextChanged)
    await rtmManager.destroy()
    dispatch(setRtmConnected(false))
    hasInit = false
  }

  const onTextChanged = (text: IRTMTextItem) => {
    console.log("[ChatCard] onTextChanged", text)
    if (text.type == ERTMTextType.TRANSCRIBE) {
      // const isAgent = Number(text.uid) != Number(options.userId)
      dispatch(
        addChatItem({
          userId: options.userId,
          text: text.text,
          type: text.stream_id === "0" ? EMessageType.AGENT : EMessageType.USER,
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
          <div className="flex items-center justify-end gap-4">
            <GraphSelect />
            <LanguageSelect />
            {isRagGraph(graphName) && <PdfSelect />}
          </div>
          {/* Chat messages would go here */}
          <MessageList />
          <div className="border-t pt-4">
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
                className="flex-grow rounded-md border bg-background p-1.5 focus:outline-none focus:ring-1 focus:ring-ring"
              />
              <Button
                type="submit"
                disabled={disableInputMemo || inputValue.length == 0}
                size="icon"
                variant="outline"
                className="bg-transparent"
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
