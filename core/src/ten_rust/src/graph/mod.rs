//
// Copyright © 2025 Agora
// This file is part of TEN Framework, an open source project.
// Licensed under the Apache License, Version 2.0, with certain conditions.
// Refer to the "LICENSE" file in the root directory for more information.
//
pub mod check;
pub mod connection;
pub mod graph_info;
pub mod msg_conversion;
pub mod node;
pub mod reverse;
pub mod selector;
pub mod subgraph;

use std::collections::HashMap;

use anyhow::Result;
use node::GraphNode;
use serde::{Deserialize, Serialize};

use self::{
    connection::{GraphConnection, GraphMessageFlow},
    node::GraphNodeType,
};
use crate::{
    base_dir_pkg_info::PkgsInfoInApp,
    constants::{ERR_MSG_GRAPH_APP_FIELD_EMPTY, ERR_MSG_GRAPH_MIXED_APP_DECLARATIONS},
    pkg_info::localhost,
};

/// The state of the 'app' field declaration in all nodes in the graph.
///
/// There might be the following cases for the 'app' field declaration:
///
/// - Case 1: neither of the nodes has declared the 'app' field. The state will
///   be `NoneDeclared`.
///
/// - Case 2: all nodes have declared the 'app' field, and all of them have the
///   same value. Ex:
///
/// {
///   "nodes": [
///     {
///       "type": "extension",
///       "app": "http://localhost:8000",
///       "addon": "addon_1",
///       "name": "ext_1",
///       "extension_group": "some_group"
///     },
///     {
///       "type": "extension",
///       "app": "http://localhost:8000",
///       "addon": "addon_2",
///       "name": "ext_2",
///       "extension_group": "another_group"
///     }
///   ]
/// }
///
///   The state will be `UniformDeclared`.
///
/// - Case 3: all nodes have declared the 'app' field, but they have different
///   values.
///
/// {
///   "nodes": [
///     {
///       "type": "extension",
///       "app": "http://localhost:8000",
///       "addon": "addon_1",
///       "name": "ext_1",
///       "extension_group": "some_group"
///     },
///     {
///       "type": "extension",
///       "app": "msgpack://localhost:8001",
///       "addon": "addon_2",
///       "name": "ext_2",
///       "extension_group": "another_group"
///     }
///   ]
/// }
///
///   The state will be `MixedDeclared`.
///
/// - Case 4: some nodes have declared the 'app' field, and some have not. It's
///   illegal.
///
/// In the view of the 'app' field declaration, there are two types of graphs:
///
/// * Single-app graph: the state is `NoneDeclared` or `UniformDeclared`.
/// * Multi-app graph: the state is `MixedDeclared`.
#[derive(Debug, Clone, PartialEq, Eq, Copy)]
pub enum AppUriDeclarationState {
    /// No node has declared an app URI.
    NoneDeclared,
    /// All nodes have declared the same app URI.
    UniformDeclared,
    /// Nodes have declared different app URIs.
    MixedDeclared,
}

impl AppUriDeclarationState {
    /// Returns true if the graph can be considered a single-app graph.
    pub fn is_single_app_graph(&self) -> bool {
        matches!(
            self,
            AppUriDeclarationState::NoneDeclared | AppUriDeclarationState::UniformDeclared
        )
    }
}

/// The type of exposed message interface.
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum GraphExposedMessageType {
    CmdIn,
    CmdOut,
    DataIn,
    DataOut,
    AudioFrameIn,
    AudioFrameOut,
    VideoFrameIn,
    VideoFrameOut,
}

/// Represents a message interface that is exposed by the graph to the outside.
/// This is mainly used by development tools to provide intelligent prompts.
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct GraphExposedMessage {
    #[serde(rename = "type")]
    pub msg_type: GraphExposedMessageType,

    /// The name of the message.
    /// Must match the regular expression ^[A-Za-z_][A-Za-z0-9_]*$
    pub name: String,

    /// The name of the extension.
    /// Must match the regular expression ^[A-Za-z_][A-Za-z0-9_]*$
    #[serde(skip_serializing_if = "Option::is_none")]
    pub extension: Option<String>,

    /// The name of the subgraph.
    /// Must match the regular expression ^[A-Za-z_][A-Za-z0-9_]*$
    #[serde(skip_serializing_if = "Option::is_none")]
    pub subgraph: Option<String>,
}

