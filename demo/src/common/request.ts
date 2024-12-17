import { genUUID } from "./utils"
import { Language } from "@/types"
import axios from "axios"

export interface StartRequestConfig {
  channel: string
  userId: number
  graphName: string
  language: Language
  voiceType: "male" | "female"
  prompt?: string
  greeting?: string
  coze_token?: string
  coze_bot_id?: string
  coze_base_url?: string
  dify_api_key?: string
}

interface GenAgoraDataConfig {
  userId: string | number
  channel: string
}

export const apiGenAgoraData = async (config: GenAgoraDataConfig) => {
  // the request will be rewrite at next.config.mjs to send to $AGENT_SERVER_URL
  const url = `/api/token/generate`
  const { userId, channel } = config
  const data = {
    request_id: genUUID(),
    uid: userId,
    channel_name: channel,
  }
  let resp: any = await axios.post(url, data)
  resp = resp.data || {}
  return resp
}

export const apiStartService = async (
  config: StartRequestConfig,
): Promise<any> => {
  // look at app/api/agents/start/route.tsx for the server-side implementation
  const url = `/api/agents/start`
  const {
    channel,
    userId,
    graphName,
    language,
    voiceType,
    greeting,
    prompt,
    coze_token,
    coze_bot_id,
    coze_base_url,
    dify_api_key,
  } = config
  const data = {
    request_id: genUUID(),
    channel_name: channel,
    user_uid: userId,
    graph_name: graphName,
    language,
    voice_type: voiceType,
    greeting: greeting ?? undefined,
    prompt: prompt ?? undefined,
    coze_token: coze_token ?? undefined,
    coze_bot_id: coze_bot_id ?? undefined,
    coze_base_url: coze_base_url ?? undefined,
    dify_api_key: dify_api_key ?? undefined
  }
  let resp: any = await axios.post(url, data)
  resp = resp.data || {}
  return resp
}

export const apiStopService = async (channel: string) => {
  // the request will be rewrite at middleware.tsx to send to $AGENT_SERVER_URL
  const url = `/api/agents/stop`
  const data = {
    request_id: genUUID(),
    channel_name: channel,
  }
  let resp: any = await axios.post(url, data)
  resp = resp.data || {}
  return resp
}

export const apiGetDocumentList = async () => {
  // the request will be rewrite at middleware.tsx to send to $AGENT_SERVER_URL
  const url = `/api/vector/document/preset/list`
  let resp: any = await axios.get(url)
  resp = resp.data || {}
  if (resp.code !== "0") {
    throw new Error(resp.msg)
  }
  return resp
}

export const apiUpdateDocument = async (options: {
  channel: string
  collection: string
  fileName: string
}) => {
  // the request will be rewrite at middleware.tsx to send to $AGENT_SERVER_URL
  const url = `/api/vector/document/update`
  const { channel, collection, fileName } = options
  const data = {
    request_id: genUUID(),
    channel_name: channel,
    collection: collection,
    file_name: fileName,
  }
  let resp: any = await axios.post(url, data)
  resp = resp.data || {}
  return resp
}

// ping/pong
export const apiPing = async (channel: string) => {
  // the request will be rewrite at middleware.tsx to send to $AGENT_SERVER_URL
  const url = `/api/agents/ping`
  const data = {
    request_id: genUUID(),
    channel_name: channel,
  }
  let resp: any = await axios.post(url, data)
  resp = resp.data || {}
  return resp
}
