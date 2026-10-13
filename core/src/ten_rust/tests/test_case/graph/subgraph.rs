//
// Copyright © 2025 Agora
// This file is part of TEN Framework, an open source project.
// Licensed under the Apache License, Version 2.0, with certain conditions.
// Refer to the "LICENSE" file in the root directory for more information.
//
#[cfg(test)]
mod tests {
    use std::fs;

    use tempfile::tempdir;
    use ten_rust::graph::{
        connection::{self, GraphConnection},
        node::{GraphNode, GraphNodeType, GraphResource},
        Graph, GraphExposedMessage, GraphExposedMessageType, GraphExposedProperty,
    };

    #[tokio::test]
    async fn test_flatten_basic_subgraph() {
        // Create a temporary directory for the subgraph
        let temp_dir = tempdir().unwrap();
        let subgraph_file_path = temp_dir.path().join("test_subgraph.json");

        // Create a main graph with a subgraph node
        let main_graph = Graph {
            nodes: vec![
                GraphNode::new_extension_node(
                    "ext_a".to_string(),
                    "addon_a".to_string(),
                    None,
                    None,
                    None,
                ),
                GraphNode::new_subgraph_node(
                    "subgraph_1".to_string(),
                    Some(serde_json::json!({"app_id": "${env:AGORA_APP_ID}"})),
                    GraphResource {
                        import_uri: format!("file://{}", subgraph_file_path.to_str().unwrap()),
                    },
                ),
            ],
            connections: Some(vec![GraphConnection {
                loc: connection::GraphLoc {
                    app: None,
                    extension: Some("ext_a".to_string()),
                    subgraph: None,
                    selector: None,
                },
                cmd: Some(vec![connection::GraphMessageFlow::new(
                    Some("B".to_string()),
                    None,
                    vec![connection::GraphDestination {
                        loc: connection::GraphLoc {
                            app: None,
                            extension: Some("subgraph_1_ext_d".to_string()),
                            subgraph: None,
                            selector: None,
                        },
                        msg_conversion: None,
                    }],
                    vec![],
                )]),
                data: None,
                audio_frame: None,
                video_frame: None,
            }]),
            exposed_messages: Some(vec![]),
            exposed_properties: Some(vec![]),
        };

        // Create a subgraph to be loaded
        let subgraph = Graph {
            nodes: vec![
                GraphNode::new_extension_node(
                    "ext_c".to_string(),
                    "addon_c".to_string(),
                    None,
                    None,
                    None,
                ),
                GraphNode::new_extension_node(
                    "ext_d".to_string(),
                    "addon_d".to_string(),
                    None,
                    None,
                    None,
                ),
            ],
            connections: Some(vec![GraphConnection {
                loc: connection::GraphLoc {
                    app: None,
                    extension: Some("ext_c".to_string()),
                    subgraph: None,
                    selector: None,
                },
                cmd: Some(vec![connection::GraphMessageFlow::new(
                    Some("B".to_string()),
                    None,
                    vec![connection::GraphDestination {
                        loc: connection::GraphLoc {
                            app: None,
                            extension: Some("ext_d".to_string()),
                            subgraph: None,
                            selector: None,
                        },
                        msg_conversion: None,
                    }],
                    vec![],
                )]),
                data: None,
                audio_frame: None,
                video_frame: None,
            }]),
            exposed_messages: None,
            exposed_properties: Some(vec![GraphExposedProperty {
                extension: Some("ext_d".to_string()),
                name: "app_id".to_string(),
                subgraph: None,
            }]),
        };

        // Write the subgraph to a file
        let subgraph_json = serde_json::to_string(&subgraph).unwrap();
        fs::write(subgraph_file_path, subgraph_json).unwrap();

        // Flatten the graph
        let flattened = main_graph.flatten_graph(None).await.unwrap().unwrap();

        // Verify results
        assert_eq!(flattened.nodes.len(), 3); // ext_a + 2 from subgraph

        // Verify that all nodes are extension nodes
        assert!(flattened.nodes.iter().all(|node| node.get_type() == GraphNodeType::Extension));

        // Convert to extension nodes
        let extension_nodes = flattened
            .nodes
            .iter()
            .map(|node| match node {
                GraphNode::Extension {
                    content,
                } => content.clone(),
                _ => panic!("Expected extension node, got {node:?}"),
            })
            .collect::<Vec<_>>();

        // Check that original extension is preserved
        assert!(extension_nodes.iter().any(|node| node.name == "ext_a" && node.addon == "addon_a"));

        // Check that subgraph extensions are flattened with prefix
        assert!(extension_nodes
            .iter()
            .any(|node| node.name == "subgraph_1_ext_c" && node.addon == "addon_c"));
        assert!(extension_nodes
            .iter()
            .any(|node| node.name == "subgraph_1_ext_d" && node.addon == "addon_d"));

        // Check that properties are merged correctly
        let ext_d_node =
            extension_nodes.iter().find(|node| node.name == "subgraph_1_ext_d").unwrap();
        assert!(ext_d_node.property.is_some());
        assert_eq!(ext_d_node.property.as_ref().unwrap()["app_id"], "${env:AGORA_APP_ID}");

        // Check that connections are flattened
        let connections = flattened.connections.as_ref().unwrap();
        assert_eq!(connections.len(), 2); // Original + internal subgraph connection

        // Check that the connection destination is correct
        let main_connection =
            connections.iter().find(|conn| conn.loc.extension.as_deref() == Some("ext_a")).unwrap();
        let cmd_flow = &main_connection.cmd.as_ref().unwrap()[0];
        assert_eq!(cmd_flow.dest[0].loc.extension.as_ref().unwrap(), "subgraph_1_ext_d");

        // Check internal subgraph connection is preserved
        let internal_connection = connections
            .iter()
            .find(|conn| conn.loc.extension.as_deref() == Some("subgraph_1_ext_c"))
            .unwrap();
        assert!(internal_connection.cmd.is_some());

        // Check that exposed_messages and exposed_properties are discarded
        assert!(flattened.exposed_messages.is_none());
        assert!(flattened.exposed_properties.is_none());
    }

