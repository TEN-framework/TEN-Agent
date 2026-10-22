//
// Copyright © 2025 Agora
// This file is part of TEN Framework, an open source project.
// Licensed under the Apache License, Version 2.0, with certain conditions.
// Refer to the "LICENSE" file in the root directory for more information.
//
mod exposed_message;
mod flatten_integration;
mod graph_info;
mod import_uri;
mod loc;
mod names_expansion;
mod reverse;
mod selector;
mod subgraph;

#[cfg(test)]
mod tests {
    use std::collections::HashMap;

    use ten_rust::{
        constants::{
            ERR_MSG_GRAPH_APP_FIELD_EMPTY, ERR_MSG_GRAPH_APP_FIELD_SHOULD_BE_DECLARED,
            ERR_MSG_GRAPH_APP_FIELD_SHOULD_NOT_BE_DECLARED,
            ERR_MSG_GRAPH_LOCALHOST_FORBIDDEN_IN_MULTI_APP_MODE,
            ERR_MSG_GRAPH_LOCALHOST_FORBIDDEN_IN_SINGLE_APP_MODE,
        },
        graph::{
            graph_info::GraphContent,
            node::{FilterOperator, GraphNode},
            Graph,
        },
        pkg_info::property::parse_property_from_str,
    };

    #[tokio::test]
    async fn test_predefined_graph_has_no_extensions() {
        let property_json_str = include_str!("../../test_data/predefined_graph_no_extensions.json");

        let mut graphs_cache = HashMap::new();

        parse_property_from_str(property_json_str, &mut graphs_cache, None, None, None)
            .await
            .unwrap();
        let (_, graph_info) = graphs_cache.into_iter().next().unwrap();
        let graph = &graph_info.graph;
        let result = graph.graph.static_check();

        assert!(result.is_err());
        println!("Error: {:?}", result.err().unwrap());
    }

    #[tokio::test]
    async fn test_predefined_graph_has_extension_duplicated() {
        let property_str =
            include_str!("../../test_data/predefined_graph_has_duplicated_extension.json");

        let mut graphs_cache = HashMap::new();

        parse_property_from_str(property_str, &mut graphs_cache, None, None, None).await.unwrap();
        let (_, graph_info) = graphs_cache.into_iter().next().unwrap();
        let graph = &graph_info.graph;
        let result = graph.graph.static_check();

        assert!(result.is_err());
        println!("Error: {:?}", result.err().unwrap());
    }

    #[tokio::test]
    async fn test_start_graph_cmd_has_extension_duplicated() {
        let cmd_str = include_str!("../../test_data/start_graph_cmd_has_duplicated_extension.json");

        let graph: Graph = Graph::from_str_with_base_dir(cmd_str, None).await.unwrap();
        let result = graph.static_check();
        assert!(result.is_err());
        println!("Error: {:?}", result.err().unwrap());
    }

    #[tokio::test]
    async fn test_predefined_graph_connection_src_not_found() {
        let property_str =
            include_str!("../../test_data/predefined_graph_connection_src_not_found.json");

        let mut graphs_cache = HashMap::new();

        parse_property_from_str(property_str, &mut graphs_cache, None, None, None).await.unwrap();
        let (_, graph_info) = graphs_cache.into_iter().next().unwrap();
        let result = graph_info.graph.graph.check_connection_extensions_exist();

        assert!(result.is_err());
        println!("Error: {:?}", result.err().unwrap());
    }

    #[tokio::test]
    async fn test_predefined_graph_connection_dest_not_found() {
        let property_str =
            include_str!("../../test_data/predefined_graph_connection_dest_not_found.json");

        let mut graphs_cache = HashMap::new();

        parse_property_from_str(property_str, &mut graphs_cache, None, None, None).await.unwrap();
        let (_, graph_info) = graphs_cache.into_iter().next().unwrap();
        let result = graph_info.graph.graph.check_connection_extensions_exist();

        assert!(result.is_err());
        println!("Error: {:?}", result.err().unwrap());
    }