/// Represents a property that is exposed by the graph to the outside.
/// This is mainly used by development tools to provide intelligent prompts.
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct GraphExposedProperty {
    /// The name of the extension.
    /// Must match the regular expression ^[A-Za-z_][A-Za-z0-9_]*$
    #[serde(skip_serializing_if = "Option::is_none")]
    pub extension: Option<String>,

    /// The name of the subgraph.
    /// Must match the regular expression ^[A-Za-z_][A-Za-z0-9_]*$
    #[serde(skip_serializing_if = "Option::is_none")]
    pub subgraph: Option<String>,

    /// The name of the property.
    /// Must match the regular expression ^[A-Za-z_][A-Za-z0-9_]*$
    pub name: String,
}

/// Represents a connection graph that defines how extensions connect to each
/// other.
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct Graph {
    #[serde(skip_serializing_if = "Vec::is_empty", default)]
    pub nodes: Vec<GraphNode>,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub connections: Option<Vec<GraphConnection>>,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub exposed_messages: Option<Vec<GraphExposedMessage>>,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub exposed_properties: Option<Vec<GraphExposedProperty>>,
}

impl Graph {
    /// Parses a JSON string into a Graph with validation, completion, and
    /// flattening.
    ///
    /// This function takes a JSON string representation of a graph and an
    /// optional current_base_dir parameter, parses it into a Graph structure,
    /// then validates, completes, and flattens the graph.
    ///
    /// # Parameters
    /// - `s`: A string slice containing the JSON representation of the graph
    /// - `current_base_dir`: An optional base directory path used for resolving
    ///   relative paths during graph flattening
    ///
    /// # Returns
    /// - `Ok(Graph)`: Successfully parsed and processed graph
    /// - `Err(anyhow::Error)`: Parsing, validation, or processing error
    pub async fn from_str_with_base_dir(s: &str, current_base_dir: Option<&str>) -> Result<Self> {
        let mut graph: Graph = serde_json::from_str(s)?;

        graph.validate_and_complete(current_base_dir)?;

        // Return the parsed data.
        Ok(graph)
    }

    pub fn from_str_and_validate(s: &str) -> Result<Self> {
        let mut graph: Graph = serde_json::from_str(s)?;
        graph.validate_and_complete(None)?;
        Ok(graph)
    }

    /// Determines how app URIs are declared across all nodes in the graph.
    ///
    /// This method analyzes all nodes in the graph to determine the app
    /// declaration state:
    /// - If no nodes have an 'app' field declared, returns `NoneDeclared`.
    /// - If all nodes have the same 'app' URI declared, returns
    ///   `UniformDeclared`.
    /// - If all nodes have 'app' fields but with different URIs, returns
    ///   `MixedDeclared`.
    /// - If some nodes have 'app' fields and others don't, returns an error as
    ///   this is invalid.
    ///
    /// Graphs can be categorized based on the number of apps:
    /// - A graph for a single app (NoneDeclared or UniformDeclared state)
    /// - A graph spanning multiple apps (MixedDeclared state)
    ///
    /// For a valid graph, either all nodes must have the app field defined or
    /// none of them should. If some nodes have the app field defined while
    /// others do not, it creates an invalid graph because TEN cannot
    /// determine which app the nodes without the defined field belong to.
    /// Therefore, the only valid case where nodes don't define the app
    /// field is when all nodes in the graph lack this field.
    ///
    /// For graphs spanning multiple apps, no node can have 'localhost' as its
    /// app field value, as other apps would not know how to connect to the
    /// app that node belongs to. For consistency, single app graphs also do
    /// not allow 'localhost' as an explicit app field value. Instead,
    /// 'localhost' is used as the internal default value when no app field is
    /// specified.
    /// Returns true if all nodes in the graph belong to the same app, i.e., the
    /// graph is not a multi-app graph.
    ///
    /// This is a convenience wrapper around `analyze_app_uri_declaration_state`
    /// for callers that only need the single-vs-multi distinction.
    pub fn is_single_app_graph(&self) -> Result<bool> {
        Ok(self.analyze_app_uri_declaration_state()?.is_single_app_graph())
    }

