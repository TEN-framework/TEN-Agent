"use client";

import {
  AvatarManager,
  AvatarSDK,
  AvatarView,
  DrivingServiceMode,
  Environment,
} from "@spatialwalk/avatarkit";
import type { IAgoraRTCClient } from "agora-rtc-sdk-ng";
import { AgoraProvider, AvatarPlayer } from "@spatialwalk/avatarkit-rtc";
import { MessagesSquare, MessagesSquareIcon } from "lucide-react";
import React, { useEffect, useRef, useState } from "react";
import { useAppSelector } from "@/common";
import AvatarConnectButton from "@/components/Agent/AvatarConnectButton";
import AvatarTranscriptOverlay from "@/components/Agent/AvatarTranscriptOverlay";
import { Button } from "@/components/ui/button";
import { rtcManager } from "@/manager";
import {
  getSpatialwalkUrlConfig,
  validateSpatialwalkRequiredConfig,
} from "@/common/spatialwalk";
import { cn } from "@/lib/utils";

let initKey: string | null = null;
let initPromise: Promise<void> | null = null;

const ensureSdkInitialized = async (appId: string, environment: "cn" | "intl") => {
  const nextKey = `${appId}:${environment}`;
  if (initPromise && initKey === nextKey) {
    return initPromise;
  }
  if (initKey && initKey !== nextKey) {
    AvatarSDK.cleanup();
    initPromise = null;
  }
  initKey = nextKey;
  initPromise = AvatarSDK.initialize(appId, {
    environment: environment === "cn" ? Environment.cn : Environment.intl,
    drivingServiceMode: DrivingServiceMode.host,
  });
  return initPromise;
};

export default function AvatarSpatialwalk() {
  const options = useAppSelector((state) => state.global.options);
  const spatialwalkSettings = useAppSelector(
    (state) => state.global.spatialwalkSettings
  );
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [showTranscript, setShowTranscript] = useState(true);

  const containerRef = useRef<HTMLDivElement>(null);
  const avatarViewRef = useRef<AvatarView | null>(null);
  const playerRef = useRef<AvatarPlayer | null>(null);
  const playerConnectedRef = useRef(false);
  const lastConnectKeyRef = useRef<string | null>(null);
  const [spatialwalkUrlConfig] = useState(getSpatialwalkUrlConfig());

  useEffect(() => {
    let cancelled = false;

    const setup = async () => {
      setErrorMessage("");
      const validation = validateSpatialwalkRequiredConfig(spatialwalkUrlConfig);
      if (!validation.isValid) {
        setErrorMessage(validation.message);
        return;
      }
      if (!containerRef.current) {
        return;
      }
      setLoading(true);

      try {
        const connectKey = [
          spatialwalkUrlConfig.appId,
          spatialwalkUrlConfig.avatarId,
          spatialwalkSettings.environment,
          options.appId || "",
          options.channel || "",
          String(options.userId || ""),
          options.token || "",
        ].join("|");
        if (
          lastConnectKeyRef.current === connectKey &&
          playerRef.current &&
          playerConnectedRef.current
        ) {
          const nativeClient = (playerRef.current as any)?.provider?.getNativeClient?.() as
            | IAgoraRTCClient
            | null;
          if (nativeClient) {
            rtcManager.attachNativeClient(nativeClient, connectKey);
          }
          return;
        }

        await ensureSdkInitialized(
          spatialwalkUrlConfig.appId,
          spatialwalkSettings.environment
        );
        if (cancelled) return;

        let player = playerRef.current;
        if (!player) {
          const avatar = await AvatarManager.shared.load(
            spatialwalkUrlConfig.avatarId
          );
          if (cancelled) return;

          const avatarView = new AvatarView(avatar, containerRef.current);
          avatarViewRef.current = avatarView;

          const provider = new AgoraProvider();
          // Package typings currently miss BaseProvider event methods; runtime is compatible.
          player = new AvatarPlayer(provider as any, avatarView, {
            logLevel: "warning",
          });
          playerRef.current = player;
          playerConnectedRef.current = false;
        }

        if (options.channel && options.appId && options.token && options.userId) {
          const connectConfig = {
            appId: options.appId,
            channel: options.channel,
            token: options.token,
            uid: options.userId,
          };
          if (playerConnectedRef.current) {
            await player.disconnect();
            playerConnectedRef.current = false;
          }
          await player.connect(connectConfig);
          playerConnectedRef.current = true;
          lastConnectKeyRef.current = connectKey;
          const nativeClient = (player as any)?.provider?.getNativeClient?.() as
            | IAgoraRTCClient
            | null;
          if (!nativeClient) {
            throw new Error("Failed to get native Agora client from player provider");
          }
          rtcManager.attachNativeClient(nativeClient, connectKey);
        }
      } catch (error: any) {
        const message =
          error?.message || "Failed to initialize Spatialwalk Avatar.";
        setErrorMessage(message);
        console.error("[spatialwalk] init error:", error);
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    setup();

    return () => {
      cancelled = true;
      // Intentionally avoid disconnect in React cleanup to prevent SDK
      // race ("AvatarView not initialized") during passive unmount.
    };
  }, [
    options.appId,
    options.channel,
    options.token,
    options.userId,
    spatialwalkUrlConfig.appId,
    spatialwalkUrlConfig.avatarId,
    spatialwalkSettings.environment,
  ]);

  return (
    <div
      className={cn(
        "absolute top-0 left-0 h-screen w-screen overflow-hidden rounded-none"
      )}
    >
      <div className="pointer-events-none absolute top-2 right-2 z-30 flex items-center gap-2">
        <Button
          size="icon"
          variant="outline"
          title={showTranscript ? "Hide transcript" : "Show transcript"}
          onClick={() => setShowTranscript((prev) => !prev)}
          className="pointer-events-auto h-10 w-10 rounded-full border border-white/20 bg-black/55 text-white hover:bg-black/70"
        >
          {showTranscript ? (
            <MessagesSquare className="h-5 w-5" />
          ) : (
            <MessagesSquareIcon className="h-5 w-5 opacity-60" />
          )}
          <span className="sr-only">
            {showTranscript ? "Hide transcript" : "Show transcript"}
          </span>
        </Button>
        <AvatarConnectButton className="pointer-events-auto" />
      </div>
      {showTranscript && <AvatarTranscriptOverlay />}

      <div ref={containerRef} className="h-full w-full" />

      {loading && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-black/70 text-white">
          Loading avatar...
        </div>
      )}

      {errorMessage && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-red-500/80 text-white">
          <div>{errorMessage}</div>
        </div>
      )}
    </div>
  );
}
