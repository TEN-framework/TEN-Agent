declare module 'agora-rtm' {
  export interface RTMMessage {
    text: string;
    messageType?: 'TEXT' | 'RAW';
    rawMessage?: Uint8Array;
  }

  export interface RTMMessageEvent {
    message: RTMMessage;
    publisher: string;
  }

  export interface RTMPresenceEvent {
    eventType: 'SNAPSHOT' | string;
    type?: string;
    publisher: string;
  }

  export class RTM {
    constructor(appId: string, userId: string);
    addEventListener(event: 'message', callback: (event: RTMMessageEvent) => void): void;
    addEventListener(event: 'presence', callback: (event: RTMPresenceEvent) => void): void;
    addEventListener(event: 'status', callback: (event: any) => void): void;
    login(params: { token: string }): Promise<void>;
    logout(): Promise<void>;
    subscribe(channel: string): Promise<void>;
    publish(channel: string, message: string): Promise<void>;
  }

  const AgoraRTM: {
    RTM: typeof RTM;
  };

  export default AgoraRTM;
} 