    fn analyze_app_uri_declaration_state(&self) -> Result<AppUriDeclarationState> {
        let mut nodes_have_declared_app = 0;
        let mut app_uris = std::collections::HashSet::new();

        for (idx, node) in self.nodes.iter().enumerate() {
            if let Some(app_uri) = &node.get_app_uri() {
                if app_uri.is_empty() {
                    return Err(anyhow::anyhow!(
                        "nodes[{}]: {}",
                        idx,
                        ERR_MSG_GRAPH_APP_FIELD_EMPTY
                    ));
                }

                app_uris.insert(app_uri);
                nodes_have_declared_app += 1;
            }
        }

        let extension_nodes_len =
            self.nodes.iter().filter(|node| node.get_type() == GraphNodeType::Extension).count();

        // Some nodes have 'app' declared and some don't - this is invalid.
        // Because TEN can not determine which app the nodes without the defined
        // field belong to.
        if nodes_have_declared_app != 0 && nodes_have_declared_app != extension_nodes_len {
            return Err(anyhow::anyhow!(ERR_MSG_GRAPH_MIXED_APP_DECLARATIONS));
        }

        match app_uris.len() {
            // No nodes have 'app' declared.
            0 => Ok(AppUriDeclarationState::NoneDeclared),

            // All nodes have the same 'app' URI declared.
            1 => Ok(AppUriDeclarationState::UniformDeclared),

            // All nodes have 'app' declared but with different URIs.
            _ => Ok(AppUriDeclarationState::MixedDeclared),
        }
    }

    /// Validates and completes the graph by ensuring all nodes and connections
    /// follow the app declaration rules and other validation requirements.
    pub fn validate_and_complete(&mut self, _current_base_dir: Option<&str>) -> Result<()> {
        // Determine the app URI declaration state by examining all nodes.
        let app_uri_declaration_state = self.analyze_app_uri_declaration_state()?;

        // Validate all nodes.
        for (idx, node) in self.nodes.iter_mut().enumerate() {
            node.validate_and_complete(&app_uri_declaration_state)
                .map_err(|e| anyhow::anyhow!("nodes[{}]: {}", idx, e))?;
        }

        // Validate all connections if they exist.
        if let Some(connections) = &mut self.connections {
            for (idx, connection) in connections.iter_mut().enumerate() {
                connection
                    .validate_and_complete(&app_uri_declaration_state)
                    .map_err(|e| anyhow::anyhow!("connections[{}]: {}", idx, e))?;
            }
        }

        // Validate exposed_properties if they exist
        if let Some(exposed_properties) = &self.exposed_properties {
            for (idx, property) in exposed_properties.iter().enumerate() {
                // Verify that the extension exists in the graph
                if !self.nodes.iter().any(|node| {
                    if let Some(ext) = &property.extension {
                        node.get_name() == ext
                    } else {
                        false
                    }
                }) {
                    return Err(anyhow::anyhow!(
                        "exposed_properties[{}]: extension '{}' does not exist in the graph",
                        idx,
                        property.extension.as_ref().unwrap_or(&String::new())
                    ));
                }
            }
        }

        Ok(())
    }

    pub fn check(
        &self,
        graph_app_base_dir: &Option<String>,
        pkgs_cache: &HashMap<String, PkgsInfoInApp>,
    ) -> Result<()> {
        self.static_check()?;

        self.check_nodes_installation(graph_app_base_dir, pkgs_cache, false)?;
        self.check_connections_compatibility(graph_app_base_dir, pkgs_cache, false)?;

        Ok(())
    }

    pub fn check_for_single_app(
        &self,
        graph_app_base_dir: &Option<String>,
        pkgs_cache: &HashMap<String, PkgsInfoInApp>,
    ) -> Result<()> {
        assert!(pkgs_cache.len() == 1);

        self.static_check()?;

        // In a single app, there is no information about pkg_info of other
        // apps, neither the message schemas.
        self.check_nodes_installation(graph_app_base_dir, pkgs_cache, true)?;
        self.check_connections_compatibility(graph_app_base_dir, pkgs_cache, true)?;

        Ok(())
    }

    pub fn static_check(&self) -> Result<()> {
        self.check_extension_uniqueness()?;
        self.check_extension_existence()?;
        self.check_connection_extensions_exist()?;
        self.check_subgraph_references_exist()?;
        self.check_extension_uniqueness_in_connections()?;
        self.check_message_names()?;
        self.check_msg_conversions()?;

        Ok(())
    }