    #[tokio::test]
    async fn test_flatten_subgraph_field_reference() {
        // Create a temporary directory for the subgraph
        let temp_dir = tempdir().unwrap();
        let subgraph_file_path = temp_dir.path().join("test_subgraph.json");

        // Create a main graph with subgraph field references
        let main_graph = Graph {
            nodes: vec![
                GraphNode::new_extension_node(
                    "ext_a".to_string(),
                    "addon_a".to_string(),
                    None,
                    None,
                    None,
                ),
                GraphNode::new_subgraph_node(
                    "subgraph_2".to_string(),
                    None,
                    GraphResource {
                        import_uri: format!("file://{}", subgraph_file_path.to_str().unwrap()),
                    },
                ),
            ],
            connections: Some(vec![
                // ext_a sends cmd B to subgraph_2 (should resolve to ext_d via
                // exposed_messages)
                GraphConnection {
                    loc: connection::GraphLoc {
                        app: None,
                        extension: Some("ext_a".to_string()),
                        subgraph: None,
                        selector: None,
                    },
                    cmd: Some(vec![connection::GraphMessageFlow::new(
                        Some("B".to_string()),
                        None,
                        vec![connection::GraphDestination {
                            loc: connection::GraphLoc {
                                app: None,
                                extension: None,
                                subgraph: Some("subgraph_2".to_string()),
                                selector: None,
                            },
                            msg_conversion: None,
                        }],
                        vec![],
                    )]),
                    data: None,
                    audio_frame: None,
                    video_frame: None,
                },
                // subgraph_2 sends cmd H to ext_a (should resolve to ext_c via
                // exposed_messages)
                GraphConnection {
                    loc: connection::GraphLoc {
                        app: None,
                        extension: None,
                        subgraph: Some("subgraph_2".to_string()),
                        selector: None,
                    },
                    cmd: Some(vec![connection::GraphMessageFlow::new(
                        Some("H".to_string()),
                        None,
                        vec![connection::GraphDestination {
                            loc: connection::GraphLoc {
                                app: None,
                                extension: Some("ext_a".to_string()),
                                subgraph: None,
                                selector: None,
                            },
                            msg_conversion: None,
                        }],
                        vec![],
                    )]),
                    data: None,
                    audio_frame: None,
                    video_frame: None,
                },
            ]),
            exposed_messages: None,
            exposed_properties: Some(vec![GraphExposedProperty {
                extension: Some("ext_d".to_string()),
                name: "app_id".to_string(),
                subgraph: None,
            }]),
        };

        // Create a subgraph with exposed_messages
        let subgraph = Graph {
            nodes: vec![
                GraphNode::new_extension_node(
                    "ext_c".to_string(),
                    "addon_c".to_string(),
                    None,
                    None,
                    None,
                ),
                GraphNode::new_extension_node(
                    "ext_d".to_string(),
                    "addon_d".to_string(),
                    None,
                    None,
                    None,
                ),
            ],
            connections: None,
            exposed_messages: Some(vec![
                GraphExposedMessage {
                    msg_type: GraphExposedMessageType::CmdIn,
                    name: "B".to_string(),
                    extension: Some("ext_d".to_string()),
                    subgraph: None,
                },
                GraphExposedMessage {
                    msg_type: GraphExposedMessageType::CmdOut,
                    name: "H".to_string(),
                    extension: Some("ext_c".to_string()),
                    subgraph: None,
                },
            ]),
            exposed_properties: None,
        };

        // Write the subgraph to a file
        let subgraph_json = serde_json::to_string(&subgraph).unwrap();
        fs::write(subgraph_file_path, subgraph_json).unwrap();

        // Flatten the graph
        let flattened = main_graph.flatten_graph(None).await.unwrap().unwrap();

        // Verify results
        assert_eq!(flattened.nodes.len(), 3); // ext_a + 2 from subgraph

        // Verify that all nodes are extension nodes
        assert!(flattened.nodes.iter().all(|node| node.get_type() == GraphNodeType::Extension));

        // Convert to extension nodes
        let extension_nodes = flattened
            .nodes
            .iter()
            .map(|node| match node {
                GraphNode::Extension {
                    content,
                } => content.clone(),
                _ => panic!("Expected extension node, got {node:?}"),
            })
            .collect::<Vec<_>>();

        // Check that original extension is preserved
        assert!(extension_nodes.iter().any(|node| node.name == "ext_a" && node.addon == "addon_a"));

        // Check that subgraph extensions are flattened with prefix
        assert!(extension_nodes
            .iter()
            .any(|node| node.name == "subgraph_2_ext_c" && node.addon == "addon_c"));
        assert!(extension_nodes
            .iter()
            .any(|node| node.name == "subgraph_2_ext_d" && node.addon == "addon_d"));

        // Check that connections are resolved correctly
        let connections = flattened.connections.as_ref().unwrap();
        assert_eq!(connections.len(), 2);

        // Check that subgraph reference in destination is resolved to ext_d
        let connection_to_subgraph =
            connections.iter().find(|conn| conn.loc.extension.as_deref() == Some("ext_a")).unwrap();
        let cmd_flow = &connection_to_subgraph.cmd.as_ref().unwrap()[0];
        assert_eq!(cmd_flow.name.as_deref(), Some("B"));
        assert_eq!(cmd_flow.dest[0].loc.extension.as_ref().unwrap(), "subgraph_2_ext_d");
        assert!(cmd_flow.dest[0].loc.subgraph.is_none());

        // Check that subgraph reference in source is resolved to ext_c
        let connection_from_subgraph = connections
            .iter()
            .find(|conn| conn.loc.extension.as_deref() == Some("subgraph_2_ext_c"))
            .unwrap();
        let cmd_flow = &connection_from_subgraph.cmd.as_ref().unwrap()[0];
        assert_eq!(cmd_flow.name.as_deref(), Some("H"));
        assert_eq!(cmd_flow.dest[0].loc.extension.as_ref().unwrap(), "ext_a");
    }

