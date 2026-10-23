"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { useAppDispatch, useAppSelector, useMultibandTrackVolume } from "@/common";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import {
  addChatItem,
  setAgentConnected,
  setOptions,
  setRoomConnected,
  setRtmConnected,
} from "@/store/reducers/global";
import { EMessageDataType, EMessageType, type IChatItem } from "@/types";
import type { IProgressEvent } from "@/manager/rtc/types";
import BoardStage, { DEFAULT_CRAYON_SWATCHES } from "./BoardStage";
import MagicCanvasBackground, {
  type CreativeMode,
  type DoodlePhase,
} from "./MagicCanvasBackground";
import MouseTrail from "./MouseTrail";
import TranscriptPanel from "./TranscriptPanel";
import type { IMicrophoneAudioTrack } from "agora-rtc-sdk-ng";

function usePrefersReducedMotion() {
  const [reduced, setReduced] = React.useState(false);
  React.useEffect(() => {
    const mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mql.matches);
    const onChange = () => setReduced(mql.matches);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, []);
  return reduced;
}

function getLatestImage(chatItems: IChatItem[]) {
  const images = chatItems.filter((i) => i.data_type === EMessageDataType.IMAGE);
  return images.length ? images[images.length - 1] : undefined;
}

function getLastTime(chatItems: IChatItem[], predicate: (i: IChatItem) => boolean) {
  for (let idx = chatItems.length - 1; idx >= 0; idx -= 1) {
    const item = chatItems[idx];
    if (predicate(item)) return item.time ?? 0;
  }
  return 0;
}

const CRAYON_PROMPT_COLORS: Record<string, string> = {
  ink: "black",
  lavender: "lavender purple",
  mint: "mint green",
  sky: "sky blue",
  rose: "rose pink",
};

