//
// Copyright © 2025 Agora
// This file is part of TEN Framework, an open source project.
// Licensed under the Apache License, Version 2.0, with certain conditions.
// Refer to the "LICENSE" file in the root directory for more information.
//
use std::collections::HashMap;

use anyhow::Result;

use crate::graph::{
    connection::GraphLoc,
    graph_info::load_graph_from_uri,
    node::{ExtensionNode, GraphNode, SubgraphNode},
    Graph, GraphConnection, GraphExposedMessage, GraphExposedMessageType, GraphMessageFlow,
    GraphNodeType,
};

impl Graph {
    /// Helper function to flatten a GraphLoc by adding subgraph name prefix
    /// to extension names and validating that no nested subgraphs exist.
    fn flatten_graph_loc_in_subgraph(loc: &mut GraphLoc, subgraph_name: &str) {
        if let Some(ref extension) = loc.extension {
            loc.extension = Some(format!("{subgraph_name}_{extension}"));
        }

        if loc.subgraph.is_some() {
            panic!(
                "Should not happen, when flattening a subgraph, the subgraphs inside it should \
                 have already been flattened, so we should not see any subgraph inside."
            );
        }
    }

    /// Updates connection source to use flattened names for subgraph elements.
    fn flatten_connection_source_in_subgraph(
        connection: &mut GraphConnection,
        subgraph_name: &str,
    ) {
        Self::flatten_graph_loc_in_subgraph(&mut connection.loc, subgraph_name);
    }

    /// Updates connection destinations to use flattened names for subgraph
    /// elements.
    fn flatten_connection_destinations_in_subgraph(
        connection: &mut GraphConnection,
        subgraph_name: &str,
    ) {
        let update_destinations = |flows: &mut Vec<GraphMessageFlow>| {
            for flow in flows {
                for dest in &mut flow.dest {
                    Self::flatten_graph_loc_in_subgraph(&mut dest.loc, subgraph_name);
                }
            }
        };

        if let Some(ref mut cmd) = connection.cmd {
            update_destinations(cmd);
        }
        if let Some(ref mut data) = connection.data {
            update_destinations(data);
        }
        if let Some(ref mut audio_frame) = connection.audio_frame {
            update_destinations(audio_frame);
        }
        if let Some(ref mut video_frame) = connection.video_frame {
            update_destinations(video_frame);
        }
    }

    /// Helper function to resolve subgraph reference to actual extension name
    /// with prefix. Prefix (subgraph_name) when flattening the graph.
    fn resolve_subgraph_to_extension_with_prefix(
        subgraph_name: &str,
        subgraph: &Graph,
        msg_name: &str,
        msg_type: GraphExposedMessageType,
    ) -> Result<String> {
        let extension_name =
            Self::resolve_subgraph_to_extension(subgraph_name, msg_name, msg_type, subgraph)?;
        Ok(format!("{subgraph_name}_{extension_name}"))
    }

