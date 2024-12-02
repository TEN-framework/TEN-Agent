import { genUUID } from "./utils"
import { Language } from "@/types"
import axios from "axios"
import { AddonDef, Connection, Graph, Node } from "./graph"

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
  const { channel, userId, graphName, language, voiceType } = config
  const data = {
    request_id: genUUID(),
    channel_name: channel,
    user_uid: userId,
    graph_name: graphName,
    language,
    voice_type: voiceType
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

export const apiFetchAddonsExtensions = async (): Promise<AddonDef.Module[]> => {
  let resp: any = await axios.get(`/api/dev/v1/addons/extensions`)
  return resp.data.data
}

export const apiCheckCompatibleMessages = async (payload: {
  app: string
  graph: string
  extension_group: string
  extension: string
  msg_type: string
  msg_direction: string
  msg_name: string
}) => {
  let resp: any = await axios.post(`/api/dev/v1/messages/compatible`, payload)
  resp = (resp.data) || {}
  return resp
}

export const apiFetchGraphs = async (): Promise<Graph[]> => {
  let resp: any = await axios.get(`/api/dev/v1/graphs`)
  return resp.data.data.map((graph: any) => ({
    id: graph.name,
    autoStart: graph.auto_start,
    nodes: [],
    connections: [],
  }))
}

export const apiFetchGraphNodes = async (graphId: string): Promise<Node[]> => {
  let resp: any = await axios.get(`/api/dev/v1/graphs/${graphId}/nodes`)
  return resp.data.data.map((node: any) => ({
    name: node.name,
    addon: node.addon,
    extensionGroup: node.extension_group,
    app: node.app,
    property: node.property || {},
  }))
}

export const apiFetchGraphConnections = async (graphId: string): Promise<Connection[]> => {
  let resp: any = await axios.get(`/api/dev/v1/graphs/${graphId}/connections`)
  return resp.data.data.map(
    (connection: any) => ({
      app: connection.app,
      extensionGroup: connection.extension_group,
      extension: connection.extension,
      cmd: connection.cmd?.map((cmd: any) => ({
        name: cmd.name,
        dest: cmd.dest.map((dest: any) => ({
          app: dest.app,
          extensionGroup: dest.extension_group,
          extension: dest.extension,
          msgConversion: dest.msgConversion
            ? {
              type: dest.msgConversion.type,
              rules: dest.msgConversion.rules.map((rule: any) => ({
                path: rule.path,
                conversionMode: rule.conversionMode,
                value: rule.value,
                originalPath: rule.originalPath,
              })),
              keepOriginal: dest.msgConversion.keepOriginal,
            }
            : undefined,
        })),
      })),
      data: connection.data?.map((data: any) => ({
        name: data.name,
        dest: data.dest.map((dest: any) => ({
          app: dest.app,
          extensionGroup: dest.extension_group,
          extension: dest.extension,
          msgConversion: dest.msgConversion
            ? {
              type: dest.msgConversion.type,
              rules: dest.msgConversion.rules.map((rule: any) => ({
                path: rule.path,
                conversionMode: rule.conversionMode,
                value: rule.value,
                originalPath: rule.originalPath,
              })),
              keepOriginal: dest.msgConversion.keepOriginal,
            }
            : undefined,
        })),
      })),
      audioFrame: connection.audio_frame?.map((audioFrame: any) => ({
        name: audioFrame.name,
        dest: audioFrame.dest.map((dest: any) => ({
          app: dest.app,
          extensionGroup: dest.extension_group,
          extension: dest.extension,
          msgConversion: dest.msgConversion
            ? {
              type: dest.msgConversion.type,
              rules: dest.msgConversion.rules.map((rule: any) => ({
                path: rule.path,
                conversionMode: rule.conversionMode,
                value: rule.value,
                originalPath: rule.originalPath,
              })),
              keepOriginal: dest.msgConversion.keepOriginal,
            }
            : undefined,
        })),
      })),
      videoFrame: connection.videoFrame?.map((videoFrame: any) => ({
        name: videoFrame.name,
        dest: videoFrame.dest.map((dest: any) => ({
          app: dest.app,
          extensionGroup: dest.extension_group,
          extension: dest.extension,
          msgConversion: dest.msgConversion
            ? {
              type: dest.msgConversion.type,
              rules: dest.msgConversion.rules.map((rule: any) => ({
                path: rule.path,
                conversionMode: rule.conversionMode,
                value: rule.value,
                originalPath: rule.originalPath,
              })),
              keepOriginal: dest.msgConversion.keepOriginal,
            }
            : undefined,
        })),
      })),
    }),
  )
}

export const apiUpdateGraph = async (graphId: string, updates: Partial<Graph>) => {
  const { autoStart, nodes, connections } = updates
  const payload: any = {}

  // Map autoStart field
  if (autoStart !== undefined) payload.auto_start = autoStart

  // Map nodes to the payload
  if (nodes) {
    payload.nodes = nodes.map((node) => ({
      name: node.name,
      addon: node.addon,
      extension_group: node.extensionGroup,
      app: node.app,
      property: node.property,
    }))
  }

  // Map connections to the payload
  if (connections) {
    payload.connections = connections.map((connection) => ({
      app: connection.app,
      extension_group: connection.extensionGroup,
      extension: connection.extension,
      cmd: connection.cmd?.map((cmd) => ({
        name: cmd.name,
        dest: cmd.dest.map((dest) => ({
          app: dest.app,
          extension_group: dest.extensionGroup,
          extension: dest.extension,
          msgConversion: dest.msgConversion
            ? {
              type: dest.msgConversion.type,
              rules: dest.msgConversion.rules.map((rule) => ({
                path: rule.path,
                conversionMode: rule.conversionMode,
                value: rule.value,
                originalPath: rule.originalPath,
              })),
              keepOriginal: dest.msgConversion.keepOriginal,
            }
            : undefined,
        })),
      })),
      data: connection.data?.map((data) => ({
        name: data.name,
        dest: data.dest.map((dest) => ({
          app: dest.app,
          extension_group: dest.extensionGroup,
          extension: dest.extension,
          msgConversion: dest.msgConversion
            ? {
              type: dest.msgConversion.type,
              rules: dest.msgConversion.rules.map((rule) => ({
                path: rule.path,
                conversionMode: rule.conversionMode,
                value: rule.value,
                originalPath: rule.originalPath,
              })),
              keepOriginal: dest.msgConversion.keepOriginal,
            }
            : undefined,
        })),
      })),
      audio_frame: connection.audioFrame?.map((audioFrame) => ({
        name: audioFrame.name,
        dest: audioFrame.dest.map((dest) => ({
          app: dest.app,
          extension_group: dest.extensionGroup,
          extension: dest.extension,
          msgConversion: dest.msgConversion
            ? {
              type: dest.msgConversion.type,
              rules: dest.msgConversion.rules.map((rule) => ({
                path: rule.path,
                conversionMode: rule.conversionMode,
                value: rule.value,
                originalPath: rule.originalPath,
              })),
              keepOriginal: dest.msgConversion.keepOriginal,
            }
            : undefined,
        })),
      })),
      video_frame: connection.videoFrame?.map((videoFrame) => ({
        name: videoFrame.name,
        dest: videoFrame.dest.map((dest) => ({
          app: dest.app,
          extension_group: dest.extensionGroup,
          extension: dest.extension,
          msgConversion: dest.msgConversion
            ? {
              type: dest.msgConversion.type,
              rules: dest.msgConversion.rules.map((rule) => ({
                path: rule.path,
                conversionMode: rule.conversionMode,
                value: rule.value,
                originalPath: rule.originalPath,
              })),
              keepOriginal: dest.msgConversion.keepOriginal,
            }
            : undefined,
        })),
      })),
    }))
  }

  let resp: any = await axios.put(`/api/dev/v1/graphs/${graphId}`, payload)
  resp = (resp.data) || {}
  return resp
}

export const apiFetchAddonModulesDefaultProperties = async (): Promise<
  Record<string, Partial<AddonDef.Module>>
> => {
  let resp: any = await axios.get(`/api/dev/v1/addons/default-properties`)
  const properties = resp.data.data
  const result: Record<string, Partial<AddonDef.Module>> = {}
  for (const property of properties) {
    result[property.addon] = property.property
  }
  return result
}

export const apiSaveProperty = async () => {
  let resp: any = await axios.put(`/api/dev/v1/property`)
  resp = (resp.data) || {}
  return resp
}

export const apiReloadPackage = async () => {
  let resp: any = await axios.post(`/api/dev/v1/packages/reload`)
  resp = (resp.data) || {}
  return resp
}


export const apiFetchInstalledAddons = async (): Promise<AddonDef.Module[]> => {
  const [modules, defaultProperties] = await Promise.all([
    apiFetchAddonsExtensions(),
    apiFetchAddonModulesDefaultProperties(),
  ])
  return modules.map((module: any) => ({
    name: module.name,
    defaultProperty: defaultProperties[module.name],
    api: module.api,
  }))
}

export const apiFetchGraphDetails = async (graphId: string): Promise<Graph> => {
  const [nodes, connections] = await Promise.all([
    apiFetchGraphNodes(graphId),
    apiFetchGraphConnections(graphId),
  ])
  return {
    id: graphId,
    autoStart: true,
    nodes,
    connections,
  }
}