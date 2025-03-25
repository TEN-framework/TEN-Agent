import {
  UID,
  IAgoraRTCRemoteUser,
  IAgoraRTCClient,
  ICameraVideoTrack,
  IMicrophoneAudioTrack,
  NetworkQuality,
  ILocalVideoTrack,
} from "agora-rtc-sdk-ng"
import { IChatItem, ITextItem } from "@/types"

export interface IRtcUser extends IUserTracks {
  userId: UID
}

export interface RtcEvents {
  remoteUserChanged: (user: IAgoraRTCRemoteUser) => void
  localTracksChanged: (tracks: IUserTracks) => void
  networkQuality: (quality: NetworkQuality) => void
  textChanged: (text: IChatItem) => void
}

export interface IUserTracks {
  videoTrack?: ICameraVideoTrack
  screenTrack?: ILocalVideoTrack
  audioTrack?: IMicrophoneAudioTrack
}