    /// Helper function to process message flows and add them to extension_flows
    /// HashMap.
    ///
    /// Since connections originating from a subgraph as source may come from
    /// different extensions within the subgraph, the logic of this function
    /// is not to modify the existing connection, but to generate multiple new
    /// connections originating from extensions within the subgraph.
    fn flatten_connection_source_of_one_type_for_subgraph(
        flows: &[GraphMessageFlow],
        msg_type: GraphExposedMessageType,
        subgraph_name: &str,
        subgraph: &Graph,
        base_connection: &GraphConnection,
        extension_flows: &mut HashMap<String, GraphConnection>,
    ) -> Result<()> {
        for flow in flows {
            // After flatten_graph processing, name should be Some and names
            // should be None
            let msg_name = flow
                .name
                .as_ref()
                .expect("name field should be Some after flatten_graph processing");

            if flow.names.is_some() {
                panic!("names field should be None after flatten_graph processing");
            }

            let extension_name = Self::resolve_subgraph_to_extension_with_prefix(
                subgraph_name,
                subgraph,
                msg_name,
                msg_type.clone(),
            )?;

            let entry =
                extension_flows.entry(extension_name.clone()).or_insert_with(|| GraphConnection {
                    loc: GraphLoc {
                        app: base_connection.loc.app.clone(),
                        extension: Some(extension_name),
                        subgraph: None,
                        selector: None,
                    },
                    cmd: None,
                    data: None,
                    audio_frame: None,
                    video_frame: None,
                });

            // Add flow to the appropriate field based on message type
            match msg_type {
                GraphExposedMessageType::CmdOut => {
                    if entry.cmd.is_none() {
                        entry.cmd = Some(Vec::new());
                    }
                    entry.cmd.as_mut().unwrap().push(flow.clone());
                }
                GraphExposedMessageType::DataOut => {
                    if entry.data.is_none() {
                        entry.data = Some(Vec::new());
                    }
                    entry.data.as_mut().unwrap().push(flow.clone());
                }
                GraphExposedMessageType::AudioFrameOut => {
                    if entry.audio_frame.is_none() {
                        entry.audio_frame = Some(Vec::new());
                    }
                    entry.audio_frame.as_mut().unwrap().push(flow.clone());
                }
                GraphExposedMessageType::VideoFrameOut => {
                    if entry.video_frame.is_none() {
                        entry.video_frame = Some(Vec::new());
                    }
                    entry.video_frame.as_mut().unwrap().push(flow.clone());
                }
                _ => {
                    return Err(anyhow::anyhow!(
                        "Unsupported message type for source: {:?}",
                        msg_type
                    ));
                }
            }
        }
        Ok(())
    }

    /// Helper function to process a destination location for subgraph
    /// resolution. This function handles both colon notation and subgraph
    /// field resolution.
    fn process_dest_location_for_subgraph_resolution(
        loc: &mut GraphLoc,
        subgraph_mappings: &HashMap<String, Graph>,
        msg_name: &str,
        msg_type: GraphExposedMessageType,
    ) -> Result<()> {
        // Since extension and subgraph fields are mutually exclusive, we can
        // simplify the logic
        if let Some(ref subgraph_name) = loc.subgraph.take() {
            // Handle subgraph field - resolve to actual extension based on
            // exposed_messages
            let subgraph = subgraph_mappings
                .get(subgraph_name)
                .ok_or_else(|| anyhow::anyhow!("Subgraph '{subgraph_name}' not found"))?;

            let extension_name = Self::resolve_subgraph_to_extension_with_prefix(
                subgraph_name,
                subgraph,
                msg_name,
                msg_type,
            )?;

            loc.extension = Some(extension_name);
            // subgraph field is already cleared by take()
        }

        Ok(())
    }

