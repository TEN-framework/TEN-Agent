"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import {
  RemotePropertyCfgSheet,
} from "@/components/Chat/ChatCfgPropertySelect";
import PdfSelect from "@/components/Chat/PdfSelect";
import {
  genRandomChatList,
  useAppDispatch,
  useAutoScroll,
  LANGUAGE_OPTIONS,
  useAppSelector,
  GRAPH_OPTIONS,
  isRagGraph,
  isEditModeOn,
} from "@/common";
import {
  setRtmConnected,
  addChatItem,
  setSelectedGraphId,
  setLanguage,
} from "@/store/reducers/global";
import MessageList from "@/components/Chat/MessageList";
import { Button } from "@/components/ui/button";
import { Send } from "lucide-react";
import { rtmManager } from "@/manager/rtm";
import { type IRTMTextItem, EMessageDataType, EMessageType, ERTMTextType } from "@/types";
import { RemoteGraphSelect } from "@/components/Chat/ChatCfgGraphSelect";
import { RemoteModuleCfgSheet } from "@/components/Chat/ChatCfgModuleSelect";

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
    console.log("[rtm] onTextChanged", text);
    if (text.type == ERTMTextType.TRANSCRIBE) {
      // const isAgent = Number(text.uid) != Number(options.userId)
      dispatch(
        addChatItem({
          userId: options.userId,
          text: text.text,
          type: text.stream_id === "0" ? EMessageType.AGENT : EMessageType.USER,
          data_type: EMessageDataType.TEXT,
          isFinal: text.is_final,
          time: text.ts,
        })
      );
    }
    if (text.type == ERTMTextType.INPUT_TEXT) {
      dispatch(
        addChatItem({
          userId: options.userId,
          text: text.text,
          type: EMessageType.USER,
          data_type: EMessageDataType.TEXT,
          isFinal: true,
          time: text.ts,
        })
      );
    }
  };

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
      <div className={cn("h-full overflow-hidden min-h-0 flex", className)}>
        <div className="flex w-full flex-col p-4 flex-1">
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
            <form onSubmit={handleInputSubmit} className="flex items-center space-x-2">
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
