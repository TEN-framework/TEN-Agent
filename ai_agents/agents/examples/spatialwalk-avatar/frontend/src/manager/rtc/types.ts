import {
  type IMicrophoneAudioTrack,
  type IRemoteAudioTrack,
  type IRemoteVideoTrack,
  type NetworkQuality,
  type UID,
} from "agora-rtc-sdk-ng";
import { type IChatItem } from "@/types";

export interface IRtcUser {
  userId: UID;
  videoTrack?: IRemoteVideoTrack;
  audioTrack?: IRemoteAudioTrack;
}

export interface RtcEvents {
  remoteUserChanged: (user: IRtcUser) => void;
  localTracksChanged: (tracks: IUserTracks) => void;
  networkQuality: (quality: NetworkQuality) => void;
  textChanged: (text: IChatItem) => void;
  uiAction: (payload: IUiActionPayload) => void;
}

export interface IUserTracks {
  audioTrack?: IMicrophoneAudioTrack;
}

export interface IUiActionPayload {
  action: string;
  data: Record<string, any>;
}