    /// Expands a connection source if it references a subgraph element using
    /// colon notation (e.g., "subgraph_1:ext_c" -> "subgraph_1_ext_c") or
    /// subgraph field. Groups message flows by their resolved extension names
    /// so that flows with the same source extension are combined into a single
    /// connection based on exposed_messages.
    fn flatten_connection_source_for_subgraph(
        connection: &GraphConnection,
        subgraph_mappings: &HashMap<String, Graph>,
    ) -> Result<Vec<GraphConnection>> {
        let mut expanded_connections = Vec::new();
        let base_connection = connection.clone();

        // Check if we have a subgraph field that needs to be resolved
        if base_connection.loc.subgraph.is_some() {
            let subgraph_name = base_connection.loc.subgraph.as_ref().unwrap();
            let subgraph = subgraph_mappings
                .get(subgraph_name)
                .ok_or_else(|| anyhow::anyhow!("Subgraph '{}' not found", subgraph_name))?;

            // Use a HashMap to group flows by their resolved extension names
            let mut extension_flows: HashMap<String, GraphConnection> = HashMap::new();

            // Process cmd flows
            if let Some(ref cmd_flows) = base_connection.cmd {
                Self::flatten_connection_source_of_one_type_for_subgraph(
                    cmd_flows,
                    GraphExposedMessageType::CmdOut,
                    subgraph_name,
                    subgraph,
                    &base_connection,
                    &mut extension_flows,
                )?;
            }

            // Process data flows
            if let Some(ref data_flows) = base_connection.data {
                Self::flatten_connection_source_of_one_type_for_subgraph(
                    data_flows,
                    GraphExposedMessageType::DataOut,
                    subgraph_name,
                    subgraph,
                    &base_connection,
                    &mut extension_flows,
                )?;
            }

            // Process audio_frame flows
            if let Some(ref audio_frame_flows) = base_connection.audio_frame {
                Self::flatten_connection_source_of_one_type_for_subgraph(
                    audio_frame_flows,
                    GraphExposedMessageType::AudioFrameOut,
                    subgraph_name,
                    subgraph,
                    &base_connection,
                    &mut extension_flows,
                )?;
            }

            // Process video_frame flows
            if let Some(ref video_frame_flows) = base_connection.video_frame {
                Self::flatten_connection_source_of_one_type_for_subgraph(
                    video_frame_flows,
                    GraphExposedMessageType::VideoFrameOut,
                    subgraph_name,
                    subgraph,
                    &base_connection,
                    &mut extension_flows,
                )?;
            }

            // Convert the HashMap values to a Vec
            expanded_connections.extend(extension_flows.into_values());

            // If no message flows were found, it should not happen
            if expanded_connections.is_empty() {
                panic!("No message flows found for subgraph: {subgraph_name}");
            }
        } else {
            expanded_connections.push(base_connection);
        }

        Ok(expanded_connections)
    }

    /// Updates all message flow destinations to convert subgraph references
    /// from colon notation to underscore notation and resolve subgraph field
    /// references using exposed_messages.
    fn flatten_connection_destinations_for_subgraph(
        connection: &mut GraphConnection,
        subgraph_mappings: &HashMap<String, Graph>,
    ) -> Result<()> {
        let update_destinations =
            |flows: &mut Vec<GraphMessageFlow>, msg_type: &str| -> Result<()> {
                for flow in flows {
                    // After flatten_graph processing, name should be Some and names
                    // should be None
                    let msg_name = flow
                        .name
                        .as_ref()
                        .expect("name field should be Some after flatten_graph processing");

                    if flow.names.is_some() {
                        panic!("names field should be None after flatten_graph processing");
                    }

                    for dest in &mut flow.dest {
                        let exposed_msg_type =
                            Self::get_exposed_message_type_for_dest_subgraph(msg_type)?;

                        Self::process_dest_location_for_subgraph_resolution(
                            &mut dest.loc,
                            subgraph_mappings,
                            msg_name,
                            exposed_msg_type,
                        )?;
                    }
                }
                Ok(())
            };

        if let Some(ref mut cmd) = connection.cmd {
            update_destinations(cmd, "cmd")?;
        }
        if let Some(ref mut data) = connection.data {
            update_destinations(data, "data")?;
        }
        if let Some(ref mut audio_frame) = connection.audio_frame {
            update_destinations(audio_frame, "audio_frame")?;
        }
        if let Some(ref mut video_frame) = connection.video_frame {
            update_destinations(video_frame, "video_frame")?;
        }

        Ok(())
    }

