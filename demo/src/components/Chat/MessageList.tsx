import * as React from "react"
import {
  useAppDispatch,
  useAutoScroll,
  LANGUAGE_OPTIONS,
  useAppSelector,
  GRAPH_OPTIONS,
  isRagGraph,
} from "@/common"
import { EMessageType, type IChatItem } from "@/types"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { cn } from "@/lib/utils"

export default function MessageList(props: { className?: string }) {
  const { className } = props

  const chatItems = useAppSelector((state) => state.global.chatItems)

  const containerRef = React.useRef<HTMLDivElement>(null)

  useAutoScroll(containerRef)

  return (
    <div
      ref={containerRef}
      className={cn("flex-grow overflow-y-auto p-4", className)}
    >
      {chatItems.map((item, index) => {
        return <MessageItem data={item} key={item.time} />
      })}
    </div>
  )
}

export function MessageItem(props: { data: IChatItem }) {
  const { data } = props

  return (
    <>
      <div
        className={cn("flex items-start space-x-2", {
          "justify-end": data.type === EMessageType.USER,
        })}
      >
        <Avatar>
          <AvatarFallback>
            {data.type === EMessageType.AGENT ? "AG" : "U"}
          </AvatarFallback>
        </Avatar>
        <div className="max-w-[80%] rounded-lg bg-secondary p-2 text-secondary-foreground">
          <p>{data.text}</p>
        </div>
      </div>
    </>
  )
}