    pub fn static_check_for_pre_flatten_graph(&self) -> Result<()> {
        self.check_extension_uniqueness()?;
        self.check_connection_extensions_exist()?;
        self.check_subgraph_references_exist()?;

        Ok(())
    }

    pub fn get_addon_name_of_extension(
        &self,
        app: &Option<String>,
        extension: &String,
    ) -> Result<&String> {
        self.nodes
            .iter()
            .find(|node| {
                node.get_type() == GraphNodeType::Extension
                    && node.get_name() == extension
                    && node.get_app_uri() == app
            })
            .and_then(|node| {
                if let GraphNode::Extension {
                    content,
                } = node
                {
                    Some(&content.addon)
                } else {
                    None
                }
            })
            .ok_or_else(|| {
                anyhow::anyhow!(
                    "Extension '{}' is not found in nodes, should not happen.",
                    extension
                )
            })
    }

    /// Expands items with 'names' arrays into multiple items with individual
    /// 'name' fields.
    ///
    /// This method processes all connections in the graph and for any message
    /// flow (cmd, data, audio_frame, video_frame) that has a 'names' field,
    /// it creates multiple copies of that item, one for each name in the
    /// array, replacing the 'names' field with an individual 'name' field.
    pub fn expand_names_to_individual_items(&self) -> Result<Option<Graph>> {
        let mut graph_changed = false;
        let mut new_connections = Vec::new();

        if let Some(connections) = &self.connections {
            for connection in connections {
                let mut new_connection = connection.clone();

                // Process cmd flows
                if let Some(cmd_flows) = &connection.cmd {
                    let mut new_cmd_flows = Vec::new();
                    for flow in cmd_flows {
                        if let Some(names) = &flow.names {
                            // Expand this flow into multiple flows
                            for name in names {
                                let mut new_flow = flow.clone();
                                new_flow.name = Some(name.clone());
                                new_flow.names = None; // Remove the names field
                                new_cmd_flows.push(new_flow);
                            }
                            graph_changed = true;
                        } else {
                            new_cmd_flows.push(flow.clone());
                        }
                    }
                    new_connection.cmd = Some(new_cmd_flows);
                }

                // Process data flows
                if let Some(data_flows) = &connection.data {
                    let mut new_data_flows = Vec::new();
                    for flow in data_flows {
                        if let Some(names) = &flow.names {
                            // Expand this flow into multiple flows
                            for name in names {
                                let mut new_flow = flow.clone();
                                new_flow.name = Some(name.clone());
                                new_flow.names = None; // Remove the names field
                                new_data_flows.push(new_flow);
                            }
                            graph_changed = true;
                        } else {
                            new_data_flows.push(flow.clone());
                        }
                    }
                    new_connection.data = Some(new_data_flows);
                }

                // Process audio_frame flows
                if let Some(audio_frame_flows) = &connection.audio_frame {
                    let mut new_audio_frame_flows = Vec::new();
                    for flow in audio_frame_flows {
                        if let Some(names) = &flow.names {
                            // Expand this flow into multiple flows
                            for name in names {
                                let mut new_flow = flow.clone();
                                new_flow.name = Some(name.clone());
                                new_flow.names = None; // Remove the names field
                                new_audio_frame_flows.push(new_flow);
                            }
                            graph_changed = true;
                        } else {
                            new_audio_frame_flows.push(flow.clone());
                        }
                    }
                    new_connection.audio_frame = Some(new_audio_frame_flows);
                }

                // Process video_frame flows
                if let Some(video_frame_flows) = &connection.video_frame {
                    let mut new_video_frame_flows = Vec::new();
                    for flow in video_frame_flows {
                        if let Some(names) = &flow.names {
                            // Expand this flow into multiple flows
                            for name in names {
                                let mut new_flow = flow.clone();
                                new_flow.name = Some(name.clone());
                                new_flow.names = None; // Remove the names field
                                new_video_frame_flows.push(new_flow);
                            }
                            graph_changed = true;
                        } else {
                            new_video_frame_flows.push(flow.clone());
                        }
                    }
                    new_connection.video_frame = Some(new_video_frame_flows);
                }

                new_connections.push(new_connection);
            }
        }

        if !graph_changed {
            return Ok(None);
        }

        // Create new graph with expanded connections
        let mut new_graph = self.clone();
        new_graph.connections = Some(new_connections);
        Ok(Some(new_graph))
    }