    /// Applies properties from subgraph node reference to a flattened extension
    /// node based on exposed_properties mapping.
    fn apply_subgraph_properties_to_extension(
        flattened_node: &mut ExtensionNode,
        sub_node: &ExtensionNode,
        subgraph_node: &SubgraphNode,
        subgraph: &Graph,
    ) -> Result<()> {
        // Apply properties from subgraph node reference based on
        // exposed_properties mapping
        if let Some(serde_json::Value::Object(ref_obj)) = &subgraph_node.property {
            // Process each property specified in the subgraph node
            for (property_name, property_value) in ref_obj {
                // Find the corresponding exposed property by name
                if let Some(exposed_properties) = &subgraph.exposed_properties {
                    if let Some(exposed_prop) =
                        exposed_properties.iter().find(|ep| &ep.name == property_name)
                    {
                        // Check if this exposed property applies to the current
                        // extension
                        if let Some(ref target_extension) = exposed_prop.extension {
                            if target_extension == &sub_node.name {
                                // Initialize property object if it doesn't
                                // exist
                                if flattened_node.property.is_none() {
                                    flattened_node.property =
                                        Some(serde_json::Value::Object(serde_json::Map::new()));
                                }

                                // Apply the property value to the target
                                // property name
                                if let Some(serde_json::Value::Object(node_obj)) =
                                    &mut flattened_node.property
                                {
                                    node_obj
                                        .insert(exposed_prop.name.clone(), property_value.clone());
                                }
                            }
                        } else {
                            panic!(
                                "Property '{property_name}' specified in subgraph node '{}' is \
                                 not exposed by the subgraph",
                                subgraph_node.name
                            );
                        }
                    } else {
                        return Err(anyhow::anyhow!(
                            "Property '{}' specified in subgraph node '{}' is not exposed by the \
                             subgraph",
                            property_name,
                            subgraph_node.name
                        ));
                    }
                } else {
                    return Err(anyhow::anyhow!(
                        "Subgraph '{}' does not have exposed_properties defined, but properties \
                         are specified in the subgraph node",
                        subgraph_node.name
                    ));
                }
            }
        }

        Ok(())
    }

    /// Helper function to add internal connections from a subgraph with proper
    /// name prefixing.
    fn add_internal_connections_from_subgraph(
        subgraph: &Graph,
        subgraph_name: &str,
        flattened_connections: &mut Vec<GraphConnection>,
    ) {
        if let Some(sub_connections) = &subgraph.connections {
            for connection in sub_connections {
                let mut flattened_connection = connection.clone();

                // Update extension names in the connection source
                Self::flatten_connection_source_in_subgraph(
                    &mut flattened_connection,
                    subgraph_name,
                );

                // Update extension names in all message flows
                Self::flatten_connection_destinations_in_subgraph(
                    &mut flattened_connection,
                    subgraph_name,
                );

                flattened_connections.push(flattened_connection);
            }
        }
    }

    /// Helper function to process extension nodes from a subgraph and add them
    /// to the flattened nodes list with proper name prefixing and property
    /// application.
    fn process_extension_nodes_from_subgraph(
        subgraph_nodes: &[ExtensionNode],
        subgraph_name: &str,
        subgraph_node: &SubgraphNode,
        subgraph: &Graph,
        flattened_nodes: &mut Vec<ExtensionNode>,
    ) -> Result<()> {
        for sub_node in subgraph_nodes {
            let mut flattened_node = sub_node.clone();
            // Add subgraph name as prefix
            flattened_node.name = format!("{}_{}", subgraph_name, sub_node.name);

            // Apply properties from subgraph node reference based on
            // exposed_properties mapping
            Self::apply_subgraph_properties_to_extension(
                &mut flattened_node,
                sub_node,
                subgraph_node,
                subgraph,
            )?;

            flattened_nodes.push(flattened_node);
        }
        Ok(())
    }