    #[tokio::test]
    async fn test_predefined_graph_node_app_localhost() {
        let property_str =
            include_str!("../../test_data/predefined_graph_connection_app_localhost.json");

        let mut graphs_cache = HashMap::new();

        let property =
            parse_property_from_str(property_str, &mut graphs_cache, None, None, None).await;

        // 'localhost' is not allowed in graph definition.
        assert!(property.is_err());
        println!("Error: {property:?}");

        let msg = property.err().unwrap().to_string();
        assert!(msg.contains(ERR_MSG_GRAPH_LOCALHOST_FORBIDDEN_IN_SINGLE_APP_MODE));
    }

    #[tokio::test]
    async fn test_start_graph_cmd_single_app_node_app_localhost() {
        let graph_str =
            include_str!("../../test_data/start_graph_cmd_single_app_node_app_localhost.json");

        let graph = Graph::from_str_with_base_dir(graph_str, None).await;

        // 'localhost' is not allowed in graph definition.
        assert!(graph.is_err());
        println!("Error: {graph:?}");

        let msg = graph.err().unwrap().to_string();
        assert!(msg.contains(ERR_MSG_GRAPH_LOCALHOST_FORBIDDEN_IN_SINGLE_APP_MODE));
    }

    #[tokio::test]
    async fn test_start_graph_cmd_multi_apps_node_app_localhost() {
        let graph_str =
            include_str!("../../test_data/start_graph_cmd_multi_apps_node_app_localhost.json");
        let graph = Graph::from_str_with_base_dir(graph_str, None).await;

        // 'localhost' is not allowed in graph definition.
        assert!(graph.is_err());
        println!("Error: {graph:?}");

        let msg = graph.err().unwrap().to_string();
        assert!(msg.contains(ERR_MSG_GRAPH_LOCALHOST_FORBIDDEN_IN_MULTI_APP_MODE));
    }

    #[tokio::test]
    async fn test_predefined_graph_connection_app_localhost() {
        let property_str =
            include_str!("../../test_data/predefined_graph_connection_app_localhost.json");
        let mut graphs_cache = HashMap::new();
        let property =
            parse_property_from_str(property_str, &mut graphs_cache, None, None, None).await;
        // 'localhost' is not allowed in graph definition.
        assert!(property.is_err());
        println!("Error: {property:?}");

        let msg = property.err().unwrap().to_string();
        assert!(msg.contains(ERR_MSG_GRAPH_LOCALHOST_FORBIDDEN_IN_SINGLE_APP_MODE));
    }

    #[tokio::test]
    async fn test_predefined_graph_app_in_nodes_not_all_declared() {
        let property_str =
            include_str!("../../test_data/predefined_graph_app_in_nodes_not_all_declared.json");
        let mut graphs_cache = HashMap::new();
        let property =
            parse_property_from_str(property_str, &mut graphs_cache, None, None, None).await;
        // Either all nodes should have 'app' declared, or none should, but not
        // a mix of both.
        assert!(property.is_err());
        println!("Error: {property:?}");

        let msg = property.err().unwrap().to_string();
        assert!(msg.contains(
            "Either all nodes should have 'app' declared, or none should, but not a mix of both."
        ));
    }

    #[tokio::test]
    async fn test_predefined_graph_app_in_connections_not_all_declared() {
        let property_str = include_str!(
            "../../test_data/predefined_graph_app_in_connections_not_all_declared.json"
        );
        let mut graphs_cache = HashMap::new();
        let property =
            parse_property_from_str(property_str, &mut graphs_cache, None, None, None).await;
        // The 'app' can not be none, as it has been declared in nodes.
        assert!(property.is_err());
        println!("Error: {property:?}");

        let msg = property.err().unwrap().to_string();
        assert!(msg.contains(ERR_MSG_GRAPH_APP_FIELD_SHOULD_BE_DECLARED));
    }