    /// Applies the passes that must run before subgraph flattening:
    ///
    /// 1. Expand `names` arrays into individual `name` items.
    /// 2. Replace selector references with the nodes they match.
    /// 3. Convert reversed connections (`source`) to forward connections
    ///    (`dest`).
    ///
    /// `flatten_subgraphs` relies on all three having already run - it expects
    /// `name` to be `Some`, `names` to be `None`, and every node to be an
    /// extension node. Any graph handed to it, including one imported through
    /// `import_uri`, has to go through here first.
    ///
    /// Returns `Ok(None)` if none of the passes changed anything.
    pub fn apply_pre_flatten_passes(&self) -> Result<Option<Graph>> {
        let mut processing_graph = self;

        let expanded_names_graph = processing_graph.expand_names_to_individual_items()?;
        processing_graph = expanded_names_graph.as_ref().unwrap_or(processing_graph);

        let flattened_selector_graph = processing_graph.flatten_selectors()?;
        processing_graph = flattened_selector_graph.as_ref().unwrap_or(processing_graph);

        let reversed_graph =
            processing_graph.convert_reversed_connections_to_forward_connections()?;
        processing_graph = reversed_graph.as_ref().unwrap_or(processing_graph);

        if std::ptr::eq(processing_graph, self) {
            return Ok(None);
        }

        Ok(Some(processing_graph.clone()))
    }

    /// Convenience method for flattening a graph instance without preserving
    /// exposed info. This is the main public API for flattening graphs.
    ///
    /// Returns `Ok(None)` if the graph doesn't need flattening. Returns
    /// `Ok(Some(flattened_graph))` if the graph was successfully flattened.
    pub async fn flatten_graph(&self, current_base_dir: Option<&str>) -> Result<Option<Graph>> {
        let mut processing_graph = self;

        // Steps 1-3: names expansion, selector resolution, reversed connections.
        let pre_flattened_graph = processing_graph.apply_pre_flatten_passes()?;
        processing_graph = pre_flattened_graph.as_ref().unwrap_or(processing_graph);

        // Step 4: Flatten subgraphs
        let flattened = Self::flatten_subgraphs(processing_graph, current_base_dir, false)
            .await
            .map_err(|e| anyhow::anyhow!("Failed to flatten graph: {}", e))?;
        processing_graph = flattened.as_ref().unwrap_or(processing_graph);

        // Check if the processing graph is the same as the original graph.
        if std::ptr::eq(processing_graph, self) {
            return Ok(None);
        }

        Ok(Some(processing_graph.clone()))
    }

