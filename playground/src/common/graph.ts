import axios from "axios"
import { useCallback, useEffect, useState } from "react"
import { useAppDispatch, useAppSelector } from "./hooks"
import {
  setAddonModules,
  setGraph,
  setGraphList,
} from "@/store/reducers/global"
import path from "path"
import { deepMerge } from "./utils"

export namespace AddonDef {
  export type AttributeType =
    | "string"
    | "bool"
    | "int32"
    | "int64"
    | "Uint32"
    | "Uint64"
    | "float64"
    | "array"
    | "buf"

  export type Attribute = {
    type: AttributeType
  }

  export type PropertyDefinition = {
    name: string
    attributes: Attribute
  }

  export type Command = {
    name: string
    property?: PropertyDefinition[]
    required?: string[]
    result?: {
      property: PropertyDefinition[]
      required?: string[]
    }
  }

  export type ApiEndpoint = {
    name: string
    property?: PropertyDefinition[]
  }

  export type Api = {
    property?: Record<string, Attribute>
    cmd_in?: Command[]
    cmd_out?: Command[]
    data_in?: ApiEndpoint[]
    data_out?: ApiEndpoint[]
    audio_frame_in?: ApiEndpoint[]
    audio_frame_out?: ApiEndpoint[]
    video_frame_in?: ApiEndpoint[]
    video_frame_out?: ApiEndpoint[]
  }

  export type Module = {
    name: string
    defaultProperty: Property
    api: Api
  }
}

type Property = {
  [key: string]: any
}

type Node = {
  name: string
  addon: string
  extensionGroup: string
  app: string
  property?: Property
}
type Command = {
  name: string // Command name
  dest: Array<Destination> // Destination connections
}

type Data = {
  name: string // Data type name
  dest: Array<Destination> // Destination connections
}

type AudioFrame = {
  name: string // Audio frame type name
  dest: Array<Destination> // Destination connections
}

type VideoFrame = {
  name: string // Video frame type name
  dest: Array<Destination> // Destination connections
}

type MsgConversion = {
  type: string // Type of message conversion
  rules: Array<{
    path: string // Path in the data structure
    conversionMode: string // Mode of conversion (e.g., "replace", "append")
    value?: string // Optional value for the conversion
    originalPath?: string // Optional original path for mapping
  }>
  keepOriginal?: boolean // Whether to keep the original data
}

type Destination = {
  app: string // Application identifier
  extensionGroup: string // Extension group name
  extension: string // Extension name
  msgConversion?: MsgConversion // Optional message conversion rules
}

type Connection = {
  app: string // Application identifier
  extensionGroup: string // Extension group name
  extension: string // Extension name
  cmd?: Array<Command> // Optional command connections
  data?: Array<Data> // Optional data connections
  audioFrame?: Array<AudioFrame> // Optional audio frame connections
  videoFrame?: Array<VideoFrame> // Optional video frame connections
}

type Graph = {
  id: string
  autoStart: boolean
  nodes: Node[]
  connections: Connection[]
}

const baseUrl = "/api/dev/v1"