    #[tokio::test]
    async fn test_predefined_graph_app_in_connections_should_not_declared() {
        let property_str = include_str!(
            "../../test_data/predefined_graph_app_in_connections_should_not_declared.json"
        );
        let mut graphs_cache = HashMap::new();
        let property =
            parse_property_from_str(property_str, &mut graphs_cache, None, None, None).await;
        // The 'app' should not be declared, as not any node has declared it.
        assert!(property.is_err());
        println!("Error: {property:?}");

        let msg = property.err().unwrap().to_string();
        assert!(msg.contains(ERR_MSG_GRAPH_APP_FIELD_SHOULD_NOT_BE_DECLARED));
    }

    #[tokio::test]
    async fn test_predefined_graph_app_in_dest_not_all_declared() {
        let property_str =
            include_str!("../../test_data/predefined_graph_app_in_dest_not_all_declared.json");
        let mut graphs_cache = HashMap::new();
        let property =
            parse_property_from_str(property_str, &mut graphs_cache, None, None, None).await;
        // The 'app' can not be none, as it has been declared in nodes.
        assert!(property.is_err());
        println!("Error: {property:?}");

        let msg = property.err().unwrap().to_string();
        assert!(msg.contains(ERR_MSG_GRAPH_APP_FIELD_SHOULD_BE_DECLARED));
    }

    #[tokio::test]
    async fn test_predefined_graph_app_in_dest_should_not_declared() {
        let property_str =
            include_str!("../../test_data/predefined_graph_app_in_dest_should_not_declared.json");
        let mut graphs_cache = HashMap::new();
        let property =
            parse_property_from_str(property_str, &mut graphs_cache, None, None, None).await;

        // The 'app' should not be declared, as not any node has declared it.
        assert!(property.is_err());
        println!("Error: {property:?}");

        let msg = property.err().unwrap().to_string();
        assert!(msg.contains(ERR_MSG_GRAPH_APP_FIELD_SHOULD_NOT_BE_DECLARED));
    }

    #[tokio::test]
    async fn test_graph_same_extension_in_two_section_of_connections() {
        let graph_str =
            include_str!("../../test_data/graph_same_extension_in_two_section_of_connections.json");

        let graph = Graph::from_str_with_base_dir(graph_str, None).await.unwrap();

        let result = graph.check_extension_uniqueness_in_connections();

        assert!(result.is_err());
        println!("Error: {result:?}");

        let msg = result.err().unwrap().to_string();
        assert!(msg
            .contains("extension 'some_extension' is defined in connection[0] and connection[1]"));
    }

    #[tokio::test]
    async fn test_graph_duplicated_cmd_name_in_one_connection() {
        let graph_str =
            include_str!("../../test_data/graph_duplicated_cmd_name_in_one_connection.json");

        let graph = Graph::from_str_with_base_dir(graph_str, None).await.unwrap();
        let result = graph.check_message_names();
        assert!(result.is_err());
        println!("Error: {result:?}");

        let msg = result.err().unwrap().to_string();
        assert!(msg.contains("'hello' is defined in flow[0] and flow[1]"));
    }

