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
import { setGraphName, setLanguage } from "@/store/reducers/global"
import MessageList from "@/components/Chat/MessageList"
import { Button } from "@/components/ui/button"
import { Send } from "lucide-react"
import { rtmManager } from "@/manager/rtm"

export default function ChatCard(props: { className?: string }) {
  const { className } = props

  const graphName = useAppSelector((state) => state.global.graphName)
  const chatItems = useAppSelector((state) => state.global.chatItems)

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
              onSubmit={(e) => {
                e.preventDefault()
              }}
              className="flex items-center space-x-2"
            >
              <input
                type="text"
                placeholder="Type a message..."
                // value={inputValue}
                // onChange={handleInputChange}
                className="flex-grow rounded-md border bg-background p-1.5 focus:outline-none focus:ring-1 focus:ring-ring"
              />
              <Button
                type="submit"
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