const useGraphManager = () => {
  const dispatch = useAppDispatch()
  const selectedGraphId = useAppSelector(
    (state) => state.global.selectedGraphId,
  )
  const graphMap = useAppSelector(
    (state) => state.global.graphMap,
  )
  const selectedGraph = graphMap[selectedGraphId]
  const addonModules = useAppSelector((state) => state.global.addonModules)

  useEffect(() => {
    if (selectedGraphId) {
      fetchGraphDetails(selectedGraphId).then((graph) => {
        dispatch(setGraph(graph))
      })
    }
  }, [selectedGraphId])

  const initializeGraphData = useCallback(async () => {
    await reload()
    const fetchedGraphs = await fetchGraphs()
    const modules = await fetchInstalledAddons()
    dispatch(setGraphList(fetchedGraphs.map((graph) => graph.id)))
    dispatch(setAddonModules(modules))
  }, [baseUrl])

  const getGraphModuleAddonValueByName = useCallback(
    (nodeName: string) => {
      if (!selectedGraph) {
        return null
      }
      const node = selectedGraph.nodes.find((node) => node.name === nodeName)
      if (!node) {
        return null
      }
      return node
    },
    [selectedGraph],
  )

  const fetchInstalledAddons = useCallback(async (): Promise<
    AddonDef.Module[]
  > => {
    const response = await axios.get(`${baseUrl}/addons/extensions`)
    const modules = response.data.data
    const defaultProperties = await fetchAddonModuleProperties()
    return modules.map((module: any) => ({
      name: module.name,
      defaultProperty: defaultProperties[module.name],
      api: module.api,
    }))
  }, [baseUrl])

  const fetchGraphs = useCallback(async (): Promise<Graph[]> => {
    const response = await axios.get(`${baseUrl}/graphs`)
    return response.data.data.map((graph: any) => ({
      id: graph.name,
      autoStart: graph.auto_start,
      nodes: [],
      connections: [],
    }))
  }, [baseUrl])

  const fetchGraphDetails = useCallback(
    async (graphId: string): Promise<Graph> => {
      const nodesResponse = await axios.get(
        `${baseUrl}/graphs/${graphId}/nodes`,
      )
      const connectionsResponse = await axios.get(
        `${baseUrl}/graphs/${graphId}/connections`,
      )

      // Map nodes to their refined structure
      const nodes: Node[] = nodesResponse.data.data.map((node: any) => ({
        name: node.name,
        addon: node.addon,
        extensionGroup: node.extension_group,
        app: node.app,
        property: node.property || {},
      }))

      // Map connections to the refined structure
      const connections: Connection[] = connectionsResponse.data.data.map(
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

      return {
        id: graphId,
        autoStart: true,
        nodes,
        connections,
      }
    },
    [baseUrl],
  )

  const updateGraph = useCallback(
    async (graphId: string, updates: Partial<Graph>): Promise<void> => {
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

      // Send updated data to the server
      await axios.put(`${baseUrl}/graphs/${graphId}`, payload)

      // Save additional properties if needed
      await saveProperty()

      // Update the local state with the latest graph details
      const updatedGraph = await fetchGraphDetails(graphId)
      dispatch(setGraph(updatedGraph))
    },
    [baseUrl],
  )

  const getCompatibleMessages = useCallback(
    async (payload: {
      app: string
      graph: string
      extensionGroup: string
      extension: string
      msgType: string
      msgDirection: string
      msgName: string
    }): Promise<any[]> => {
      const response = await axios.post(
        `${baseUrl}/messages/compatible`,
        payload,
      )
      return response.data
    },
    [baseUrl],
  )

  const saveProperty = useCallback(async (): Promise<void> => {
    await axios.put(`${baseUrl}/property`)
  }, [baseUrl])

  const fetchAddonModuleProperties = useCallback(async (): Promise<
    Record<string, Partial<AddonDef.Module>>
  > => {
    const response = await axios.get(`${baseUrl}/addons/default-properties`)
    const properties = response.data.data
    const result: Record<string, Partial<AddonDef.Module>> = {}
    for (const property of properties) {
      result[property.addon] = property.property
    }
    return result
  }, [baseUrl])

  const reload = useCallback(async (): Promise<any> => {
    const response = await axios.post(`${baseUrl}/packages/reload`)
    return response.data
  }, [baseUrl])

  return {
    initializeGraphData,
    fetchInstalledAddons,
    fetchGraphs,
    fetchGraphDetails,
    updateGraph,
    getCompatibleMessages,
    saveProperty,
    fetchAddonModuleProperties,
    reload,
    getModuleAddonValueByName: getGraphModuleAddonValueByName,
    selectedGraph,
  }
}

export { useGraphManager }
export type { Graph, Node, Connection, Command }