    #[tokio::test]
    async fn test_graph_messages_same_name_in_different_type_are_ok() {
        let graph_str =
            include_str!("../../test_data/graph_messages_same_name_in_different_type_are_ok.json");

        let graph = Graph::from_str_with_base_dir(graph_str, None).await.unwrap();
        let result = graph.check_message_names();
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_graph_app_can_not_be_empty_string() {
        let graph_str = include_str!("../../test_data/graph_app_can_not_be_empty_string.json");
        let graph = Graph::from_str_with_base_dir(graph_str, None).await;

        // The 'app' can not be empty string.
        assert!(graph.is_err());
        println!("Error: {graph:?}");

        let msg = graph.err().unwrap().to_string();
        assert!(msg.contains(ERR_MSG_GRAPH_APP_FIELD_EMPTY));
    }

    #[tokio::test]
    async fn test_graph_message_conversion_fixed_value() {
        let graph_str = include_str!("../../test_data/graph_message_conversion_fixed_value.json");
        let graph = Graph::from_str_with_base_dir(graph_str, None).await.unwrap();

        let connections = graph.connections.unwrap();
        let cmd = connections.first().unwrap().cmd.as_ref().unwrap().first().unwrap();
        let msg_conversion = cmd.dest.first().unwrap().msg_conversion.as_ref().unwrap();
        let rules = &msg_conversion.msg.as_ref().unwrap().rules.rules;
        assert_eq!(rules.len(), 4);
        assert_eq!(rules[1].value.as_ref().unwrap().as_str().unwrap(), "hello");
        assert!(rules[2].value.as_ref().unwrap().as_bool().unwrap());
    }

    #[tokio::test]
    async fn test_graph_from_str_with_base_dir_valid_json() {
        let input_json = r#"{
            "nodes": [
                {
                    "type": "extension",
                    "name": "test_extension",
                    "addon": "test_addon"
                }
            ]
        }"#;

        let result = Graph::from_str_with_base_dir(input_json, None).await;
        assert!(result.is_ok());

        let graph = result.unwrap();
        assert_eq!(graph.nodes.len(), 1);
        assert_eq!(graph.nodes[0].get_name(), "test_extension");

        // Verify the graph can be serialized back to JSON
        let serialized = serde_json::to_string(&graph);
        assert!(serialized.is_ok());

        let parsed: serde_json::Value = serde_json::from_str(&serialized.unwrap()).unwrap();
        assert!(parsed.is_object());
        assert!(parsed["nodes"].is_array());
    }

    #[tokio::test]
    async fn test_graph_from_str_with_base_dir_invalid_json() {
        let input_json = "invalid json";

        let result = Graph::from_str_with_base_dir(input_json, None).await;
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_graph_from_str_with_base_dir_empty_graph() {
        let input_json = r#"{
            "nodes": []
        }"#;

        let result = Graph::from_str_with_base_dir(input_json, None).await;
        assert!(result.is_ok());

        let graph = result.unwrap();
        assert_eq!(graph.nodes.len(), 0);

        // Verify the graph can be serialized back to JSON
        let serialized = serde_json::to_string(&graph).unwrap();
        let parsed: serde_json::Value = serde_json::from_str(&serialized).unwrap();
        assert!(parsed.is_object());

        // As the 'nodes' array is empty, it will not be serialized.
        assert_eq!(parsed.as_object().unwrap().len(), 0);
    }

    #[tokio::test]
    async fn test_graph_from_str_with_base_dir_with_base_dir() {
        let input_json = r#"{
            "nodes": [
                {
                    "type": "extension",
                    "name": "test_extension",
                    "addon": "test_addon"
                }
            ]
        }"#;

        let result = Graph::from_str_with_base_dir(input_json, Some("/some/base/dir")).await;
        assert!(result.is_ok());

