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

enum GraphConnProtocol {
  CMD = "cmd",
  DATA = "data",
  AUDIO_FRAME = "audioFrame",
  VIDEO_FRAME = "videoFrame",
}

class GraphEditor {
  private static sharedApp: string = "localhost"

  /**
   * Set a shared app value.
   */
  static setApp(app: string): void {
    GraphEditor.sharedApp = app
  }

  /**
   * Add a node to the graph
   */
  static addNode(
    graph: Graph,
    addon: string,
    name: string,
    group: string = "default",
    properties: Record<string, any> = {},
  ): Node {
    if (graph.nodes.some((node) => node.name === name)) {
      throw new Error(
        `Node with name "${name}" already exists in graph "${graph.id}".`,
      )
    }

    const node = {
      name,
      addon,
      extensionGroup: group,
      app: GraphEditor.sharedApp,
      property: properties,
    }

    graph.nodes.push(node)
    return node
  }

  /**
   * Remove a node from the graph
   */
  static removeNode(graph: Graph, nodeName: string): void {
    const nodeIndex = graph.nodes.findIndex((node) => node.name === nodeName)
    if (nodeIndex === -1) {
      throw new Error(`Node "${nodeName}" not found in graph "${graph.id}".`)
    }
    graph.nodes.splice(nodeIndex, 1)
  }

  /**
   * Update node properties
   */
  static updateNode(
    graph: Graph,
    nodeName: string,
    properties: Record<string, any>,
  ): void {
    const node = graph.nodes.find((node) => node.name === nodeName)
    if (!node) {
      throw new Error(`Node "${nodeName}" not found in graph "${graph.id}".`)
    }

    // Update properties (remove property if value is empty)
    node.property = {
      ...node.property,
      ...Object.fromEntries(
        Object.entries(properties).filter(([_, value]) => value !== ""),
      ),
    }
  }

  static updateNodeProperty(
    graph: Graph,
    nodeName: string,
    properties: Record<string, any>,
  ): boolean {
    const node = this.findNode(graph, nodeName)
    if (!node) return false

    node.property = {
      ...node.property,
      ...Object.fromEntries(
        Object.entries(properties).filter(([_, value]) => value !== ""),
      ),
    }

    return true
  }

  static removeNodeProperties(
    graph: Graph,
    nodeName: string,
    properties: string[],
  ): boolean {
    const node = this.findNode(graph, nodeName)
    if (!node) return false

    properties.forEach((prop) => {
      if (node.property) delete node.property[prop]
    })

    return true
  }

  /**
   * Add a connection to the graph across all protocols (cmd, data, audioFrame, videoFrame)
   */
  static addConnection(
    graph: Graph,
    source: string,
    destination: string,
    protocolLabel: GraphConnProtocol,
    protocolName: string, // Name for the protocol object
  ): void {
    // Find the source connection in the graph
    let connection = graph.connections.find(
      (conn) =>
        conn.extensionGroup === source.split(".")[0] &&
        conn.extension === source.split(".")[1],
    )

    if (!connection) {
      // If no connection exists, create a new one
      connection = {
        app: GraphEditor.sharedApp,
        extensionGroup: source.split(".")[0],
        extension: source.split(".")[1],
      }
      graph.connections.push(connection)
    }

    // Handle protocol-specific addition
    const protocolField = protocolLabel.toLowerCase() as keyof Connection
    if (!connection[protocolField]) {
      connection[protocolField] = [] as any
    }

    const protocolArray = connection[protocolField] as Array<
      Command | Data | AudioFrame | VideoFrame
    >

    // Check if the protocol object exists
    let protocolObject = protocolArray.find(
      (item) => item.name === protocolName,
    )
    if (!protocolObject) {
      protocolObject = {
        name: protocolName,
        dest: [],
      }
      protocolArray.push(protocolObject)
    }

    // Check if the destination already exists
    if (
      protocolObject.dest.some(
        (dest) => dest.extension === destination.split(".")[1],
      )
    ) {
      throw new Error(
        `Destination "${destination}" already exists in protocol "${protocolLabel}" with name "${protocolName}".`,
      )
    }

    // Add the destination
    protocolObject.dest.push({
      app: GraphEditor.sharedApp,
      extensionGroup: destination.split(".")[0],
      extension: destination.split(".")[1],
    })
  }
  static addOrUpdateConnection(
    graph: Graph,
    source: string,
    destination: string,
    protocolLabel: GraphConnProtocol,
    protocolName: string, // Explicit name of the protocol object
  ): void {
    const [srcGroup, srcExtension] = source.split(".")
    let connection = this.findConnection(graph, srcGroup, srcExtension)

    if (connection) {
      // Add or update destination in the existing connection
      const protocolField = protocolLabel.toLowerCase() as keyof Connection
      if (!connection[protocolField]) {
        connection[protocolField] = [] as any
      }

      const protocolArray = connection[protocolField] as Array<
        Command | Data | AudioFrame | VideoFrame
      >

      // Find the protocol object by name
      let protocolObject = protocolArray.find(
        (item) => item.name === protocolName,
      )
      if (!protocolObject) {
        // Create a new protocol object if it doesn't exist
        protocolObject = {
          name: protocolName,
          dest: [],
        }
        protocolArray.push(protocolObject)
      }

      // Check if the destination already exists
      if (
        !protocolObject.dest.some(
          (dest) => dest.extension === destination.split(".")[1],
        )
      ) {
        // Add the new destination
        protocolObject.dest.push({
          app: GraphEditor.sharedApp,
          extensionGroup: destination.split(".")[0],
          extension: destination.split(".")[1],
        })
      }
    } else {
      // Add a new connection if none exists
      this.addConnection(
        graph,
        source,
        destination,
        protocolLabel,
        protocolName,
      )
    }
  }
  /**
   * Remove a connection from the graph across all protocols (cmd, data, audioFrame, videoFrame)
   */
  static removeConnection(
    graph: Graph,
    source: string,
    destination?: string,
    protocolLabel?: GraphConnProtocol,
    protocolName?: string, // Optional name of the protocol object
  ): void {
    // Find the source connection in the graph
    const connectionIndex = graph.connections.findIndex(
      (conn) =>
        conn.extensionGroup === source.split(".")[0] &&
        conn.extension === source.split(".")[1],
    )

    if (connectionIndex === -1) {
      throw new Error(`Source "${source}" not found in the graph.`)
    }

    const connection = graph.connections[connectionIndex]

    // If protocolLabel is provided, handle protocol-specific removal
    if (protocolLabel) {
      const protocolField = protocolLabel.toLowerCase() as keyof Connection
      const protocolArray = connection[protocolField] as Array<
        Command | Data | AudioFrame | VideoFrame
      >

      if (!protocolArray) {
        throw new Error(
          `Protocol "${protocolLabel}" does not exist for source "${source}".`,
        )
      }

      const protocolObjectIndex = protocolArray.findIndex(
        (item) => item.name === protocolName,
      )

      if (protocolObjectIndex === -1) {
        throw new Error(
          `Protocol object with name "${protocolName}" not found in protocol "${protocolLabel}".`,
        )
      }

      if (destination) {
        // Remove a specific destination
        protocolArray[protocolObjectIndex].dest = protocolArray[
          protocolObjectIndex
        ].dest.filter((dest) => dest.extension !== destination.split(".")[1])

        // Remove the protocol object if it has no destinations
        if (protocolArray[protocolObjectIndex].dest.length === 0) {
          protocolArray.splice(protocolObjectIndex, 1)
        }
      } else {
        // Remove the entire protocol object
        protocolArray.splice(protocolObjectIndex, 1)
      }
    } else {
      // If no protocolLabel is provided, remove the entire connection
      graph.connections.splice(connectionIndex, 1)
    }
  }

