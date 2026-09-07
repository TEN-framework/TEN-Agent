"use client";

import { Send } from "lucide-react";
import * as React from "react";
import { useAppDispatch, useAppSelector, useAutoScroll } from "@/common";
import MessageList from "@/components/Chat/MessageList";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { rtmManager } from "@/manager/rtm";
import { addChatItem } from "@/store/reducers/global";
import {
  EMessageDataType,
  EMessageType,
  type IRTMTextItem,
} from "@/types";

export default function ChatCard(props: { className?: string }) {
  const { className } = props;
  const [modal2Open, setModal2Open] = React.useState(false);
  const [inputValue, setInputValue] = React.useState("");

  const rtmConnected = useAppSelector((state) => state.global.rtmConnected);
  const dispatch = useAppDispatch();
  const graphName = useAppSelector((state) => state.global.selectedGraphId);
  const agentConnected = useAppSelector((state) => state.global.agentConnected);
  const options = useAppSelector((state) => state.global.options);

  const disableInputMemo = React.useMemo(() => {
    return (
      !options.channel ||
      !options.userId ||
      !options.appId ||
      !options.token ||
      !rtmConnected ||
      !agentConnected
    );
  }, [
    options.channel,
    options.userId,
    options.appId,
    options.token,
    rtmConnected,
    agentConnected,
  ]);

  // const chatItems = genRandomChatList(10)
  const chatRef = React.useRef(null);

  useAutoScroll(chatRef);

  const onTextChanged = (text: IRTMTextItem) => {
    if (text.data_type === "transcribe") {
      dispatch(
        addChatItem({
          userId: text.stream_id,
          text: text.text,
          type: text.role === "assistant" ? EMessageType.AGENT : EMessageType.USER,
          data_type: EMessageDataType.TEXT,
          isFinal: text.is_final,
          time: text.text_ts,
        })
      );
      return;
    }
    if (text.data_type === "input_text") {
      dispatch(
        addChatItem({
          userId: text.stream_id,
          text: text.text,
          type: EMessageType.USER,
          data_type: EMessageDataType.TEXT,
          isFinal: true,
          time: text.text_ts,
        })
      );
    }
  };

  React.useEffect(() => {
    if (rtmConnected) {
      rtmManager.on("rtmMessage", onTextChanged);
    }
    return () => {
      if (rtmConnected) {
        rtmManager.off("rtmMessage", onTextChanged);
      }
    };
  }, [rtmConnected]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(e.target.value);
  };

  const handleInputSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!inputValue || disableInputMemo) {
      return;
    }
    rtmManager.sendText(inputValue);
    setInputValue("");
  };

  return (
    <>
      {/* Chat Card */}
      <div className={cn("flex h-full min-h-0 overflow-hidden", className)}>
        <div className="flex w-full flex-1 flex-col p-4">
          {/* Scrollable messages container */}
          <div className="flex-1 overflow-y-auto" ref={chatRef}>
            <MessageList />
          </div>
          {/* Input area */}
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
                  "grow rounded-md border bg-background p-1.5 focus:outline-hidden focus:ring-1 focus:ring-ring",
                  {
                    ["cursor-not-allowed"]: disableInputMemo,
                  }
                )}
              />
              <Button
                type="submit"
                disabled={disableInputMemo || inputValue.length === 0}
                size="icon"
                variant="outline"
                className={cn("bg-transparent", {
                  ["opacity-50"]: disableInputMemo || inputValue.length === 0,
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
  );
}