    /// Converts exposed_messages into a ten:graph_proxy extension node and
    /// automatically creates connections.
    ///
    /// This method implements the cross-graph message routing design by:
    /// 1. Creating a ten:graph_proxy extension node if exposed_messages exist
    /// 2. Creating connections based on message types:
    ///    - For *_in messages: ten:graph_proxy -> target extension
    ///    - For *_out messages: source extension -> ten:graph_proxy
    ///
    /// # Arguments
    /// * `host_loc_property` - Optional host location property (app_uri,
    ///   graph_id, extension_name) to set on the graph_proxy node
    ///
    /// # Returns
    /// * `Ok(None)` if there are no exposed_messages
    /// * `Ok(Some(new_graph))` if graph_proxy was added successfully
    /// * `Err` if there are validation errors
    pub fn inject_graph_proxy_from_exposed_messages(
        &self,
        host_loc_json_str: Option<&str>,
    ) -> Result<Option<Graph>> {
        // Check if exposed_messages exist
        let Some(exposed_messages) = &self.exposed_messages else {
            return Ok(None);
        };

        if exposed_messages.is_empty() {
            return Ok(None);
        }

        const GRAPH_PROXY_NAME: &str = "ten:graph_proxy";
        const GRAPH_PROXY_ADDON: &str = "ten:graph_proxy";

        // Check if graph_proxy node already exists
        if self.nodes.iter().any(|node| node.get_name() == GRAPH_PROXY_NAME) {
            return Err(anyhow::anyhow!(
                "Graph already contains a node named '{}', cannot inject graph_proxy",
                GRAPH_PROXY_NAME
            ));
        }

        let mut new_graph = self.clone();

        // Parse the host_loc_json_str to serde_json::Value and wrap it in a
        // property object with "host_loc" key
        let proxy_property = host_loc_json_str.map(|host_loc| {
            let host_loc_value: serde_json::Value = serde_json::from_str(host_loc).unwrap();
            serde_json::json!({
                "host_loc": host_loc_value
            })
        });

        let proxy_node = GraphNode::new_extension_node(
            GRAPH_PROXY_NAME.to_string(),
            GRAPH_PROXY_ADDON.to_string(),
            None, // extension_group
            None, // app
            proxy_property,
        );

        new_graph.nodes.push(proxy_node);

        // Create connections based on exposed_messages
        let mut new_connections = new_graph.connections.clone().unwrap_or_default();

        for exposed_msg in exposed_messages {
            // Validate that either extension or subgraph is specified
            let target_extension = if let Some(ext) = &exposed_msg.extension {
                ext.clone()
            } else if exposed_msg.subgraph.is_some() {
                return Err(anyhow::anyhow!(
                    "Subgraph references in exposed_messages are not supported for graph_proxy \
                     injection. Please flatten the graph first."
                ));
            } else {
                return Err(anyhow::anyhow!(
                    "exposed_messages entry must specify either 'extension' or 'subgraph'"
                ));
            };

            // Verify the target extension exists and get its app URI
            let target_extension_app = self
                .nodes
                .iter()
                .find(|node| {
                    node.get_type() == GraphNodeType::Extension
                        && node.get_name() == target_extension
                })
                .map(|node| node.get_app_uri())
                .ok_or_else(|| {
                    anyhow::anyhow!(
                        "Extension '{}' referenced in exposed_messages does not exist in the graph",
                        target_extension
                    )
                })?;

            use connection::GraphDestination;

            match exposed_msg.msg_type {
                // For *_in messages: ten:graph_proxy -> target extension
                GraphExposedMessageType::CmdIn => {
                    let connection = Self::find_or_create_connection(
                        &mut new_connections,
                        GRAPH_PROXY_NAME,
                        GraphNodeType::Extension,
                        None,
                    );

                    let dest = GraphDestination::new(
                        target_extension_app.clone(),
                        GraphNodeType::Extension,
                        target_extension.clone(),
                    )?;

                    Self::add_dest_to_flow(
                        connection.cmd.get_or_insert_with(Vec::new),
                        &exposed_msg.name,
                        dest,
                    );
                }
                GraphExposedMessageType::DataIn => {
                    let connection = Self::find_or_create_connection(
                        &mut new_connections,
                        GRAPH_PROXY_NAME,
                        GraphNodeType::Extension,
                        None,
                    );

                    let dest = GraphDestination::new(
                        target_extension_app.clone(),
                        GraphNodeType::Extension,
                        target_extension.clone(),
                    )?;

                    Self::add_dest_to_flow(
                        connection.data.get_or_insert_with(Vec::new),
                        &exposed_msg.name,
                        dest,
                    );
                }
                GraphExposedMessageType::AudioFrameIn => {
                    let connection = Self::find_or_create_connection(
                        &mut new_connections,
                        GRAPH_PROXY_NAME,
                        GraphNodeType::Extension,
                        None,
                    );

                    let dest = GraphDestination::new(
                        target_extension_app.clone(),
                        GraphNodeType::Extension,
                        target_extension.clone(),
                    )?;

                    Self::add_dest_to_flow(
                        connection.audio_frame.get_or_insert_with(Vec::new),
                        &exposed_msg.name,
                        dest,
                    );
                }
                GraphExposedMessageType::VideoFrameIn => {
                    let connection = Self::find_or_create_connection(
                        &mut new_connections,
                        GRAPH_PROXY_NAME,
                        GraphNodeType::Extension,
                        None,
                    );

                    let dest = GraphDestination::new(
                        target_extension_app.clone(),
                        GraphNodeType::Extension,
                        target_extension.clone(),
                    )?;

                    Self::add_dest_to_flow(
                        connection.video_frame.get_or_insert_with(Vec::new),
                        &exposed_msg.name,
                        dest,
                    );
                }
                // For *_out messages: source extension -> ten:graph_proxy
                GraphExposedMessageType::CmdOut => {
                    let connection = Self::find_or_create_connection(
                        &mut new_connections,
                        &target_extension,
                        GraphNodeType::Extension,
                        target_extension_app.clone(),
                    );

                    let dest = GraphDestination::new(
                        None,
                        GraphNodeType::Extension,
                        GRAPH_PROXY_NAME.to_string(),
                    )?;

                    Self::add_dest_to_flow(
                        connection.cmd.get_or_insert_with(Vec::new),
                        &exposed_msg.name,
                        dest,
                    );
                }
                GraphExposedMessageType::DataOut => {
                    let connection = Self::find_or_create_connection(
                        &mut new_connections,
                        &target_extension,
                        GraphNodeType::Extension,
                        target_extension_app.clone(),
                    );

                    let dest = GraphDestination::new(
                        None,
                        GraphNodeType::Extension,
                        GRAPH_PROXY_NAME.to_string(),
                    )?;

                    Self::add_dest_to_flow(
                        connection.data.get_or_insert_with(Vec::new),
                        &exposed_msg.name,
                        dest,
                    );
                }
                GraphExposedMessageType::AudioFrameOut => {
                    let connection = Self::find_or_create_connection(
                        &mut new_connections,
                        &target_extension,
                        GraphNodeType::Extension,
                        target_extension_app.clone(),
                    );

                    let dest = GraphDestination::new(
                        None,
                        GraphNodeType::Extension,
                        GRAPH_PROXY_NAME.to_string(),
                    )?;

                    Self::add_dest_to_flow(
                        connection.audio_frame.get_or_insert_with(Vec::new),
                        &exposed_msg.name,
                        dest,
                    );
                }
                GraphExposedMessageType::VideoFrameOut => {
                    let connection = Self::find_or_create_connection(
                        &mut new_connections,
                        &target_extension,
                        GraphNodeType::Extension,
                        target_extension_app.clone(),
                    );

                    let dest = GraphDestination::new(
                        None,
                        GraphNodeType::Extension,
                        GRAPH_PROXY_NAME.to_string(),
                    )?;

                    Self::add_dest_to_flow(
                        connection.video_frame.get_or_insert_with(Vec::new),
                        &exposed_msg.name,
                        dest,
                    );
                }
            }
        }

        new_graph.connections = Some(new_connections);

        Ok(Some(new_graph))
    }

