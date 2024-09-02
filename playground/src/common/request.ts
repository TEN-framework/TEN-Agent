import { AnyObject } from "antd/es/_util/type"
import { REQUEST_URL } from "./constant"
import { genUUID } from "./utils"
import { Language } from "@/types"

interface StartRequestConfig {
  channel: string
  userId: number,
  graphName: string,
  language: Language,
  voiceType: "male" | "female"
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
  // look at app/api/agents/start/route.tsx for the server-side implementation
  const url = `/api/agents/start`
  const { channel, userId, graphName, language, voiceType } = config
  const data = {
    request_id: genUUID(),
    channel_name: channel,
    user_uid: userId,
    graph_name: graphName,
    language,
    voice_type: voiceType
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
  // look at app/api/agents/stop/route.tsx for the server-side implementation
  const url = `/api/agents/stop`
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

export const apiGetDocumentList = async () => {
  const url = `${REQUEST_URL}/vector/document/preset/list`
  let resp: any = await fetch(url, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
  })
  resp = (await resp.json()) || {}
  if (resp.code !== "0") {
    throw new Error(resp.msg)
  }
  return resp
}

export const apiUpdateDocument = async (options: { channel: string, collection: string, fileName: string }) => {
  const url = `${REQUEST_URL}/vector/document/update`
  const { channel, collection, fileName } = options
  const data = {
    request_id: genUUID(),
    channel_name: channel,
    collection: collection,
    file_name: fileName
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
