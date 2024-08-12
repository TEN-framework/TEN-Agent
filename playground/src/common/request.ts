import { REQUEST_URL } from "./constant"
import { genUUID } from "./utils"

interface StartRequestConfig {
  channel: string
  userId: number,
  language: string
  voiceType: string
  graphName: string | null
}

interface GenAgoraDataConfig {
  userId: string | number
  channel: string
}

export const apiGenAgoraData = async (config: GenAgoraDataConfig) => {
  const url = `${REQUEST_URL}/token/generate`
  const { userId, channel } = config
  const data = {
    request_id: genUUID(),
    uid: userId,
    channel_name: channel
  }
  let resp: any = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  })
  resp = (await resp.json()) || {}
  return resp
}

export const apiStartService = async (config: StartRequestConfig): Promise<any> => {
  const url = `${REQUEST_URL}/start`
  const { language, channel, userId, voiceType, graphName } = config
  const data = {
    request_id: genUUID(),
    agora_asr_language: language,
    channel_name: channel,
    openai_proxy_url: "",
    remote_stream_id: userId,
    voice_type: voiceType,
    graph_name: graphName
  }
  let resp: any = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  })
  resp = (await resp.json()) || {}
  return resp
}

export const apiStopService = async (channel: string) => {
  const url = `${REQUEST_URL}/stop`
  const data = {
    request_id: genUUID(),
    channel_name: channel
  }
  let resp = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  })
  resp = (await resp.json()) || {}
  return resp
}

// ping/pong 
export const apiPing = async (channel: string) => {
  const url = `${REQUEST_URL}/ping`
  const data = {
    request_id: genUUID(),
    channel_name: channel
  }
  let resp = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  })
  resp = (await resp.json()) || {}
  return resp
}