export default function ImmersiveShell() {
  const dispatch = useAppDispatch();
  const reducedMotion = usePrefersReducedMotion();

  const options = useAppSelector((s) => s.global.options);
  const roomConnected = useAppSelector((s) => s.global.roomConnected);
  const agentConnected = useAppSelector((s) => s.global.agentConnected);
  const rtmConnected = useAppSelector((s) => s.global.rtmConnected);
  const chatItems = useAppSelector((s) => s.global.chatItems);

  const mode: CreativeMode = "classic";

  const [channel, setChannel] = React.useState(options.channel || "voice_image_kids");
  const [userId, setUserId] = React.useState<number>(
    options.userId || Math.floor(100000 + Math.random() * 900000)
  );

  const rtcRef = React.useRef<any>(null);
  const rtmRef = React.useRef<any>(null);
  const [connecting, setConnecting] = React.useState(false);
  const [micTrack, setMicTrack] = React.useState<IMicrophoneAudioTrack>();
  const [micMediaTrack, setMicMediaTrack] = React.useState<MediaStreamTrack>();
  const [micMuted, setMicMuted] = React.useState(false);
  const [micDevices, setMicDevices] = React.useState<
    { label: string; value: string; deviceId: string }[]
  >([{ label: "Default microphone", value: "default", deviceId: "" }]);
  const [micValue, setMicValue] = React.useState("default");
  const [boardHeight, setBoardHeight] = React.useState<number | null>(null);
  const [crayonId, setCrayonId] = React.useState(
    DEFAULT_CRAYON_SWATCHES[0]?.id ?? "crayon"
  );
  const [clearedAt, setClearedAt] = React.useState(0);
  const activeCrayon = React.useMemo(
    () =>
      DEFAULT_CRAYON_SWATCHES.find((swatch) => swatch.id === crayonId) ??
      DEFAULT_CRAYON_SWATCHES[0],
    [crayonId]
  );
  const lineColorName = React.useMemo(() => {
    if (!activeCrayon) return "black";
    return (
      CRAYON_PROMPT_COLORS[activeCrayon.id] ||
      activeCrayon.label.toLowerCase() ||
      "black"
    );
  }, [activeCrayon]);
  const lineColorDescriptor = React.useMemo(() => {
    if (!activeCrayon) return "black";
    const hex = activeCrayon.penBody?.trim();
    if (!hex) return lineColorName;
    return `${lineColorName} (${hex})`;
  }, [activeCrayon, lineColorName]);
  const buildDoodlePrompt = React.useCallback(
    (raw: string) => {
      const colorName = lineColorName;
      const colorDescriptor = lineColorDescriptor;
      const colorLine =
        colorName === "black"
          ? "Use black lines on a plain white background."
          : `Use ${colorDescriptor} lines on a plain white background.`;
      return `${raw}\n\nDoodle style notes: simple hand-drawn line art. Two colors only (${colorDescriptor} lines and a plain white background). No shading, no gradients, no fills, no 3D or realistic rendering. No borders, frames, paper texture, paper edges, desks, or background props. Never include pens, pencils, crayons, markers, hands, shadows, or signatures. Keep the subject isolated so the white background blends into the board. ${colorLine}`;
    },
    [lineColorDescriptor, lineColorName]
  );

  React.useEffect(() => {
    if (roomConnected) return;
    if (options.channel) setChannel(options.channel);
    if (options.userId) setUserId(options.userId);
  }, [options.channel, options.userId, roomConnected]);

  React.useEffect(() => {
    let mounted = true;
    import("@/manager/rtc/rtc").then((m) => {
      if (mounted) rtcRef.current = m.rtcManager;
    });
    import("@/manager/rtm").then((m) => {
      if (mounted) rtmRef.current = m.rtmManager;
    });
    return () => {
      mounted = false;
    };
  }, []);

  const onTextChanged = React.useCallback(
    (text: IChatItem) => dispatch(addChatItem(text)),
    [dispatch]
  );
  const [progressPhase, setProgressPhase] = React.useState<
    IProgressEvent["phase"] | null
  >(null);
  const onProgressChanged = React.useCallback((progress: IProgressEvent) => {
    setProgressPhase(progress.phase);
  }, []);

  const latestImage = React.useMemo(() => getLatestImage(chatItems), [chatItems]);
  const visibleImage = React.useMemo(() => {
    if (!latestImage) return undefined;
    if (clearedAt && latestImage.time <= clearedAt) return undefined;
    return latestImage;
  }, [clearedAt, latestImage]);
  const lastUserTime = React.useMemo(
    () =>
      getLastTime(
        chatItems,
        (i) => i.type === EMessageType.USER && i.data_type === EMessageDataType.TEXT
      ),
    [chatItems]
  );
  const lastImageTime = latestImage?.time ?? 0;
  const hasRequest = lastUserTime > 0;
  const imageArrived = hasRequest && lastImageTime >= lastUserTime;

  React.useEffect(() => {
    if (lastUserTime <= 0) return;
    setProgressPhase(null);
  }, [lastUserTime]);

  const [phase, setPhase] = React.useState<DoodlePhase>("idle");
  React.useEffect(() => {
    if (imageArrived) {
      setPhase("complete");
      const t = window.setTimeout(() => setPhase("idle"), 1700);
      return () => window.clearTimeout(t);
    }

    if (progressPhase === "queued") {
      setPhase("queued");
      const t1 = window.setTimeout(() => setPhase("sketch"), 450);
      const t2 = window.setTimeout(() => setPhase("color"), 1550);
      return () => {
        window.clearTimeout(t1);
        window.clearTimeout(t2);
      };
    }

    if (progressPhase === "drawing") {
      setPhase("sketch");
      const t = window.setTimeout(() => setPhase("color"), 1100);
      return () => window.clearTimeout(t);
    }

    if (progressPhase === "final") {
      setPhase("complete");
      const t = window.setTimeout(() => setPhase("idle"), 1700);
      return () => window.clearTimeout(t);
    }

    setPhase("idle");
    return;
  }, [imageArrived, progressPhase]);

  const canConnect = channel.trim().length > 0 && userId > 0;
  const controlsEnabled = roomConnected && agentConnected && rtmConnected;
  const isBoardGenerating =
    phase === "queued" || phase === "sketch" || phase === "color";
  const isConnected = roomConnected && agentConnected;

  const micBands = useMultibandTrackVolume(micMediaTrack, 10, 80, 520);
  const micLevels = React.useMemo(() => {
    return micBands.map((band) => {
      if (!band.length) return 0;
      let sum = 0;
      for (let i = 0; i < band.length; i += 1) sum += band[i];
      return sum / band.length;
    });
  }, [micBands]);

  React.useEffect(() => {
    if (!micTrack) {
      setMicMuted(false);
      return;
    }
    micTrack.setMuted(micMuted);
  }, [micMuted, micTrack]);

  React.useEffect(() => {
    if (!micTrack) {
      setMicDevices([{ label: "Default microphone", value: "default", deviceId: "" }]);
      setMicValue("default");
      return;
    }
    let active = true;
    const currentLabel = micTrack.getTrackLabel() || "Default microphone";
    const load = async () => {
      try {
        const mod = await import("agora-rtc-sdk-ng");
        if (!active) return;
        const arr = await mod.default.getMicrophones();
        if (!active) return;
        const usedValues = new Set(["default"]);
        const items = arr.map((item, index) => {
          const label = item.label?.trim() || `Microphone ${index + 1}`;
          let value = (item.deviceId || label).trim();
          if (!value) value = `mic-${index + 1}`;
          if (usedValues.has(value)) {
            value = `${value}-${index + 1}`;
          }
          usedValues.add(value);
          return {
            label,
            value,
            deviceId: item.deviceId,
          };
        });
        setMicDevices([
          { label: "Default microphone", value: "default", deviceId: "" },
          ...items,
        ]);
        const found = items.find((item) => item.label === currentLabel);
        setMicValue(found?.value ?? "default");
      } catch {
        if (!active) return;
        setMicDevices([{ label: "Default microphone", value: "default", deviceId: "" }]);
        setMicValue("default");
      }
    };
    load();
    return () => {
      active = false;
    };
  }, [micTrack]);

  const connect = async () => {
    if (!canConnect) {
      toast.error("Please enter a channel and user id.");
      return;
    }

    if (connecting) return;
    setConnecting(true);

    try {
      const { apiStartService } = await import("@/common");
      const startResp = await apiStartService({
        channel,
        userId,
        graphName: "voice_image_kids",
        language: "en-US",
        voiceType: "female",
      });
      const { code, msg } = startResp || {};
      if (code != null && String(code) !== "0") {
        throw new Error(msg || `Agent start failed (code=${code})`);
      }
      dispatch(setAgentConnected(true));

      const rtc = rtcRef.current;
      if (!rtc) {
        throw new Error("RTC manager not ready yet. Please try again.");
      }
      rtc.off("textChanged", onTextChanged);
      rtc.on("textChanged", onTextChanged);
      rtc.off("progressChanged", onProgressChanged);
      rtc.on("progressChanged", onProgressChanged);
      await rtc.createMicrophoneAudioTrack();
      const track: IMicrophoneAudioTrack | undefined = rtc.localTracks?.audioTrack;
      setMicTrack(track);
      setMicMediaTrack(track?.getMediaStreamTrack());
      await rtc.join({ channel, userId });

      dispatch(
        setOptions({
          ...options,
          channel,
          userId,
          appId: rtc.appId ?? "",
          token: rtc.token ?? "",
        })
      );
      await rtc.publish();
      dispatch(setRoomConnected(true));

      const rtm = rtmRef.current;
      if (rtm?.init) {
        await rtm.init({
          channel,
          userId,
          appId: rtc.appId ?? "",
          token: rtc.token ?? "",
        });
        const ok = Boolean(rtm?._client);
        dispatch(setRtmConnected(ok));
        if (!ok) {
          toast.error("Connected, but messaging failed. Text prompts are disabled.");
        }
      }

      toast.success("Doodle board connected.");
    } catch (err: any) {
      console.error(err);
      try {
        const { apiStopService } = await import("@/common");
        await apiStopService(channel);
      } catch {
        // best-effort
      }
      toast.error(err?.message || "Failed to connect.");
      dispatch(setAgentConnected(false));
      dispatch(setRoomConnected(false));
      dispatch(setRtmConnected(false));
    } finally {
      setConnecting(false);
    }
  };

  const disconnect = async () => {
    if (connecting) return;
    setConnecting(true);
    try {
      const { apiStopService } = await import("@/common");
      await apiStopService(channel);
    } catch {
      // best-effort
    }
    try {
      await rtmRef.current?.destroy?.();
      rtcRef.current?.off?.("textChanged", onTextChanged);
      rtcRef.current?.off?.("progressChanged", onProgressChanged);
      await rtcRef.current?.destroy?.();
    } finally {
      dispatch(setRtmConnected(false));
      dispatch(setRoomConnected(false));
      dispatch(setAgentConnected(false));
      setProgressPhase(null);
      setMicMediaTrack(undefined);
      setMicTrack(undefined);
      toast.message("Disconnected.");
      setConnecting(false);
    }
  };

  const sendText = async (text: string) => {
    const msg = text.trim();
    if (!msg) return;
    if (!controlsEnabled) {
      toast.error("Connect the board first.");
      return;
    }
    try {
      await rtmRef.current?.sendText?.(buildDoodlePrompt(msg));
      dispatch(
        addChatItem({
          userId: options.userId || userId,
          text: msg,
          type: EMessageType.USER,
          data_type: EMessageDataType.TEXT,
          isFinal: true,
          time: Date.now(),
        })
      );
    } catch (err: any) {
      console.error(err);
      toast.error(err?.message || "Failed to send.");
    }
  };

  const onMicChange = async (value: string) => {
    setMicValue(value);
    const target = micDevices.find((item) => item.value === value);
    if (!target || !micTrack) return;
    await micTrack.setDevice(target.deviceId);
  };

  const selectedMicLabel =
    micDevices.find((item) => item.value === micValue)?.label ||
    "Microphone";

  const boardRef = React.useRef<HTMLDivElement | null>(null);
  React.useEffect(() => {
    if (!boardRef.current) return;
    const node = boardRef.current;
    let raf = 0;
    const update = () => {
      raf = window.requestAnimationFrame(() => {
        const next = Math.round(node.getBoundingClientRect().height);
        setBoardHeight((prev) => (prev === next ? prev : next));
      });
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(node);
    return () => {
      observer.disconnect();
      if (raf) window.cancelAnimationFrame(raf);
    };
  }, []);

  const boardPose = React.useMemo(() => {
    if (reducedMotion) {
      return { x: 0, rotateX: 0, rotateY: 0, scale: 1 };
    }
    if (isBoardGenerating) {
      return { x: -32, rotateX: 7, rotateY: -14, scale: 1.02 };
    }
    return { x: 0, rotateX: 0, rotateY: 0, scale: 1 };
  }, [isBoardGenerating, reducedMotion]);

  const boardPoseTransition = React.useMemo(() => {
    if (reducedMotion) return { duration: 0 };
    return {
      type: "spring",
      stiffness: isBoardGenerating ? 200 : 260,
      damping: isBoardGenerating ? 24 : 26,
      mass: 0.7,
    };
  }, [isBoardGenerating, reducedMotion]);
  const penBodyColor = activeCrayon?.penBody;
  const penTopColor = activeCrayon?.penTop;
  const handleErase = React.useCallback(() => {
    setClearedAt(Date.now());
  }, []);

  return (
    <div className="relative min-h-screen overflow-hidden">
      <MouseTrail enabled={!reducedMotion} mode={mode} />
      <MagicCanvasBackground
        phase={phase}
        mode={mode}
        reducedMotion={reducedMotion}
      />

      <div className="relative z-10 flex min-h-screen flex-col">
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 pb-28 pt-10 sm:pb-32 sm:pt-14">
          <div className="grid w-full items-stretch gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
            <motion.div
              className="relative"
              style={{ perspective: 1400 }}
              animate={
                reducedMotion
                  ? undefined
                  : {
                      y: [0, -8, 0],
                      rotateZ: [0.35, -0.35, 0.35],
                    }
              }
              transition={
                reducedMotion
                  ? undefined
                  : { duration: 6, repeat: Infinity, ease: "easeInOut" }
              }
            >
              <motion.div
                ref={boardRef}
                className="will-change-transform"
                style={{ transformStyle: "preserve-3d" }}
                animate={boardPose}
                transition={boardPoseTransition as any}
              >
                <BoardStage
                  imageUrl={visibleImage?.text}
                  caption="latest doodle"
                  phase={phase}
                  reducedMotion={reducedMotion}
                  swatches={DEFAULT_CRAYON_SWATCHES}
                  activeSwatchId={crayonId}
                  onSwatchSelect={setCrayonId}
                  penBodyColor={penBodyColor}
                  penTopColor={penTopColor}
                  onErase={handleErase}
                  eraseDisabled={!visibleImage}
                />
              </motion.div>
            </motion.div>
            <TranscriptPanel
              className="h-full"
              style={
                boardHeight
                  ? {
                      height: boardHeight,
                      maxHeight: boardHeight,
                    }
                  : undefined
              }
              disabled={!controlsEnabled}
              onSend={sendText}
              placeholder={
                controlsEnabled
                  ? "Tell it what to draw…"
                  : "Connect the board to type prompts…"
              }
            />
          </div>
        </main>

        <footer className="fixed inset-x-0 bottom-0 z-30 px-4 pb-4">
          <div className="mx-auto w-full max-w-6xl">
            <div className={cn("mx-auto flex w-fit flex-nowrap items-center justify-center gap-4 py-2")}>
              <Select value={micValue} onValueChange={onMicChange} disabled={!micTrack}>
                <SelectTrigger
                  className={cn(
                    "h-11 w-44 bg-white/85 px-4 text-left shadow-none focus:ring-0",
                    "crayon-control"
                  )}
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <span
                      className={cn(
                        "h-2.5 w-2.5 rounded-full",
                        micTrack && !micMuted ? "bg-emerald-500" : "bg-amber-500"
                      )}
                    />
                    <div className="min-w-0">
                      <div className="truncate font-medium text-sm">{selectedMicLabel}</div>
                      <div className="mt-1 flex items-center gap-1">
                        {micLevels.slice(0, 10).map((lvl, idx) => {
                          const h = Math.max(2, Math.min(12, Math.round(lvl * 14)));
                          return (
                            <span
                              // biome-ignore lint/suspicious/noArrayIndexKey: fixed-size meter
                              key={idx}
                              className={cn(
                                "inline-block w-[3px] rounded-full",
                                micTrack && !micMuted
                                  ? "bg-[#F97316]/70"
                                  : "bg-black/10"
                              )}
                              style={{ height: h }}
                            />
                          );
                        })}
                        <span className="ml-2 text-muted-foreground text-xs">
                          {micMuted ? "muted" : isConnected ? "connected" : "offline"}
                        </span>
                      </div>
                    </div>
                  </div>
                </SelectTrigger>
                <SelectContent className="crayon-border bg-white/90">
                  {micDevices.map((item, idx) => (
                    <SelectItem key={`${item.value}-${item.deviceId || idx}`} value={item.value}>
                      {item.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Button
                type="button"
                className="h-11 w-44 shadow-none crayon-control"
                variant="secondary"
                onClick={() => setMicMuted((prev) => !prev)}
                disabled={!micTrack}
              >
                {micMuted ? "Unmute" : "Mute"}
              </Button>

              <Button
                type="button"
                className="h-11 w-44 shadow-none crayon-control"
                variant={isConnected ? "secondary" : "default"}
                onClick={isConnected ? disconnect : connect}
                disabled={connecting || (!isConnected && !canConnect)}
              >
                {isConnected ? "Disconnect" : "Connect"}
              </Button>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}
