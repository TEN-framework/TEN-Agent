import { genUUID } from "./utils"
import { Language } from "@/types"
import axios from "axios"

interface StartRequestConfig {
  channel: string
  userId: number,
  graphName: string,
  language: Language,
  voiceType: "male" | "female"
  properties: Record<string, any>
}

interface GenAgoraDataConfig {
  userId: string | number
  channel: string
}

export const apiGenAgoraData = async (config: GenAgoraDataConfig) => {
  // the request will be rewrite at middleware.tsx to send to $AGENT_SERVER_URL
  const url = `/api/token/generate`
  const { userId, channel } = config
  const data = {
    request_id: genUUID(),
    uid: userId,
    channel_name: channel
  }
  let resp: any = await axios.post(url, data)
  resp = (resp.data) || {}
  return resp
}

export const apiStartService = async (config: StartRequestConfig): Promise<any> => {
  // look at app/apis/route.tsx for the server-side implementation
  const url = `/api/agents/start`
  const { channel, userId, graphName, language, voiceType, properties } = config


  // add here for mobile or desktop
  const urlParams = new URLSearchParams(window.location.search);
  const system_message = urlParams.get('system_message');
  const greeting = urlParams.get('greeting');
  const voice = urlParams.get('voice');

  var newProperties = { ...(properties || {}) };
  newProperties.openai_v2v_python = { ...(newProperties.openai_v2v_python || {}) };

  const params = { system_message, greeting, voice };
  for (const [key, value] of Object.entries(params)) {
    if (value) {
      newProperties.openai_v2v_python[key] = value;
    }
  }

  console.error('newProperties', newProperties);


  console.error('properties', properties);

  const data = {
    request_id: genUUID(),
    channel_name: channel,
    user_uid: userId,
    graph_name: graphName,
    language,
    voice_type: voiceType,
    properties: newProperties,
  }
  let resp: any = await axios.post(url, data)
  resp = (resp.data) || {}
  return resp
}

export const apiStopService = async (channel: string) => {
  // the request will be rewrite at middleware.tsx to send to $AGENT_SERVER_URL
  const url = `/api/agents/stop`
  const data = {
    request_id: genUUID(),
    channel_name: channel
  }
  let resp: any = await axios.post(url, data)
  resp = (resp.data) || {}
  return resp
}

export const apiGetDocumentList = async () => {
  // the request will be rewrite at middleware.tsx to send to $AGENT_SERVER_URL
  const url = `/api/vector/document/preset/list`
  let resp: any = await axios.get(url)
  resp = (resp.data) || {}
  if (resp.code !== "0") {
    throw new Error(resp.msg)
  }
  return resp
}

export const apiUpdateDocument = async (options: { channel: string, collection: string, fileName: string }) => {
  // the request will be rewrite at middleware.tsx to send to $AGENT_SERVER_URL
  const url = `/api/vector/document/update`
  const { channel, collection, fileName } = options
  const data = {
    request_id: genUUID(),
    channel_name: channel,
    collection: collection,
    file_name: fileName
  }
  let resp: any = await axios.post(url, data)
  resp = (resp.data) || {}
  return resp
}


// ping/pong 
export const apiPing = async (channel: string) => {
  // the request will be rewrite at middleware.tsx to send to $AGENT_SERVER_URL
  const url = `/api/agents/ping`
  const data = {
    request_id: genUUID(),
    channel_name: channel
  }
  let resp: any = await axios.post(url, data)
  resp = (resp.data) || {}
  return resp
}

export const apiGetGraphs = async () => {
  // the request will be rewrite at middleware.tsx to send to $AGENT_SERVER_URL
  const url = `/api/dev/v1/graphs`
  let resp: any = await axios.get(url)
  resp = (resp.data) || {}
  return resp
}

export const apiGetExtensionMetadata = async () => {
  // the request will be rewrite at middleware.tsx to send to $AGENT_SERVER_URL
  const url = `/api/dev/v1/addons/extensions`
  let resp: any = await axios.get(url)
  resp = (resp.data) || {}
  return resp
}

export const apiGetNodes = async (graphName: string) => {
  // the request will be rewrite at middleware.tsx to send to $AGENT_SERVER_URL
  const url = `/api/dev/v1/graphs/${graphName}/nodes`
  let resp: any = await axios.get(url)
  resp = (resp.data) || {}
  return resp
}


export const apiReloadGraph = async (): Promise<any> => {
  // look at app/apis/route.tsx for the server-side implementation
  const url = `/api/dev/v1/packages/reload`
  let resp: any = await axios.post(url)
  resp = (resp.data) || {}
  return resp
}