import { 
  ICameraVideoTrack, 
  ILocalVideoTrack, 
  IMicrophoneAudioTrack, 
  IRemoteAudioTrack, 
  IRemoteVideoTrack 
} from 'agora-rtc-sdk-ng';
import { EMessageDataType, EMessageType } from '@/types';

export interface IUserTracks {
  videoTrack?: ICameraVideoTrack;
  audioTrack?: IMicrophoneAudioTrack;
  screenTrack?: ILocalVideoTrack;
}

export interface IRtcUser {
  userId: string | number;
  audioTrack?: IRemoteAudioTrack;
  videoTrack?: IRemoteVideoTrack;
}

export interface INetworkQuality {
  downlinkNetworkQuality: number;
  uplinkNetworkQuality: number;
}

export interface IChatItem {
  type: EMessageType;
  time: number;
  text: string;
  data_type: EMessageDataType;
  userId: string | number;
  isFinal: boolean;
}

export interface RtcEvents {
  localTracksChanged: IUserTracks;
  remoteUserChanged: IRtcUser;
  networkQuality: INetworkQuality;
  textChanged: IChatItem;
} 