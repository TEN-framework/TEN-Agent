"use client";

import type { RTMClient } from "agora-rtm";
import { type IRTMTextItem } from "@/types";
import { AGEventEmitter } from "../events";

export interface IRtmEvents {
  rtmMessage: (text: IRTMTextItem) => void;
}

export type TRTMMessageEvent = {
  channelType: "STREAM" | "MESSAGE" | "USER";
  channelName: string;
  topicName?: string;
  messageType: "STRING" | "BINARY";
  customType?: string;
  publisher: string;
  message: string | Uint8Array;
  timestamp: number;
};

let cachedAgoraRTM: any = null;
const getAgoraRTM = async () => {
  if (cachedAgoraRTM) {
    return cachedAgoraRTM;
  }
  const mod = await import("agora-rtm");
  cachedAgoraRTM = mod.default ?? mod;
  return cachedAgoraRTM;
};

export class RtmManager extends AGEventEmitter<IRtmEvents> {
  private _joined: boolean;
  _client: RTMClient | null;
  channel = "";
  userId = 0;
  appId = "";
  token = "";
  private _boundHandleRtmMessage: ((e: TRTMMessageEvent) => Promise<void>) | null =
    null;
  private _boundHandleRtmPresence: ((e: any) => Promise<void>) | null = null;

  constructor() {
    super();
    this._joined = false;
    this._client = null;
    this._boundHandleRtmMessage = this.handleRtmMessage.bind(this);
    this._boundHandleRtmPresence = this.handleRtmPresence.bind(this);
  }

  async init({
    channel,
    userId,
    appId,
    token,
  }: {
    channel: string;
    userId: number;
    appId: string;
    token: string;
  }) {
    if (this._joined) {
      return;
    }

    this.channel = channel;
    this.userId = userId;
    this.appId = appId;
    this.token = token;

    const AgoraRTM = await getAgoraRTM();
    const rtm = new AgoraRTM.RTM(appId, String(userId), {
      logLevel: "debug",
    });

    await rtm.login({ token });
    await rtm.subscribe(channel, {
      withMessage: true,
      withPresence: false,
      beQuiet: false,
      withMetadata: false,
      withLock: false,
    });

    this._joined = true;
    this._client = rtm;
    this._listenRtmEvents();
  }

  private _listenRtmEvents() {
    if (!this._client) {
      return;
    }
    this._client.addEventListener("message", this._boundHandleRtmMessage!);
    this._client.addEventListener("presence", this._boundHandleRtmPresence!);
  }

  async handleRtmMessage(e: TRTMMessageEvent) {
    const { message, messageType } = e;

    if (messageType === "STRING") {
      const msg: IRTMTextItem = JSON.parse(message as string);
      this.emit("rtmMessage", msg);
      return;
    }

    const decoder = new TextDecoder("utf-8");
    const decodedMessage = decoder.decode(message as Uint8Array);
    const msg: IRTMTextItem = JSON.parse(decodedMessage);
    this.emit("rtmMessage", msg);
  }

  async handleRtmPresence(_e: any) {
    // presence events are currently not used by UI
  }

  async sendText(text: string) {
    const msg: IRTMTextItem = {
      is_final: true,
      data_type: "input_text",
      role: "user",
      text_ts: Date.now(),
      text,
      stream_id: this.userId,
    };
    await this._client?.publish(this.channel, JSON.stringify(msg));
    // Keep optimistic local echo behavior for existing UX.
    this.emit("rtmMessage", msg);
  }

  async destroy() {
    if (!this._client) {
      this._joined = false;
      return;
    }

    this._client.removeEventListener("message", this._boundHandleRtmMessage!);
    this._client.removeEventListener("presence", this._boundHandleRtmPresence!);
    await this._client.unsubscribe(this.channel);
    await this._client.logout();

    this._client = null;
    this._joined = false;
  }
}

export const rtmManager = new RtmManager();
