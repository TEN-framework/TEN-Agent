import * as React from "react"
import {
  useAppDispatch,
  useAutoScroll,
  LANGUAGE_OPTIONS,
  useAppSelector,
  GRAPH_OPTIONS,
  isRagGraph,
} from "@/common"
import { Bot } from "lucide-react"
import { EMessageDataType, EMessageType, type IChatItem } from "@/types"
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
      className={cn("flex-grow space-y-2 overflow-y-auto p-4", className)}
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
        className={cn("flex items-start gap-2", {
          "flex-row-reverse": data.type === EMessageType.USER,
        })}
      >
        {data.type === EMessageType.AGENT && <Avatar>
          <AvatarFallback>
            <Bot />
          </AvatarFallback>
        </Avatar>
        }
        <div className="max-w-[80%] rounded-lg bg-secondary p-2 text-secondary-foreground">
          {data.data_type === EMessageDataType.IMAGE ? (
            <img src={data.text} alt="chat" className="w-full" />
          ) : (
            <p>{data.text}</p>
          )}
        </div>
      </div>
    </>
  )
}