    #[tokio::test]
    async fn test_flatten_subgraph_field_reference_missing_exposed_message() {
        // Create a temporary directory for the subgraph
        let temp_dir = tempdir().unwrap();
        let subgraph_file_path = temp_dir.path().join("test_subgraph.json");

        // Create a main graph with subgraph field reference
        let main_graph = Graph {
            nodes: vec![
                GraphNode::new_extension_node(
                    "ext_a".to_string(),
                    "addon_a".to_string(),
                    None,
                    None,
                    None,
                ),
                GraphNode::new_subgraph_node(
                    "subgraph_2".to_string(),
                    None,
                    GraphResource {
                        import_uri: format!("file://{}", subgraph_file_path.to_str().unwrap()),
                    },
                ),
            ],
            connections: Some(vec![GraphConnection {
                loc: connection::GraphLoc {
                    app: None,
                    extension: Some("ext_a".to_string()),
                    subgraph: None,
                    selector: None,
                },
                cmd: Some(vec![connection::GraphMessageFlow::new(
                    Some("NonExistentCmd".to_string()),
                    None,
                    vec![connection::GraphDestination {
                        loc: connection::GraphLoc {
                            app: None,
                            extension: None,
                            subgraph: Some("subgraph_2".to_string()),
                            selector: None,
                        },
                        msg_conversion: None,
                    }],
                    vec![],
                )]),
                data: None,
                audio_frame: None,
                video_frame: None,
            }]),
            exposed_messages: None,
            exposed_properties: None,
        };

        // Create a subgraph with exposed_messages that doesn't include the
        // requested message
        let subgraph = Graph {
            nodes: vec![GraphNode::new_extension_node(
                "ext_d".to_string(),
                "addon_d".to_string(),
                None,
                None,
                None,
            )],
            connections: None,
            exposed_messages: Some(vec![GraphExposedMessage {
                msg_type: GraphExposedMessageType::CmdIn,
                name: "TestCmd".to_string(),
                extension: None,
                subgraph: Some("subgraph_2".to_string()),
            }]),
            exposed_properties: None,
        };

        // Write the subgraph to a file
        let subgraph_json = serde_json::to_string(&subgraph).unwrap();
        fs::write(subgraph_file_path, subgraph_json).unwrap();

        // Flatten the graph - should fail
        let result = main_graph.flatten_graph(None).await;
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains(
            "Message 'NonExistentCmd' of type 'CmdIn' is not exposed by subgraph 'subgraph_2'"
        ));
    }

    #[tokio::test]
    async fn test_flatten_subgraph_field_reference_no_exposed_messages() {
        // Create a temporary directory for the subgraph
        let temp_dir = tempdir().unwrap();
        let subgraph_file_path = temp_dir.path().join("test_subgraph.json");

        // Create a main graph with subgraph field reference
        let main_graph = Graph {
            nodes: vec![
                GraphNode::new_extension_node(
                    "ext_a".to_string(),
                    "addon_a".to_string(),
                    None,
                    None,
                    None,
                ),
                GraphNode::new_subgraph_node(
                    "subgraph_2".to_string(),
                    None,
                    GraphResource {
                        import_uri: format!("file://{}", subgraph_file_path.to_str().unwrap()),
                    },
                ),
            ],
            connections: Some(vec![GraphConnection {
                loc: connection::GraphLoc {
                    app: None,
                    extension: Some("ext_a".to_string()),
                    subgraph: None,
                    selector: None,
                },
                cmd: Some(vec![connection::GraphMessageFlow::new(
                    Some("B".to_string()),
                    None,
                    vec![connection::GraphDestination {
                        loc: connection::GraphLoc {
                            app: None,
                            extension: None,
                            subgraph: Some("subgraph_2".to_string()),
                            selector: None,
                        },
                        msg_conversion: None,
                    }],
                    vec![],
                )]),
                data: None,
                audio_frame: None,
                video_frame: None,
            }]),
            exposed_messages: None,
            exposed_properties: None,
        };

        // Create a subgraph without exposed_messages
        let subgraph = Graph {
            nodes: vec![GraphNode::new_extension_node(
                "ext_d".to_string(),
                "addon_d".to_string(),
                None,
                None,
                None,
            )],
            connections: None,
            exposed_messages: None,
            exposed_properties: None,
        };

        // Write the subgraph to a file
        let subgraph_json = serde_json::to_string(&subgraph).unwrap();
        fs::write(subgraph_file_path, subgraph_json).unwrap();

        // Flatten the graph - should fail
        let result = main_graph.flatten_graph(None).await;
        assert!(result.is_err());
        assert!(result
            .unwrap_err()
            .to_string()
            .contains("Subgraph 'subgraph_2' does not have exposed_messages defined"));
    }

    #[tokio::test]
    async fn test_flatten_nested_subgraphs() {
        // Create temporary directories for the subgraphs
        let temp_dir = tempdir().unwrap();
        let subgraph1_file_path = temp_dir.path().join("subgraph1.json");
        let subgraph2_file_path = temp_dir.path().join("subgraph2.json");

        // Create a main graph with a subgraph node
        let main_graph = Graph {
            nodes: vec![
                GraphNode::new_extension_node(
                    "ext_a".to_string(),
                    "addon_a".to_string(),
                    None,
                    None,
                    None,
                ),
                GraphNode::new_subgraph_node(
                    "subgraph_1".to_string(),
                    None,
                    GraphResource {
                        import_uri: format!("file://{}", subgraph1_file_path.to_str().unwrap()),
                    },
                ),
            ],
            connections: Some(vec![GraphConnection {
                loc: connection::GraphLoc {
                    app: None,
                    extension: Some("ext_a".to_string()),
                    subgraph: None,
                    selector: None,
                },
                cmd: Some(vec![connection::GraphMessageFlow::new(
                    Some("TestCmd".to_string()),
                    None,
                    vec![connection::GraphDestination {
                        loc: connection::GraphLoc {
                            app: None,
                            extension: Some("subgraph_1_subgraph_2_ext_z".to_string()),
                            subgraph: None,
                            selector: None,
                        },
                        msg_conversion: None,
                    }],
                    vec![],
                )]),
                data: None,
                audio_frame: None,
                video_frame: None,
            }]),
            exposed_messages: None,
            exposed_properties: None,
        };

        // Create a subgraph that contains another subgraph (nested)
        let subgraph_1 = Graph {
            nodes: vec![
                GraphNode::new_extension_node(
                    "ext_x".to_string(),
                    "addon_x".to_string(),
                    None,
                    None,
                    None,
                ),
                GraphNode::new_subgraph_node(
                    "subgraph_2".to_string(),
                    None,
                    GraphResource {
                        import_uri: format!("file://{}", subgraph2_file_path.to_str().unwrap()),
                    },
                ),
            ],
            connections: Some(vec![GraphConnection {
                loc: connection::GraphLoc {
                    app: None,
                    extension: Some("ext_x".to_string()),
                    subgraph: None,
                    selector: None,
                },
                cmd: Some(vec![connection::GraphMessageFlow::new(
                    Some("InternalCmd".to_string()),
                    None,
                    vec![connection::GraphDestination {
                        loc: connection::GraphLoc {
                            app: None,
                            extension: Some("subgraph_2_ext_z".to_string()),
                            subgraph: None,
                            selector: None,
                        },
                        msg_conversion: None,
                    }],
                    vec![],
                )]),
                data: None,
                audio_frame: None,
                video_frame: None,
            }]),
            exposed_messages: None,
            exposed_properties: None,
        };

        // Create the innermost subgraph
        let subgraph_2 = Graph {
            nodes: vec![
                GraphNode::new_extension_node(
                    "ext_y".to_string(),
                    "addon_y".to_string(),
                    None,
                    None,
                    None,
                ),
                GraphNode::new_extension_node(
                    "ext_z".to_string(),
                    "addon_z".to_string(),
                    None,
                    None,
                    None,
                ),
            ],
            connections: Some(vec![GraphConnection {
                loc: connection::GraphLoc {
                    app: None,
                    extension: Some("ext_y".to_string()),
                    subgraph: None,
                    selector: None,
                },
                cmd: Some(vec![connection::GraphMessageFlow::new(
                    Some("DeepCmd".to_string()),
                    None,
                    vec![connection::GraphDestination {
                        loc: connection::GraphLoc {
                            app: None,
                            extension: Some("ext_z".to_string()),
                            subgraph: None,
                            selector: None,
                        },
                        msg_conversion: None,
                    }],
                    vec![],
                )]),
                data: None,
                audio_frame: None,
                video_frame: None,
            }]),
            exposed_messages: None,
            exposed_properties: None,
        };

        // Write the subgraphs to files
        let subgraph1_json = serde_json::to_string(&subgraph_1).unwrap();
        fs::write(&subgraph1_file_path, subgraph1_json).unwrap();

        let subgraph2_json = serde_json::to_string(&subgraph_2).unwrap();
        fs::write(&subgraph2_file_path, subgraph2_json).unwrap();

        // Flatten the graph - should now work with nested subgraphs
        let flattened = main_graph.flatten_graph(None).await.unwrap().unwrap();

        // Verify results
        assert_eq!(flattened.nodes.len(), 4); // ext_a + ext_x + ext_y + ext_z (all flattened)

        // Verify that all nodes are extension nodes
        assert!(flattened.nodes.iter().all(|node| node.get_type() == GraphNodeType::Extension));

        // Convert to extension nodes
        let extension_nodes = flattened
            .nodes
            .iter()
            .map(|node| match node {
                GraphNode::Extension {
                    content,
                } => content.clone(),
                _ => panic!("Expected extension node, got {node:?}"),
            })
            .collect::<Vec<_>>();

        // Check that original extension is preserved
        assert!(extension_nodes.iter().any(|node| node.name == "ext_a" && node.addon == "addon_a"));

        // Check that nested subgraph extensions are flattened with proper
        // prefixes
        assert!(extension_nodes
            .iter()
            .any(|node| node.name == "subgraph_1_ext_x" && node.addon == "addon_x"));
        assert!(extension_nodes
            .iter()
            .any(|node| node.name == "subgraph_1_subgraph_2_ext_y" && node.addon == "addon_y"));
        assert!(extension_nodes
            .iter()
            .any(|node| node.name == "subgraph_1_subgraph_2_ext_z" && node.addon == "addon_z"));

        // Check that connections are flattened correctly
        let connections = flattened.connections.as_ref().unwrap();
        assert_eq!(connections.len(), 3); // Original + 2 internal connections

        // Check that the main connection references the deeply nested extension
        let main_connection =
            connections.iter().find(|conn| conn.loc.extension.as_deref() == Some("ext_a")).unwrap();
        let cmd_flow = &main_connection.cmd.as_ref().unwrap()[0];
        assert_eq!(cmd_flow.dest[0].loc.extension.as_ref().unwrap(), "subgraph_1_subgraph_2_ext_z");

        // Check internal connections are preserved with proper prefixes
        let internal_connection_1 = connections
            .iter()
            .find(|conn| conn.loc.extension.as_deref() == Some("subgraph_1_ext_x"))
            .unwrap();
        let internal_cmd_flow_1 = &internal_connection_1.cmd.as_ref().unwrap()[0];
        assert_eq!(
            internal_cmd_flow_1.dest[0].loc.extension.as_ref().unwrap(),
            "subgraph_1_subgraph_2_ext_z"
        );

        let internal_connection_2 = connections
            .iter()
            .find(|conn| conn.loc.extension.as_deref() == Some("subgraph_1_subgraph_2_ext_y"))
            .unwrap();
        let internal_cmd_flow_2 = &internal_connection_2.cmd.as_ref().unwrap()[0];
        assert_eq!(
            internal_cmd_flow_2.dest[0].loc.extension.as_ref().unwrap(),
            "subgraph_1_subgraph_2_ext_z"
        );
    }

    #[tokio::test]
    async fn test_flatten_nested_subgraphs_with_exposed_messages() {
        // Create temporary directories for the subgraphs
        let temp_dir = tempdir().unwrap();
        let subgraph1_file_path = temp_dir.path().join("subgraph1.json");
        let subgraph2_file_path = temp_dir.path().join("subgraph2.json");

        // Create a main graph with subgraph field references
        let main_graph = Graph {
            nodes: vec![
                GraphNode::new_extension_node(
                    "ext_a".to_string(),
                    "addon_a".to_string(),
                    None,
                    None,
                    None,
                ),
                GraphNode::new_subgraph_node(
                    "subgraph_1".to_string(),
                    None,
                    GraphResource {
                        import_uri: format!("file://{}", subgraph1_file_path.to_str().unwrap()),
                    },
                ),
            ],
            connections: Some(vec![GraphConnection {
                loc: connection::GraphLoc {
                    app: None,
                    extension: Some("ext_a".to_string()),
                    subgraph: None,
                    selector: None,
                },
                cmd: Some(vec![connection::GraphMessageFlow::new(
                    Some("TestCmd".to_string()),
                    None,
                    vec![connection::GraphDestination {
                        loc: connection::GraphLoc {
                            app: None,
                            extension: None,
                            subgraph: Some("subgraph_1".to_string()),
                            selector: None,
                        },
                        msg_conversion: None,
                    }],
                    vec![],
                )]),
                data: None,
                audio_frame: None,
                video_frame: None,
            }]),
            exposed_messages: None,
            exposed_properties: None,
        };

        // Create a subgraph that contains another subgraph (nested)
        let subgraph_1 = Graph {
            nodes: vec![
                GraphNode::new_extension_node(
                    "ext_x".to_string(),
                    "addon_x".to_string(),
                    None,
                    None,
                    None,
                ),
                GraphNode::new_subgraph_node(
                    "subgraph_2".to_string(),
                    None,
                    GraphResource {
                        import_uri: format!("file://{}", subgraph2_file_path.to_str().unwrap()),
                    },
                ),
            ],
            connections: None,
            exposed_messages: Some(vec![GraphExposedMessage {
                msg_type: GraphExposedMessageType::CmdIn,
                name: "TestCmd".to_string(),
                extension: None,
                subgraph: Some("subgraph_2".to_string()),
            }]),
            exposed_properties: None,
        };

        // Create the innermost subgraph
        let subgraph_2 = Graph {
            nodes: vec![
                GraphNode::new_extension_node(
                    "ext_y".to_string(),
                    "addon_y".to_string(),
                    None,
                    None,
                    None,
                ),
                GraphNode::new_extension_node(
                    "ext_z".to_string(),
                    "addon_z".to_string(),
                    None,
                    None,
                    None,
                ),
            ],
            connections: None,
            exposed_messages: Some(vec![GraphExposedMessage {
                msg_type: GraphExposedMessageType::CmdIn,
                subgraph: None,
                name: "TestCmd".to_string(),
                extension: Some("ext_z".to_string()),
            }]),
            exposed_properties: None,
        };

        // Write the subgraphs to files
        let subgraph1_json = serde_json::to_string(&subgraph_1).unwrap();
        fs::write(&subgraph1_file_path, subgraph1_json).unwrap();

        let subgraph2_json = serde_json::to_string(&subgraph_2).unwrap();
        fs::write(&subgraph2_file_path, subgraph2_json).unwrap();

        // Flatten the graph - should work with nested subgraphs and
        // exposed_messages
        let flattened = main_graph.flatten_graph(None).await.unwrap().unwrap();

        // Verify results
        assert_eq!(flattened.nodes.len(), 4); // ext_a + ext_x + ext_y + ext_z (all flattened)

        // Check that nested subgraph extensions are flattened with proper
        // prefixes
        assert!(flattened.nodes.iter().any(|node| node.get_name() == "subgraph_1_ext_x"));
        assert!(flattened
            .nodes
            .iter()
            .any(|node| node.get_name() == "subgraph_1_subgraph_2_ext_y"));
        assert!(flattened
            .nodes
            .iter()
            .any(|node| node.get_name() == "subgraph_1_subgraph_2_ext_z"));

        // Check that connections are resolved correctly through nested
        // exposed_messages
        let connections = flattened.connections.as_ref().unwrap();
        assert_eq!(connections.len(), 1);

        let main_connection =
            connections.iter().find(|conn| conn.loc.extension.as_deref() == Some("ext_a")).unwrap();
        let cmd_flow = &main_connection.cmd.as_ref().unwrap()[0];
        // The subgraph reference should be resolved to the deeply nested
        // extension
        assert_eq!(cmd_flow.dest[0].loc.extension.as_ref().unwrap(), "subgraph_1_subgraph_2_ext_z");
        assert!(cmd_flow.dest[0].loc.subgraph.is_none());
    }

    #[tokio::test]
    async fn test_flatten_missing_import_uri_error() {
        let main_graph = Graph {
            nodes: vec![GraphNode::new_subgraph_node(
                "subgraph_1".to_string(),
                None,
                GraphResource {
                    import_uri: "".to_string(), // Missing import_uri
                },
            )],
            connections: None,
            exposed_messages: None,
            exposed_properties: None,
        };

        let result = main_graph.flatten_graph(None).await;
        assert!(result.is_err());
        assert!(result
            .unwrap_err()
            .to_string()
            .contains("Subgraph node 'subgraph_1' has an empty import_uri"));
    }

    #[tokio::test]
    async fn test_flatten_subgraph_field_reference_all_message_types() {
        // Create a temporary directory for the subgraph
        let temp_dir = tempdir().unwrap();
        let subgraph_file_path = temp_dir.path().join("test_subgraph.json");

        // Create a main graph with subgraph field references for all message
        // types
        let main_graph = Graph {
            nodes: vec![
                GraphNode::new_extension_node(
                    "ext_a".to_string(),
                    "addon_a".to_string(),
                    None,
                    None,
                    None,
                ),
                GraphNode::new_subgraph_node(
                    "subgraph_3".to_string(),
                    None,
                    GraphResource {
                        import_uri: format!("file://{}", subgraph_file_path.to_str().unwrap()),
                    },
                ),
            ],
            connections: Some(vec![
                // ext_a sends various message types to subgraph_3
                GraphConnection {
                    loc: connection::GraphLoc {
                        app: None,
                        extension: Some("ext_a".to_string()),
                        subgraph: None,
                        selector: None,
                    },
                    cmd: Some(vec![connection::GraphMessageFlow::new(
                        Some("TestCmd".to_string()),
                        None,
                        vec![connection::GraphDestination {
                            loc: connection::GraphLoc {
                                app: None,
                                extension: None,
                                subgraph: Some("subgraph_3".to_string()),
                                selector: None,
                            },
                            msg_conversion: None,
                        }],
                        vec![],
                    )]),
                    data: Some(vec![connection::GraphMessageFlow::new(
                        Some("TestData".to_string()),
                        None,
                        vec![connection::GraphDestination {
                            loc: connection::GraphLoc {
                                app: None,
                                extension: None,
                                subgraph: Some("subgraph_3".to_string()),
                                selector: None,
                            },
                            msg_conversion: None,
                        }],
                        vec![],
                    )]),
                    audio_frame: Some(vec![connection::GraphMessageFlow::new(
                        Some("TestAudio".to_string()),
                        None,
                        vec![connection::GraphDestination {
                            loc: connection::GraphLoc {
                                app: None,
                                extension: None,
                                subgraph: Some("subgraph_3".to_string()),
                                selector: None,
                            },
                            msg_conversion: None,
                        }],
                        vec![],
                    )]),
                    video_frame: Some(vec![connection::GraphMessageFlow::new(
                        Some("TestVideo".to_string()),
                        None,
                        vec![connection::GraphDestination {
                            loc: connection::GraphLoc {
                                app: None,
                                extension: None,
                                subgraph: Some("subgraph_3".to_string()),
                                selector: None,
                            },
                            msg_conversion: None,
                        }],
                        vec![],
                    )]),
                },
                // subgraph_3 sends various message types to ext_a
                GraphConnection {
                    loc: connection::GraphLoc {
                        app: None,
                        extension: None,
                        subgraph: Some("subgraph_3".to_string()),
                        selector: None,
                    },
                    cmd: Some(vec![connection::GraphMessageFlow::new(
                        Some("ResponseCmd".to_string()),
                        None,
                        vec![connection::GraphDestination {
                            loc: connection::GraphLoc {
                                app: None,
                                extension: Some("ext_a".to_string()),
                                subgraph: None,
                                selector: None,
                            },
                            msg_conversion: None,
                        }],
                        vec![],
                    )]),
                    data: Some(vec![connection::GraphMessageFlow::new(
                        Some("ResponseData".to_string()),
                        None,
                        vec![connection::GraphDestination {
                            loc: connection::GraphLoc {
                                app: None,
                                extension: Some("ext_a".to_string()),
                                subgraph: None,
                                selector: None,
                            },
                            msg_conversion: None,
                        }],
                        vec![],
                    )]),
                    audio_frame: Some(vec![connection::GraphMessageFlow::new(
                        Some("ResponseAudio".to_string()),
                        None,
                        vec![connection::GraphDestination {
                            loc: connection::GraphLoc {
                                app: None,
                                extension: Some("ext_a".to_string()),
                                subgraph: None,
                                selector: None,
                            },
                            msg_conversion: None,
                        }],
                        vec![],
                    )]),
                    video_frame: Some(vec![connection::GraphMessageFlow::new(
                        Some("ResponseVideo".to_string()),
                        None,
                        vec![connection::GraphDestination {
                            loc: connection::GraphLoc {
                                app: None,
                                extension: Some("ext_a".to_string()),
                                subgraph: None,
                                selector: None,
                            },
                            msg_conversion: None,
                        }],
                        vec![],
                    )]),
                },
            ]),
            exposed_messages: None,
            exposed_properties: None,
        };

        // Create a subgraph with exposed_messages for all message types
        let subgraph = Graph {
            nodes: vec![
                GraphNode::new_extension_node(
                    "ext_input".to_string(),
                    "addon_input".to_string(),
                    None,
                    None,
                    None,
                ),
                GraphNode::new_extension_node(
                    "ext_output".to_string(),
                    "addon_output".to_string(),
                    None,
                    None,
                    None,
                ),
            ],
            connections: None,
            exposed_messages: Some(vec![
                // Input messages (from external to subgraph)
                GraphExposedMessage {
                    msg_type: GraphExposedMessageType::CmdIn,
                    name: "TestCmd".to_string(),
                    extension: Some("ext_input".to_string()),
                    subgraph: None,
                },
                GraphExposedMessage {
                    msg_type: GraphExposedMessageType::DataIn,
                    name: "TestData".to_string(),
                    extension: Some("ext_input".to_string()),
                    subgraph: None,
                },
                GraphExposedMessage {
                    msg_type: GraphExposedMessageType::AudioFrameIn,
                    name: "TestAudio".to_string(),
                    extension: Some("ext_input".to_string()),
                    subgraph: None,
                },
                GraphExposedMessage {
                    msg_type: GraphExposedMessageType::VideoFrameIn,
                    name: "TestVideo".to_string(),
                    extension: Some("ext_input".to_string()),
                    subgraph: None,
                },
                // Output messages (from subgraph to external)
                GraphExposedMessage {
                    msg_type: GraphExposedMessageType::CmdOut,
                    name: "ResponseCmd".to_string(),
                    extension: Some("ext_output".to_string()),
                    subgraph: None,
                },
                GraphExposedMessage {
                    msg_type: GraphExposedMessageType::DataOut,
                    name: "ResponseData".to_string(),
                    extension: Some("ext_output".to_string()),
                    subgraph: None,
                },
                GraphExposedMessage {
                    msg_type: GraphExposedMessageType::AudioFrameOut,
                    name: "ResponseAudio".to_string(),
                    extension: Some("ext_output".to_string()),
                    subgraph: None,
                },
                GraphExposedMessage {
                    msg_type: GraphExposedMessageType::VideoFrameOut,
                    name: "ResponseVideo".to_string(),
                    extension: Some("ext_output".to_string()),
                    subgraph: None,
                },
            ]),
            exposed_properties: None,
        };

        // Write the subgraph to a file
        let subgraph_json = serde_json::to_string(&subgraph).unwrap();
        fs::write(subgraph_file_path, subgraph_json).unwrap();

        // Flatten the graph
        let flattened = main_graph.flatten_graph(None).await.unwrap().unwrap();

        // Verify results
        assert_eq!(flattened.nodes.len(), 3); // ext_a + 2 from subgraph

        // Check that connections are resolved correctly
        let connections = flattened.connections.as_ref().unwrap();
        assert_eq!(connections.len(), 2); // 1 original + 1 grouped connection from subgraph source

        // Check that subgraph references in destinations are resolved correctly
        let connection_to_subgraph =
            connections.iter().find(|conn| conn.loc.extension.as_deref() == Some("ext_a")).unwrap();

        // Verify cmd destination
        let cmd_flow = &connection_to_subgraph.cmd.as_ref().unwrap()[0];
        assert_eq!(cmd_flow.name.as_deref(), Some("TestCmd"));
        assert_eq!(cmd_flow.dest[0].loc.extension.as_ref().unwrap(), "subgraph_3_ext_input");

        // Verify data destination
        let data_flow = &connection_to_subgraph.data.as_ref().unwrap()[0];
        assert_eq!(data_flow.name.as_deref(), Some("TestData"));
        assert_eq!(data_flow.dest[0].loc.extension.as_ref().unwrap(), "subgraph_3_ext_input");

        // Verify audio_frame destination
        let audio_flow = &connection_to_subgraph.audio_frame.as_ref().unwrap()[0];
        assert_eq!(audio_flow.name.as_deref(), Some("TestAudio"));
        assert_eq!(audio_flow.dest[0].loc.extension.as_ref().unwrap(), "subgraph_3_ext_input");

        // Verify video_frame destination
        let video_flow = &connection_to_subgraph.video_frame.as_ref().unwrap()[0];
        assert_eq!(video_flow.name.as_deref(), Some("TestVideo"));
        assert_eq!(video_flow.dest[0].loc.extension.as_ref().unwrap(), "subgraph_3_ext_input");

        // Check that subgraph references in sources are resolved correctly
        // Now we should have 1 grouped connection with all message types from
        // the same extension

        // Find the grouped connection from subgraph
        let grouped_connection = connections
            .iter()
            .find(|conn| conn.loc.extension.as_deref() == Some("subgraph_3_ext_output"))
            .unwrap();

        // Verify all message types are present in the same connection
        assert!(grouped_connection.cmd.is_some());
        assert!(grouped_connection.data.is_some());
        assert!(grouped_connection.audio_frame.is_some());
        assert!(grouped_connection.video_frame.is_some());

        // Verify cmd flow
        let cmd_flow = &grouped_connection.cmd.as_ref().unwrap()[0];
        assert_eq!(cmd_flow.name.as_deref(), Some("ResponseCmd"));
        assert_eq!(cmd_flow.dest[0].loc.extension.as_ref().unwrap(), "ext_a");

        // Verify data flow
        let data_flow = &grouped_connection.data.as_ref().unwrap()[0];
        assert_eq!(data_flow.name.as_deref(), Some("ResponseData"));
        assert_eq!(data_flow.dest[0].loc.extension.as_ref().unwrap(), "ext_a");

        // Verify audio_frame flow
        let audio_flow = &grouped_connection.audio_frame.as_ref().unwrap()[0];
        assert_eq!(audio_flow.name.as_deref(), Some("ResponseAudio"));
        assert_eq!(audio_flow.dest[0].loc.extension.as_ref().unwrap(), "ext_a");

        // Verify video_frame flow
        let video_flow = &grouped_connection.video_frame.as_ref().unwrap()[0];
        assert_eq!(video_flow.name.as_deref(), Some("ResponseVideo"));
        assert_eq!(video_flow.dest[0].loc.extension.as_ref().unwrap(), "ext_a");
    }

    #[tokio::test]
    async fn test_flatten_subgraph_field_reference_exposed_properties() {
        // Create a temporary directory for the subgraph
        let temp_dir = tempdir().unwrap();
        let subgraph_file_path = temp_dir.path().join("test_subgraph.json");

        // Create a main graph with subgraph field references in
        // exposed_properties
        let main_graph = Graph {
            nodes: vec![
                GraphNode::new_extension_node(
                    "ext_a".to_string(),
                    "addon_a".to_string(),
                    None,
                    None,
                    None,
                ),
                GraphNode::new_subgraph_node(
                    "subgraph_1".to_string(),
                    None,
                    GraphResource {
                        import_uri: format!("file://{}", subgraph_file_path.to_str().unwrap()),
                    },
                ),
            ],
            connections: None,
            exposed_messages: None,
            exposed_properties: Some(vec![
                // Extension-based exposed property
                GraphExposedProperty {
                    extension: Some("ext_a".to_string()),
                    name: "config_a".to_string(),
                    subgraph: None,
                },
                // Subgraph-based exposed property
                GraphExposedProperty {
                    extension: None,
                    name: "config_b".to_string(),
                    subgraph: Some("subgraph_1".to_string()),
                },
            ]),
        };

        // Create a subgraph with exposed_properties
        let subgraph = Graph {
            nodes: vec![
                GraphNode::new_extension_node(
                    "ext_x".to_string(),
                    "addon_x".to_string(),
                    None,
                    None,
                    None,
                ),
                GraphNode::new_extension_node(
                    "ext_y".to_string(),
                    "addon_y".to_string(),
                    None,
                    None,
                    None,
                ),
            ],
            connections: None,
            exposed_messages: None,
            exposed_properties: Some(vec![GraphExposedProperty {
                extension: Some("ext_y".to_string()),
                name: "config_b".to_string(),
                subgraph: None,
            }]),
        };

        // Write the subgraph to a file
        let subgraph_json = serde_json::to_string(&subgraph).unwrap();
        fs::write(subgraph_file_path, subgraph_json).unwrap();

        // Flatten the graph with preserve_exposed_info = true
        let flattened = Graph::flatten_subgraphs(&main_graph, None, true).await.unwrap().unwrap();

        // Verify results
        assert_eq!(flattened.nodes.len(), 3); // ext_a + 2 from subgraph

        // Verify that all nodes are extension nodes
        assert!(flattened.nodes.iter().all(|node| node.get_type() == GraphNodeType::Extension));

        // Check that exposed_properties are updated correctly
        let exposed_properties = flattened.exposed_properties.as_ref().unwrap();
        assert_eq!(exposed_properties.len(), 2);

        // Check that extension-based exposed property is preserved
        let ext_a_property = exposed_properties
            .iter()
            .find(|prop| prop.extension.as_deref() == Some("ext_a"))
            .unwrap();
        assert_eq!(ext_a_property.name, "config_a");
        assert!(ext_a_property.subgraph.is_none());

        // Check that subgraph-based exposed property is expanded
        let expanded_property = exposed_properties
            .iter()
            .find(|prop| prop.extension.as_deref() == Some("subgraph_1_ext_y"))
            .unwrap();
        assert_eq!(expanded_property.name, "config_b");
        assert!(expanded_property.subgraph.is_none());
    }

    /// Builds a main graph whose only node imports `subgraph_path`.
    fn main_graph_importing(subgraph_path: &str) -> Graph {
        Graph {
            nodes: vec![GraphNode::new_subgraph_node(
                "sg".to_string(),
                None,
                GraphResource { import_uri: format!("file://{subgraph_path}") },
            )],
            connections: None,
            exposed_messages: None,
            exposed_properties: None,
        }
    }

    /// A reversed connection (`source`) written inside an imported subgraph
    /// must be converted to a forward connection, with the subgraph name
    /// prefix applied, just like one written in the main graph.
    #[tokio::test]
    async fn test_flatten_subgraph_with_reversed_connection() {
        let temp_dir = tempdir().unwrap();
        let subgraph_file_path = temp_dir.path().join("subgraph_reversed.json");

        // Inside the subgraph: ext_a --hello--> ext_b, written in reverse form.
        fs::write(
            &subgraph_file_path,
            r#"{
              "nodes": [
                {"type": "extension", "name": "ext_a", "addon": "addon_a"},
                {"type": "extension", "name": "ext_b", "addon": "addon_b"}
              ],
              "connections": [
                {
                  "extension": "ext_b",
                  "cmd": [{"name": "hello", "source": [{"extension": "ext_a"}]}]
                }
              ]
            }"#,
        )
        .unwrap();

        let main_graph = main_graph_importing(subgraph_file_path.to_str().unwrap());
        let flattened = main_graph.flatten_graph(None).await.unwrap().unwrap();

        let connections = flattened.connections.as_ref().unwrap();

        // No reversed connection may survive flattening.
        assert!(
            connections
                .iter()
                .flat_map(|conn| conn.cmd.iter().flatten())
                .all(|flow| flow.source.is_empty()),
            "reversed connection inside the subgraph was not converted: {connections:?}"
        );

        // It must have become sg_ext_a --hello--> sg_ext_b.
        let forward = connections
            .iter()
            .find(|conn| conn.loc.extension.as_deref() == Some("sg_ext_a"))
            .expect("no forward connection originating from sg_ext_a");

        let flow = forward
            .cmd
            .as_ref()
            .unwrap()
            .iter()
            .find(|flow| flow.name.as_deref() == Some("hello"))
            .expect("no 'hello' cmd flow");

        assert_eq!(flow.dest.len(), 1);
        assert_eq!(flow.dest[0].loc.extension.as_deref(), Some("sg_ext_b"));
    }

    /// A `names` array written inside an imported subgraph must be expanded
    /// into individual `name` items.
    #[tokio::test]
    async fn test_flatten_subgraph_with_names_array() {
        let temp_dir = tempdir().unwrap();
        let subgraph_file_path = temp_dir.path().join("subgraph_names.json");

        fs::write(
            &subgraph_file_path,
            r#"{
              "nodes": [
                {"type": "extension", "name": "ext_a", "addon": "addon_a"},
                {"type": "extension", "name": "ext_b", "addon": "addon_b"}
              ],
              "connections": [
                {
                  "extension": "ext_a",
                  "cmd": [{"names": ["hello", "world"], "dest": [{"extension": "ext_b"}]}]
                }
              ]
            }"#,
        )
        .unwrap();

        let main_graph = main_graph_importing(subgraph_file_path.to_str().unwrap());
        let flattened = main_graph.flatten_graph(None).await.unwrap().unwrap();

        let connections = flattened.connections.as_ref().unwrap();
        let flows: Vec<_> = connections.iter().flat_map(|conn| conn.cmd.iter().flatten()).collect();

        assert!(
            flows.iter().all(|flow| flow.names.is_none()),
            "'names' inside the subgraph was not expanded: {flows:?}"
        );

        let mut names: Vec<&str> = flows.iter().filter_map(|flow| flow.name.as_deref()).collect();
        names.sort_unstable();
        assert_eq!(names, vec!["hello", "world"]);

        for flow in &flows {
            assert_eq!(flow.dest.len(), 1);
            assert_eq!(flow.dest[0].loc.extension.as_deref(), Some("sg_ext_b"));
        }
    }

    /// A selector node written inside an imported subgraph must be resolved to
    /// the nodes it matches and removed, instead of reaching the flattening
    /// logic and panicking as a non-extension node.
    #[tokio::test]
    async fn test_flatten_subgraph_with_selector() {
        let temp_dir = tempdir().unwrap();
        let subgraph_file_path = temp_dir.path().join("subgraph_selector.json");

        fs::write(
            &subgraph_file_path,
            r#"{
              "nodes": [
                {"type": "extension", "name": "ext_a", "addon": "addon_a"},
                {"type": "extension", "name": "ext_b", "addon": "addon_b"},
                {
                  "type": "selector",
                  "name": "targets",
                  "filter": {"field": "name", "operator": "exact", "value": "ext_b"}
                }
              ],
              "connections": [
                {
                  "extension": "ext_a",
                  "cmd": [{"name": "hello", "dest": [{"selector": "targets"}]}]
                }
              ]
            }"#,
        )
        .unwrap();

        let main_graph = main_graph_importing(subgraph_file_path.to_str().unwrap());
        let flattened = main_graph.flatten_graph(None).await.unwrap().unwrap();

        // The selector node must not survive into the flattened graph.
        assert!(flattened.nodes.iter().all(|node| node.get_type() == GraphNodeType::Extension));
        assert_eq!(flattened.nodes.len(), 2);

        let connections = flattened.connections.as_ref().unwrap();
        let flow = connections
            .iter()
            .find(|conn| conn.loc.extension.as_deref() == Some("sg_ext_a"))
            .and_then(|conn| conn.cmd.as_ref())
            .and_then(|flows| flows.iter().find(|flow| flow.name.as_deref() == Some("hello")))
            .expect("no 'hello' cmd flow from sg_ext_a");

        assert_eq!(flow.dest.len(), 1);
        assert_eq!(flow.dest[0].loc.extension.as_deref(), Some("sg_ext_b"));
        assert!(flow.dest[0].loc.selector.is_none());
    }
}
