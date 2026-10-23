import {
  IAgoraRTCClient,
  IAgoraRTCRemoteUser,
  type ICameraVideoTrack,
  type ILocalVideoTrack,
  type IMicrophoneAudioTrack,
  type IRemoteAudioTrack,
  type IRemoteVideoTrack,
  type NetworkQuality,
  type UID,
} from "agora-rtc-sdk-ng";
import { type IChatItem, ITextItem } from "@/types";

export type ImageProgressPhase = "queued" | "drawing" | "final";

export interface IProgressEvent {
  phase: ImageProgressPhase;
  pct?: number;
  time: number;
}

export interface IRtcUser {
  userId: UID;
  videoTrack?: IRemoteVideoTrack;
  screenTrack?: ILocalVideoTrack;
  audioTrack?: IRemoteAudioTrack;
}

export interface RtcEvents {
  remoteUserChanged: (user: IRtcUser) => void;
  localTracksChanged: (tracks: IUserTracks) => void;
  networkQuality: (quality: NetworkQuality) => void;
  textChanged: (text: IChatItem) => void;
  progressChanged: (progress: IProgressEvent) => void;
}

export interface IUserTracks {
  videoTrack?: ICameraVideoTrack;
  screenTrack?: ILocalVideoTrack;
  audioTrack?: IMicrophoneAudioTrack;
}
