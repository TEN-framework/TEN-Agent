"use client";

import type { IMicrophoneAudioTrack } from "agora-rtc-sdk-ng";
import * as React from "react";
import { useAppDispatch, useAppSelector } from "@/common";
import MicrophoneBlock from "@/components/Agent/Microphone";
import { cn } from "@/lib/utils";
import { type IRtcUser, type IUserTracks, rtcManager } from "@/manager";
import { rtmManager } from "@/manager/rtm";
import {
  addChatItem,
  setOptions,
  setRoomConnected,
  setRtmConnected,
  showFortuneModal,
  triggerFestivalEffect,
} from "@/store/reducers/global";
import {
  EMessageDataType,
  EMessageType,
  type IChatItem,
  type IRTMTextItem,
} from "@/types";

let hasInit: boolean = false;
const TRANSCRIPT_FLUSH_INTERVAL_MS = 100;

export default function RTCCard(props: { className?: string }) {
  const { className } = props;

  const dispatch = useAppDispatch();
  const options = useAppSelector((state) => state.global.options);
  const { userId, channel } = options;
  const [audioTrack, setAudioTrack] = React.useState<IMicrophoneAudioTrack>();
  const pendingTranscriptRef = React.useRef<Map<string, IChatItem>>(new Map());
  const transcriptFlushTimerRef = React.useRef<ReturnType<
    typeof setInterval
  > | null>(null);

  React.useEffect(() => {
    if (!options.channel) {
      return;
    }
    if (hasInit) {
      return;
    }

    init();

    return () => {
      if (hasInit) {
        destory();
      }
    };
  }, [options.channel]);

  const init = async () => {
    try {
      rtcManager.on("localTracksChanged", onLocalTracksChanged);
      rtcManager.on("remoteUserChanged", onRemoteUserChanged);
      rtmManager.on("rtmMessage", onRtmMessage);

      await rtcManager.prepareSession({
        channel,
        userId,
        enableSpatialwalk: true,
      });
      dispatch(
        setOptions({
          ...options,
          appId: rtcManager.appId ?? "",
          token: rtcManager.token ?? "",
          spatialwalkToken: rtcManager.spatialwalkToken ?? "",
        })
      );
      await rtcManager.waitForNativeClient(10000);
      await rtcManager.createMicrophoneAudioTrack();
      await rtcManager.publish();

      await rtmManager.init({
        channel,
        userId,
        appId: rtcManager.appId ?? "",
        token: rtcManager.token ?? "",
      });
      if (transcriptFlushTimerRef.current) {
        clearInterval(transcriptFlushTimerRef.current);
      }
      transcriptFlushTimerRef.current = setInterval(() => {
        flushPendingTranscripts();
      }, TRANSCRIPT_FLUSH_INTERVAL_MS);

      dispatch(setRoomConnected(true));
      dispatch(setRtmConnected(true));
      hasInit = true;
    } catch (error) {
      console.error("[rtc/rtm] init failed", error);
      dispatch(setRoomConnected(false));
      dispatch(setRtmConnected(false));
      rtcManager.off("localTracksChanged", onLocalTracksChanged);
      rtcManager.off("remoteUserChanged", onRemoteUserChanged);
      rtmManager.off("rtmMessage", onRtmMessage);
      flushPendingTranscripts();
      if (transcriptFlushTimerRef.current) {
        clearInterval(transcriptFlushTimerRef.current);
        transcriptFlushTimerRef.current = null;
      }
      try {
        await rtmManager.destroy();
      } catch {}
      hasInit = false;
    }
  };

  const destory = async () => {
    rtcManager.off("localTracksChanged", onLocalTracksChanged);
    rtcManager.off("remoteUserChanged", onRemoteUserChanged);
    rtmManager.off("rtmMessage", onRtmMessage);
    flushPendingTranscripts();
    if (transcriptFlushTimerRef.current) {
      clearInterval(transcriptFlushTimerRef.current);
      transcriptFlushTimerRef.current = null;
    }
    await rtmManager.destroy();
    dispatch(setRtmConnected(false));
    await rtcManager.destroy();
    dispatch(setRoomConnected(false));
    hasInit = false;
  };

  const onRemoteUserChanged = (user: IRtcUser) => {
    // Spatialwalk SDK will play audio in sync with animation.
    user.audioTrack?.stop();
  };

  const onLocalTracksChanged = (tracks: IUserTracks) => {
    const { audioTrack } = tracks;
    if (audioTrack) {
      setAudioTrack(audioTrack);
    }
  };

  const enqueueTranscript = (item: IChatItem) => {
    const key = `${item.userId}-${item.type}`;
    pendingTranscriptRef.current.set(key, item);
  };

  const flushPendingTranscripts = () => {
    if (!pendingTranscriptRef.current.size) {
      return;
    }
    const items = Array.from(pendingTranscriptRef.current.values()).sort(
      (a, b) => a.time - b.time
    );
    pendingTranscriptRef.current.clear();
    for (const item of items) {
      dispatch(addChatItem(item));
    }
  };

  const onRtmMessage = (item: IRTMTextItem) => {
    if (item.data_type === "transcribe") {
      enqueueTranscript({
        userId: item.stream_id,
        text: item.text,
        type: item.role === "assistant" ? EMessageType.AGENT : EMessageType.USER,
        data_type: EMessageDataType.TEXT,
        isFinal: item.is_final,
        time: item.text_ts,
      });
      return;
    }

    if (item.data_type !== "raw" || !item.text) {
      return;
    }

    let rawPayload: any = null;
    try {
      rawPayload = JSON.parse(item.text);
    } catch {
      return;
    }

    if (!rawPayload || rawPayload.type !== "action") {
      return;
    }

    const action = rawPayload.data?.action;
    const actionData = rawPayload.data?.data ?? {};
    if (action === "trigger_effect") {
      const effectName = actionData?.name;
      if (effectName === "gold_rain" || effectName === "fireworks") {
        dispatch(triggerFestivalEffect({ name: effectName }));
      }
      return;
    }
    if (action === "show_fortune_result") {
      const imageId = actionData?.image_id;
      if (typeof imageId === "string" && imageId.trim().length > 0) {
        dispatch(showFortuneModal({ imageId }));
      }
    }
  };

  return (
    <div className={cn("flex h-full min-h-0 flex-col", className)}>
      <div className="w-full flex-shrink-0 space-y-2 px-2 py-2">
        <MicrophoneBlock audioTrack={audioTrack} />
      </div>
    </div>
  );
}
