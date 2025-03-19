import axios from 'axios';
import { genUUID } from './utils';

export interface StartRequestConfig {
  channel: string;
  userId: number;
  graphName: string;
  language: string;
  voiceType: 'male' | 'female';
}

export interface GenAgoraDataConfig {
  userId: string | number;
  channel: string;
}

export const apiGenAgoraData = async (config: GenAgoraDataConfig) => {
  const url = `/api/token/generate`;
  const { userId, channel } = config;
  const data = {
    request_id: genUUID(),
    uid: Number(userId),
    channel_name: channel
  };

  const resp = await axios.post(url, data);
  return resp.data || {};
};

export const apiStartService = async (config: StartRequestConfig) => {
  const url = `/api/agents/start`;
  const { channel, userId, graphName, language, voiceType } = config;
  const data = {
    request_id: genUUID(),
    channel_name: channel,
    user_uid: userId,
    graph_name: graphName,
    language,
    voice_type: voiceType
  };

  const resp = await axios.post(url, data);
  return resp.data || {};
};

export const apiStopService = async (channel: string) => {
  const url = `/api/agents/stop`;
  const data = {
    request_id: genUUID(),
    channel_name: channel
  };

  const resp = await axios.post(url, data);
  return resp.data || {};
};

export const apiPing = async (channel: string) => {
  const url = `/api/agents/ping`;
  const data = {
    request_id: genUUID(),
    channel_name: channel
  };

  const resp = await axios.post(url, data);
  return resp.data || {};
}; 