    /// Helper function to process a loaded subgraph and integrate it into the
    /// flattened structure.
    async fn process_loaded_subgraph(
        subgraph_node: &SubgraphNode,
        loaded_subgraph: &Graph,
        current_base_dir: Option<&str>,
        flattened_nodes: &mut Vec<ExtensionNode>,
        flattened_connections: &mut Vec<GraphConnection>,
        subgraph_mappings: &mut HashMap<String, Graph>,
    ) -> Result<()> {
        // Recursively flatten the loaded subgraph first to handle nested
        // subgraphs. This ensures depth-first processing.
        let flattened_subgraph =
            Box::pin(Self::flatten_subgraphs(loaded_subgraph, current_base_dir, true)).await?;

        // If the subgraph doesn't need flattening, use the original
        let flattened_subgraph = flattened_subgraph.unwrap_or_else(|| loaded_subgraph.clone());

        subgraph_mappings.insert(subgraph_node.name.clone(), flattened_subgraph.clone());

        // Flatten subgraph nodes (now all should be extensions after recursive
        // flattening)

        let subgraph_nodes = flattened_subgraph
            .nodes
            .iter()
            .map(|node| {
                if let GraphNode::Extension {
                    content,
                } = node
                {
                    content.clone()
                } else {
                    panic!("Unexpected non-extension node in flattened subgraph");
                }
            })
            .collect::<Vec<ExtensionNode>>();

        // Process all extension nodes from the subgraph
        Self::process_extension_nodes_from_subgraph(
            &subgraph_nodes,
            &subgraph_node.name,
            subgraph_node,
            &flattened_subgraph,
            flattened_nodes,
        )?;

        // Add internal connections from subgraph
        Self::add_internal_connections_from_subgraph(
            &flattened_subgraph,
            &subgraph_node.name,
            flattened_connections,
        );

        Ok(())
    }

    /// Helper function to process a single subgraph node and add its flattened
    /// content to the output collections.
    async fn process_subgraph_node(
        subgraph_node: &SubgraphNode,
        current_base_dir: Option<&str>,
        flattened_nodes: &mut Vec<ExtensionNode>,
        flattened_connections: &mut Vec<GraphConnection>,
        subgraph_mappings: &mut HashMap<String, Graph>,
    ) -> Result<()> {
        let import_uri = subgraph_node.graph.import_uri.as_str();
        if import_uri.is_empty() {
            return Err(anyhow::anyhow!(
                "Subgraph node '{}' has an empty import_uri",
                subgraph_node.name
            ));
        }

        let mut new_base_dir: Option<String> = None;
        let subgraph = load_graph_from_uri(import_uri, current_base_dir, &mut new_base_dir).await?;

        // `load_graph_from_uri` only deserializes the file, so an imported
        // subgraph has not been through the pre-flatten passes yet. Run them
        // here, otherwise `names`, selectors and reversed connections written
        // inside the subgraph reach the flattening logic unlowered.
        let pre_flattened_subgraph = subgraph.apply_pre_flatten_passes().map_err(|e| {
            anyhow::anyhow!("Failed to process subgraph '{}': {}", subgraph_node.name, e)
        })?;
        let subgraph = pre_flattened_subgraph.unwrap_or(subgraph);

        Self::process_loaded_subgraph(
            subgraph_node,
            &subgraph,
            new_base_dir.as_deref(),
            flattened_nodes,
            flattened_connections,
            subgraph_mappings,
        )
        .await
    }

    /// Helper function to process connections from a graph using subgraph
    /// mappings.
    fn process_graph_connections(
        connections: &[GraphConnection],
        subgraph_mappings: &HashMap<String, Graph>,
        flattened_connections: &mut Vec<GraphConnection>,
    ) -> Result<()> {
        for connection in connections {
            // Expand connection source if it references a subgraph element
            let expanded_connections =
                Self::flatten_connection_source_for_subgraph(connection, subgraph_mappings)?;

            for mut flattened_connection in expanded_connections {
                // Update all message flow destinations
                Self::flatten_connection_destinations_for_subgraph(
                    &mut flattened_connection,
                    subgraph_mappings,
                )?;

                flattened_connections.push(flattened_connection);
            }
        }
        Ok(())
    }