        let graph = result.unwrap();
        assert_eq!(graph.nodes.len(), 1);
        assert_eq!(graph.nodes[0].get_name(), "test_extension");
    }

    #[tokio::test]
    async fn test_graph_from_str_with_base_dir_malformed_structure() {
        let input_json = r#"{
            "nodes": [
                {
                    "type": "extension",
                    "name": "test_extension"
                }
            ]
        }"#;

        let result = Graph::from_str_with_base_dir(input_json, None).await;
        // This should fail during validation because addon field is missing
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_graph_connection_with_source() {
        let graph_str =
            include_str!("../../test_data/graph_with_sources/graph_connection_with_source.json");

        let mut graph_content = serde_json::from_str::<GraphContent>(graph_str).unwrap();

        let _ = graph_content.validate_and_complete_and_flatten(None).await;

        let graph = graph_content.flattened_graph.as_ref().unwrap();

        let connections = graph.connections.as_ref().unwrap();
        let loc = &connections.first().unwrap().loc;
        assert_eq!(loc.extension, Some("another_ext".to_string()));

        let cmd = connections.first().unwrap().cmd.as_ref().unwrap().first().unwrap();
        let source = &cmd.source;
        assert!(source.is_empty());

        let dest = cmd.dest.first().unwrap();
        let loc = &dest.loc;
        assert_eq!(loc.extension, Some("some_extension".to_string()));
    }

    #[tokio::test]
    async fn test_graph_result_conversion_in_not_allowed_flow() {
        let graph_str =
            include_str!("../../test_data/graph_result_conversion_in_not_allowed_flow.json");

        let graph = Graph::from_str_and_validate(graph_str).unwrap();

        let result = graph.static_check();
        assert!(result.is_err());
        println!("Error: {result:?}");

        let msg = result.err().unwrap().to_string();
        assert!(msg.contains("result conversion is not allowed for data out msg"));
    }

    #[tokio::test]
    async fn test_graph_selector_node() {
        let graph_str =
            include_str!("../../test_data/graph_with_selector/graph_with_selector_1.json");

        let graph = serde_json::from_str::<Graph>(graph_str).unwrap();

        // Get all selector nodes
        let selector_nodes = graph
            .nodes
            .iter()
            .filter(|node| matches!(node, GraphNode::Selector { .. }))
            .collect::<Vec<_>>();
        assert_eq!(selector_nodes.len(), 3);

        // Find the selector node with name selector_for_ext_1_and_2
        let selector_node = selector_nodes
            .iter()
            .find(|node| node.get_name() == "selector_for_ext_1_and_2")
            .unwrap();

        let selector_node = selector_node.as_selector_node().unwrap();
        let filter = &selector_node.filter.as_and_filter().unwrap();

        assert_eq!(filter.len(), 2);
        // and[0] is an atomic filter
        let atomic_filter = filter[0].as_atomic_filter().unwrap();
        assert_eq!(atomic_filter.field, "name");
        assert_eq!(atomic_filter.operator, FilterOperator::Regex);
        assert_eq!(atomic_filter.value, "test_extension_[1-2]");

        // and[1] is an atomic filter
        let atomic_filter = filter[1].as_atomic_filter().unwrap();
        assert_eq!(atomic_filter.field, "app");
        assert_eq!(atomic_filter.operator, FilterOperator::Exact);
        assert_eq!(atomic_filter.value, "msgpack://127.0.0.1:8001/");

        // Find the selector node with name selector_for_ext_1_and_2_and_3
        let selector_node = selector_nodes
            .iter()
            .find(|node| node.get_name() == "selector_for_ext_1_and_2_and_3")
            .unwrap();

        let selector_node = selector_node.as_selector_node().unwrap();
        let filter = &selector_node.filter.as_atomic_filter().unwrap();
        assert_eq!(filter.field, "name");
        assert_eq!(filter.operator, FilterOperator::Regex);
        assert_eq!(filter.value, "test_extension_[1-3]");

        // Find the selector node with name selector_for_ext_1_or_3
        let selector_node = selector_nodes
            .iter()
            .find(|node| node.get_name() == "selector_for_ext_1_or_3")
            .unwrap();

        let selector_node = selector_node.as_selector_node().unwrap();
        let filter = &selector_node.filter.as_or_filter().unwrap();
        assert_eq!(filter.len(), 2);
        // or[0] is an atomic filter
        let atomic_filter = filter[0].as_atomic_filter().unwrap();
        assert_eq!(atomic_filter.field, "name");
        assert_eq!(atomic_filter.operator, FilterOperator::Regex);
        assert_eq!(atomic_filter.value, "test_extension_1");

        // or[1] is an atomic filter
        let atomic_filter = filter[1].as_atomic_filter().unwrap();
        assert_eq!(atomic_filter.field, "name");
        assert_eq!(atomic_filter.operator, FilterOperator::Regex);
        assert_eq!(atomic_filter.value, "test_extension_3");
    }
}