  static findNode(graph: Graph, nodeName: string): Node | null {
    return graph.nodes.find((node) => node.name === nodeName) || null
  }

  static findConnection(
    graph: Graph,
    extensionGroup: string,
    extension: string,
  ): Connection | null {
    return (
      graph.connections.find(
        (conn) =>
          conn.extensionGroup === extensionGroup &&
          conn.extension === extension,
      ) || null
    )
  }

  static removeEmptyConnections(graph: Graph): void {
    graph.connections = graph.connections.filter((connection) => {
      connection.cmd =
        connection.cmd?.filter((cmd) => cmd.dest.length > 0) || []
      connection.data =
        connection.data?.filter((data) => data.dest.length > 0) || []
      connection.audioFrame =
        connection.audioFrame?.filter((audio) => audio.dest.length > 0) || []
      connection.videoFrame =
        connection.videoFrame?.filter((video) => video.dest.length > 0) || []

      // Remove the entire connection if all protocols are empty
      return (
        connection.cmd.length > 0 ||
        connection.data.length > 0 ||
        connection.audioFrame.length > 0 ||
        connection.videoFrame.length > 0
      )
    })
  }

  static removeNodeAndConnections(graph: Graph, nodeName: string): void {
    // Remove the node
    this.removeNode(graph, nodeName)

    // Remove all connections involving this node
    graph.connections = graph.connections.filter((connection) => {
      const isSource =
        connection.extensionGroup + "." + connection.extension === nodeName
      const protocols = ["cmd", "data", "audioFrame", "videoFrame"] as const

      protocols.forEach((protocol) => {
        if (connection[protocol]) {
          connection[protocol] = connection[protocol]?.filter(
            (item) => !item.dest.some((dest) => dest.extension === nodeName),
          )
        }
      })

      // Return true if connection still has content, false to remove it
      return (
        !isSource &&
        (connection.cmd?.length ||
          connection.data?.length ||
          connection.audioFrame?.length ||
          connection.videoFrame?.length)
      )
    })
  }

  /**
   * Link a tool to an LLM in the graph
   */
  static linkLLMTool(
    graph: Graph,
    llmExtension: string,
    toolExtension: string,
  ): void {
    const llmNode = graph.nodes.find((node) => node.name === llmExtension)
    const toolNode = graph.nodes.find((node) => node.name === toolExtension)

    if (!llmNode || !toolNode) {
      throw new Error(
        `Either LLM "${llmExtension}" or Tool "${toolExtension}" does not exist in graph "${graph.id}".`,
      )
    }

    // this.addConnection(graph, llmExtension, toolExtension, "llm_tool_link")
  }
}

export type { Graph, Node, Connection, Command, Destination }

export { GraphEditor, GraphConnProtocol as ProtocolLabel }