    /// Helper function that contains the common logic for flattening a graph's
    /// nodes and connections.
    async fn flatten_subgraph_internal(
        graph: &Graph,
        current_base_dir: Option<&str>,
        flattened_nodes: &mut Vec<ExtensionNode>,
        flattened_connections: &mut Vec<GraphConnection>,
        subgraph_mappings: &mut HashMap<String, Graph>,
    ) -> Result<()> {
        // Process all nodes in the graph
        for node in &graph.nodes {
            match node {
                GraphNode::Extension {
                    content,
                } => {
                    flattened_nodes.push(content.clone());
                }
                GraphNode::Subgraph {
                    content,
                } => {
                    Self::process_subgraph_node(
                        content,
                        current_base_dir,
                        flattened_nodes,
                        flattened_connections,
                        subgraph_mappings,
                    )
                    .await?;
                }
                GraphNode::Selector {
                    ..
                } => {
                    // Skip selector nodes
                    continue;
                }
            }
        }

        // Process connections from the graph
        if let Some(connections) = &graph.connections {
            Self::process_graph_connections(connections, subgraph_mappings, flattened_connections)?;
        }

        Ok(())
    }

    /// Helper function to update exposed_messages to reflect the flattened
    /// structure
    fn update_exposed_messages_after_flattening(
        original_exposed_messages: &Option<Vec<GraphExposedMessage>>,
        subgraph_mappings: &HashMap<String, Graph>,
    ) -> Option<Vec<GraphExposedMessage>> {
        if let Some(exposed_messages) = original_exposed_messages {
            let mut updated = Vec::new();
            for exposed in exposed_messages {
                // Check that either extension or subgraph field is present, but
                // not both
                match (&exposed.extension, &exposed.subgraph) {
                    (Some(_), Some(_)) => {
                        panic!(
                            "Both extension and subgraph fields are specified in exposed message. \
                             Only one should be present."
                        );
                    }
                    (None, None) => {
                        panic!(
                            "Neither extension nor subgraph field is specified in exposed \
                             message. One must be present."
                        );
                    }
                    (Some(_), None) => {
                        // Extension field is present - keep as-is
                        updated.push(exposed.clone());
                    }
                    (None, Some(ref subgraph_name)) => {
                        // Subgraph field is present - expand it
                        let flattened_subgraph =
                            subgraph_mappings.get(subgraph_name).unwrap_or_else(|| {
                                panic!(
                                    "Subgraph '{subgraph_name}' referenced in exposed message not \
                                     found in subgraph mappings"
                                );
                            });

                        // Find matching exposed messages in the flattened
                        // subgraph
                        if let Some(nested_exposed_messages) = &flattened_subgraph.exposed_messages
                        {
                            for nested_exposed in nested_exposed_messages {
                                if nested_exposed.msg_type == exposed.msg_type
                                    && nested_exposed.name == exposed.name
                                {
                                    if let Some(ref nested_extension) = nested_exposed.extension {
                                        // Create a new exposed message with the
                                        // flattened extension name
                                        let mut new_exposed = exposed.clone();
                                        new_exposed.extension =
                                            Some(format!("{subgraph_name}_{nested_extension}"));
                                        // Clear subgraph field
                                        new_exposed.subgraph = None;
                                        updated.push(new_exposed);
                                    }
                                }
                            }
                        }
                    }
                }
            }
            if updated.is_empty() {
                None
            } else {
                Some(updated)
            }
        } else {
            None
        }
    }

