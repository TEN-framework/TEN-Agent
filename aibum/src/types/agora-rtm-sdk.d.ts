declare module 'agora-rtm-sdk' {
  export interface RtmMessage {
    text: string;
    messageType?: 'TEXT' | 'RAW';
    rawMessage?: Uint8Array;
  }

  export interface RtmChannel {
    join(): Promise<void>;
    leave(): Promise<void>;
    on(event: 'ChannelMessage', callback: (message: RtmMessage, memberId: string) => void): void;
    off(event: 'ChannelMessage', callback: (message: RtmMessage, memberId: string) => void): void;
  }

  export interface RtmClient {
    login(options: { uid: string; token: string }): Promise<void>;
    logout(): Promise<void>;
    createChannel(channelId: string): RtmChannel;
    on(event: 'MessageFromPeer', callback: (message: RtmMessage, peerId: string) => void): void;
    on(event: 'ConnectionStateChanged', callback: (newState: string, reason: string) => void): void;
    off(event: 'MessageFromPeer', callback: (message: RtmMessage, peerId: string) => void): void;
    off(event: 'ConnectionStateChanged', callback: (newState: string, reason: string) => void): void;
  }

  interface AgoraRTM {
    createInstance(appId: string): RtmClient;
  }

  const AgoraRTM: AgoraRTM;
  export default AgoraRTM;
} 