    /// Helper function to find an existing connection or create a new one.
    fn find_or_create_connection<'a>(
        connections: &'a mut Vec<GraphConnection>,
        node_name: &str,
        node_type: GraphNodeType,
        app: Option<String>,
    ) -> &'a mut GraphConnection {
        use connection::GraphLoc;

        // Try to find existing connection
        let loc =
            GraphLoc::with_app_and_type_and_name(app.clone(), node_type, node_name.to_string())
                .unwrap();

        if let Some(pos) = connections.iter().position(|conn| conn.loc.matches(&loc)) {
            return &mut connections[pos];
        }

        // Create new connection if not found
        let new_conn = GraphConnection::new(loc);
        connections.push(new_conn);
        connections.last_mut().unwrap()
    }

    /// Helper function to add a destination to an existing flow or create a new
    /// flow if none exists for the given message name.
    ///
    /// This function searches for an existing GraphMessageFlow with the given
    /// message name. If found, it adds the destination to that flow's dest
    /// vector. If not found, it creates a new flow with the message name and
    /// destination.
    fn add_dest_to_flow(
        flows: &mut Vec<GraphMessageFlow>,
        msg_name: &str,
        dest: connection::GraphDestination,
    ) {
        use connection::GraphMessageFlow;

        // Try to find existing flow with the same message name
        if let Some(existing_flow) =
            flows.iter_mut().find(|flow| flow.name.as_ref().is_some_and(|n| n == msg_name))
        {
            // Add destination to existing flow
            existing_flow.dest.push(dest);
        } else {
            // Create new flow
            let flow = GraphMessageFlow::new(Some(msg_name.to_string()), None, vec![dest], vec![]);
            flows.push(flow);
        }
    }
}

/// Checks if the application URI is either not specified (None) or set to the
/// default localhost value.
///
/// This function is used to determine if an application's URI is using the
/// default location, which helps decide whether the URI field should be
/// included when serializing property data.
pub fn is_app_default_loc_or_none(app_uri: &Option<String>) -> bool {
    match app_uri {
        None => true,
        Some(uri) => uri == localhost(),
    }
}