    /// Helper function to update exposed_properties to reflect the flattened
    /// structure
    fn update_exposed_properties_after_flattening(
        original_exposed_properties: &Option<Vec<crate::graph::GraphExposedProperty>>,
        subgraph_mappings: &HashMap<String, Graph>,
    ) -> Option<Vec<crate::graph::GraphExposedProperty>> {
        if let Some(exposed_properties) = original_exposed_properties {
            let mut updated = Vec::new();
            for exposed in exposed_properties {
                // Check that either extension or subgraph field is present, but
                // not both
                match (&exposed.extension, &exposed.subgraph) {
                    (Some(_), Some(_)) => {
                        panic!(
                            "Both extension and subgraph fields are specified in exposed \
                             property. Only one should be present."
                        );
                    }
                    (None, None) => {
                        panic!(
                            "Neither extension nor subgraph field is specified in exposed \
                             property. One must be present."
                        );
                    }
                    (Some(_), None) => {
                        // Extension field is present - keep as-is
                        updated.push(exposed.clone());
                    }
                    (None, Some(ref subgraph_name)) => {
                        // Subgraph field is present - expand it
                        let flattened_subgraph =
                            subgraph_mappings.get(subgraph_name).unwrap_or_else(|| {
                                panic!(
                                    "Subgraph '{subgraph_name}' referenced in exposed property \
                                     not found in subgraph mappings"
                                );
                            });

                        // Find matching exposed properties in the flattened
                        // subgraph
                        if let Some(nested_exposed_properties) =
                            &flattened_subgraph.exposed_properties
                        {
                            for nested_exposed in nested_exposed_properties {
                                if nested_exposed.name == exposed.name {
                                    if let Some(ref nested_extension) = nested_exposed.extension {
                                        // Create a new exposed property with
                                        // the flattened extension name
                                        let mut new_exposed = exposed.clone();
                                        new_exposed.extension =
                                            Some(format!("{subgraph_name}_{nested_extension}"));
                                        // Clear subgraph field
                                        new_exposed.subgraph = None;
                                        updated.push(new_exposed);
                                    }
                                }
                            }
                        }
                    }
                }
            }
            if updated.is_empty() {
                None
            } else {
                Some(updated)
            }
        } else {
            None
        }
    }

    /// Flattens a graph containing subgraph nodes into a regular graph
    /// structure with only extension nodes. This process converts subgraph
    /// references into their constituent extensions with prefixed names and
    /// merges all connections.
    ///
    /// Returns `Ok(None)` if the graph contains no subgraphs and doesn't need
    /// flattening. Returns `Ok(Some(flattened_graph))` if the graph was
    /// successfully flattened.
    pub async fn flatten_subgraphs(
        graph: &Graph,
        current_base_dir: Option<&str>,
        preserve_exposed_info: bool,
    ) -> Result<Option<Graph>> {
        // Check if this graph contains any subgraphs
        let has_subgraphs =
            graph.nodes.iter().any(|node| node.get_type() == GraphNodeType::Subgraph);

        if !has_subgraphs {
            // No subgraphs, return None to indicate no flattening needed
            return Ok(None);
        }

        // This graph has subgraphs, so we need to flatten them
        let mut flattened_nodes = Vec::new();
        let mut flattened_connections = Vec::new();
        let mut subgraph_mappings = HashMap::new();

        Self::flatten_subgraph_internal(
            graph,
            current_base_dir,
            &mut flattened_nodes,
            &mut flattened_connections,
            &mut subgraph_mappings,
        )
        .await?;

        // Handle exposed_messages and exposed_properties based on
        // preserve_exposed_info flag
        let (updated_exposed_messages, updated_exposed_properties) = if preserve_exposed_info {
            (
                Self::update_exposed_messages_after_flattening(
                    &graph.exposed_messages,
                    &subgraph_mappings,
                ),
                Self::update_exposed_properties_after_flattening(
                    &graph.exposed_properties,
                    &subgraph_mappings,
                ),
            )
        } else {
            (None, None)
        };

        Ok(Some(Graph {
            nodes: flattened_nodes
                .into_iter()
                .map(|node| GraphNode::Extension {
                    content: node,
                })
                .collect(),
            connections: if flattened_connections.is_empty() {
                None
            } else {
                Some(flattened_connections)
            },
            exposed_messages: updated_exposed_messages,
            exposed_properties: updated_exposed_properties,
        }))
    }
}
