//
// Copyright © 2025 Agora
// This file is part of TEN Framework, an open source project.
// Licensed under the Apache License, Version 2.0, with certain conditions.
// Refer to the "LICENSE" file in the root directory for more information.
//
#[cfg(test)]
mod tests {
    use ten_rust::{
        constants::ERR_MSG_UNKNOWN_GRAPH_NODE_TYPE,
        graph::{connection::GraphLoc, Graph},
    };

    #[test]
    fn test_check_node_exists_without_node_type_returns_error() {
        let graph = Graph {
            nodes: vec![],
            connections: None,
            exposed_messages: None,
            exposed_properties: None,
        };

        let result = GraphLoc::new().check_node_exists(&graph);

        assert_eq!(result.unwrap_err().to_string(), ERR_MSG_UNKNOWN_GRAPH_NODE_TYPE);
    }
}
