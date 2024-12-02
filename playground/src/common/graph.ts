import axios from "axios"
import { useCallback, useEffect, useMemo, useState } from "react"
import { useAppDispatch, useAppSelector } from "./hooks"
import {
  fetchGraphDetails,
  initializeGraphData,
  setAddonModules,
  setGraph,
  setGraphList,
  updateGraph,
} from "@/store/reducers/global"
import {
  apiFetchAddonsExtensions,
  apiFetchGraphDetails,
  apiFetchGraphs,
  apiFetchInstalledAddons,
  apiReloadPackage,
  apiSaveProperty,
  apiUpdateGraph,
} from "./request"

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

const useGraphManager = () => {
  const dispatch = useAppDispatch()
  const selectedGraphId = useAppSelector(
    (state) => state.global.selectedGraphId,
  )
  const graphMap = useAppSelector((state) => state.global.graphMap)
  const selectedGraph = graphMap[selectedGraphId]
  const addonModules = useAppSelector((state) => state.global.addonModules)

  // Extract tool modules from addonModules
  const toolModules = useMemo(
    () => addonModules.filter((module) => module.name.includes("tool")
    && module.name !== "vision_analyze_tool_python"
  ),
    [addonModules],
  )

  const initialize = async () => {
    await dispatch(initializeGraphData())
  }

  const fetchDetails = async () => {
    if (selectedGraphId) {
      await dispatch(fetchGraphDetails(selectedGraphId))
    }
  }

  const update = async (graphId: string, updates: Partial<Graph>) => {
    await dispatch(updateGraph({ graphId, updates }))
  }

  const getGraphNodeAddonByName = useCallback(
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

  return {
    initialize,
    fetchDetails,
    update,
    getGraphNodeAddonByName,
    selectedGraph,
    toolModules,
  }
}

export { useGraphManager }
export type { Graph, Node, Connection, Command, Destination }
