//
// Copyright © 2025 Agora
// This file is part of TEN Framework, an open source project.
// Licensed under the Apache License, Version 2.0, with certain conditions.
// Refer to the "LICENSE" file in the root directory for more information.
//
#[cfg(test)]
mod tests {
    use ten_rust::json_schema::{
        ten_validate_graph_json_string, ten_validate_interface_json_string,
        ten_validate_manifest_json_string, ten_validate_property_json_string,
        validate_manifest_lock_json_string,
    };

    #[test]
    fn test_validate_default_cpp_app() {
        let manifest = r#"
        {
          "type": "app",
          "name": "default_app_cpp",
          "version": "0.1.0",
          "dependencies": []
        }
        "#;
        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_graph_allows_builtin_test_extension() {
        let graph = r#"
        {
          "nodes": [
            {
              "type": "extension",
              "name": "ten:test_extension",
              "addon": "ten:test_extension"
            },
            {
              "type": "extension",
              "name": "ext_a",
              "addon": "addon_a"
            }
          ],
          "connections": [
            {
              "extension": "ten:test_extension",
              "cmd": [
                {
                  "name": "test_cmd",
                  "dest": [
                    {
                      "extension": "ext_a"
                    }
                  ]
                }
              ]
            }
          ]
        }
        "#;

        let result = ten_validate_graph_json_string(graph);
        assert!(result.is_ok(), "{result:?}");
    }

    #[test]
    fn test_validate_dependencies_normal() {
        let manifest = r#"
        {
          "type": "extension",
          "name": "default_extension_cpp",
          "version": "0.1.0",
          "dependencies": [{
            "type": "system",
            "name": "ten_runtime",
            "version": "0.6.0"
          }],
          "api": {}
        }
        "#;
        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_dev_dependencies_normal() {
        let manifest = r#"
        {
          "type": "extension",
          "name": "default_extension_cpp",
          "version": "0.1.0",
          "dev_dependencies": [{
            "type": "system",
            "name": "googletest",
            "version": "1.7.0-rc2"
          }],
          "api": {}
        }
        "#;
        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_mixed_dependencies_normal() {
        let manifest = r#"
        {
          "type": "extension",
          "name": "default_extension_cpp",
          "version": "0.1.0",
          "dev_dependencies": [{
            "type": "system",
            "name": "ten_runtime",
            "version": "0.6.0"
          },{
            "type": "system",
            "name": "googletest",
            "version": "1.7.0-rc2"
          }],
          "api": {}
        }
        "#;
        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_dependencies_with_path() {
        let manifest = r#"
        {
          "type": "app",
          "name": "default_app_cpp",
          "version": "0.1.0",
          "dependencies": [{
            "path": "path/to/dependency"
          }]
        }
        "#;
        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_dependencies_normal_and_with_path() {
        let manifest = r#"
        {
          "type": "app",
          "name": "default_app_cpp",
          "version": "0.1.0",
          "dependencies": [{
            "type": "system",
            "name": "ten_runtime",
            "version": "0.6.0"
          },{
            "path": "path/to/dependency"
          }]
        }
        "#;
        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_ok());
    }

    #[test]
    fn test_only_app_needs_predefined_graphs() {
        let manifest = r#"
        {
          "type": "extension",
          "name": "default_extension_cpp",
          "version": "0.1.0",
          "dependencies": []
        }
        "#;
        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_ok());
    }

    #[test]
    fn test_only_app_needs_predefined_graphs_supports() {
        let manifest = r#"
        {
          "type": "extension",
          "name": "default_extension_cpp",
          "version": "0.1.0",
          "dependencies": [],
          "supports": []
        }
        "#;
        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_ok());
    }

    #[test]
    fn test_only_app_needs_predefined_graphs_supports_with_content() {
        let manifest = r#"
        {
          "type": "extension",
          "name": "default_extension_cpp",
          "version": "0.1.0",
          "dependencies": [],
          "supports": [{"os": "linux", "arch": "x64"}]
        }
        "#;
        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_invalid_type() {
        let manifest = r#"
        {
          "type": "invalid",
          "name": "default_app_cpp",
          "version": "0.1.0",
          "dependencies": [],
          "api": {}
        }
        "#;

        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_invalid_graph_invalid_additional_property() {
        let property = r#"
        {
          "ten": {
            "predefined_graphs": [
              {
                "name": "default",
                "nodes": [
                  {
                    "type": "extension",
                    "name": "default_extension_cpp",
                    "addon": "default_extension_cpp",
                    "extension_group": "default_extension_group",
                    "should_not_present": "aa"
                  }
                ]
              }
            ]
          }
        }
        "#;

        let result = ten_validate_property_json_string(property);
        assert!(result.is_err());

        let msg = result.unwrap_err().to_string();
        assert!(msg.contains("Additional properties are not allowed"));
    }

    #[test]
    fn test_validate_graph_rejects_null_in_node_property() {
        let graph = r#"
        {
          "nodes": [
            {
              "type": "extension",
              "name": "llm",
              "addon": "glue_python_async",
              "property": {
                "system_messages": [
                  {
                    "role": "system",
                    "content": null
                  }
                ]
              }
            }
          ]
        }
        "#;

        let result = ten_validate_graph_json_string(graph);
        assert!(result.is_err());

        let msg = result.unwrap_err().to_string();
        assert!(msg.contains("null"));
    }

    #[test]
    fn test_validate_invalid_command_name_empty() {
        let property = r#"{
  "ten": {
    "predefined_graphs": [
      {
        "name": "default",
        "graph": {
          "nodes": [
            {
              "type": "extension",
              "name": "default_extension_cpp",
              "addon": "default_extension_cpp",
              "extension_group": "default_extension_group"
            }
          ],
          "connections": [
            {
              "extension": "default_extension_cpp",
              "cmd": [
                {
                  "name": "",
                  "dest": [
                    {
                      "extension": "default_extension_cpp"
                    }
                  ]
                }
              ]
            }
          ]
        }
      }
    ]
  }
}"#;

        let result = ten_validate_property_json_string(property);
        assert!(result.is_err());

        let msg = result.unwrap_err().to_string();
        assert!(msg.contains("is shorter than 1 character"));
    }

    #[test]
    fn test_validate_invalid_cmd_no_dest() {
        let property = r#"{
  "ten": {
    "predefined_graphs": [
      {
        "name": "default",
        "graph": {
          "nodes": [
            {
              "type": "extension",
              "name": "default_extension_cpp",
              "addon": "default_extension_cpp",
              "extension_group": "default_extension_group"
            }
          ],
          "connections": [
            {
              "extension": "default_extension_cpp",
              "cmd": [
                {
                  "name": "demo",
                  "dest": []
                }
              ]
            }
          ]
        }
      }
    ]
  }
}"#;

        let result = ten_validate_property_json_string(property);
        assert!(result.is_err());

        let msg = result.unwrap_err().to_string();
        assert!(msg.contains("[] has less than 1 item"));
    }

    #[test]
    fn test_validate_extension_property() {
        let property = r#"{
  "ten": {
    "predefined_graphs": [
      {
        "name": "default",
        "graph": {
          "nodes": [
            {
              "type": "extension",
              "name": "default_extension_cpp",
              "addon": "default_extension_cpp",
              "extension_group": "default_extension_group",
              "property": {
                "a": 1
              }
            }
          ]
        }
      }
    ]
  }
}"#;

        let result = ten_validate_property_json_string(property);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_extension_no_cmds() {
        let property = r#"{
  "ten": {
    "predefined_graphs": [
      {
        "name": "default",
        "graph": {
          "nodes": [
            {
              "type": "extension",
              "name": "default_extension_cpp",
              "addon": "default_extension_cpp",
              "extension_group": "default_extension_group"
            }
          ]
        }
      }
    ]
  }
}"#;

        let result = ten_validate_property_json_string(property);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_api_cmd_in_success_1() {
        let manifest = r#"
        {
          "type": "extension",
          "name": "default_extension_cpp",
          "version": "0.1.0",
          "dependencies": [],
          "api": {
            "cmd_in": [
              {
                "name": "foo",
                "property": {
                  "properties": {
                    "a": {
                      "type": "int8"
                    },
                    "b": {
                      "type": "uint8"
                    },
                    "c": {
                      "type": "array",
                      "items": {
                        "type": "string"
                      }
                    },
                    "d": {
                      "type": "object",
                      "properties": {
                        "e": {
                          "type": "float32"
                        }
                      }
                    }
                  }
                },
                "result": {
                  "property": {
                    "properties": {
                      "a": {
                        "type": "buf"
                      },
                      "detail": {
                        "type": "buf"
                      }
                    }
                  }
                }
              }
            ]
          }
        }
        "#;

        let result = ten_validate_manifest_json_string(manifest);
        println!("result: {result:?}");
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_api_cmd_in_success_2() {
        let manifest = r#"
        {
          "type": "extension",
          "name": "default_extension_cpp",
          "version": "0.1.0",
          "dependencies": [],
          "api": {
            "cmd_in": [
              {
                "name": "foo",
                "property": {
                  "properties": {
                    "a": {
                      "type": "int8"
                    },
                    "b": {
                      "type": "uint8"
                    },
                    "c": {
                      "type": "array",
                      "items": {
                        "type": "string"
                      }
                    },
                    "d": {
                      "type": "object",
                      "properties": {
                        "e": {
                          "type": "float32"
                        }
                      }
                    }
                  },
                  "required": ["a","b"]
                },
                "result": {
                  "property": {
                    "properties": {
                      "a": {
                        "type": "buf"
                      },
                      "detail": {
                        "type": "buf"
                      }
                    }
                  }
                }
              }
            ]
          }
        }
        "#;

        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_api_cmd_in_success_3() {
        let manifest = r#"
        {
          "type": "extension",
          "name": "default_extension_cpp",
          "version": "0.1.0",
          "dependencies": [],
          "api": {
            "cmd_in": [
              {
                "name": "foo",
                "property": {
                  "properties": {
                    "a": {
                      "type": "int8"
                    },
                    "b": {
                      "type": "uint8"
                    },
                    "c": {
                      "type": "array",
                      "items": {
                        "type": "string"
                      }
                    },
                    "d": {
                      "type": "object",
                      "properties": {
                        "e": {
                          "type": "float32"
                        }
                      }
                    }
                  },
                  "required": ["a","b"]
                },
                "result": {
                  "property": {
                    "properties": {
                      "a": {
                        "type": "buf"
                      },
                      "detail": {
                        "type": "buf"
                      }
                    },
                    "required": ["a"]
                  }
                }
              }
            ]
          }
        }
        "#;

        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_api_cmd_in_has_nested_object_required() {
        let manifest = r#"
        {
          "type": "extension",
          "name": "default_extension_cpp",
          "version": "0.1.0",
          "dependencies": [],
          "api": {
            "cmd_in": [
              {
                "name": "foo",
                "property": {
                  "properties": {
                    "a": {
                      "type": "int8"
                    },
                    "b": {
                      "type": "uint8"
                    },
                    "c": {
                      "type": "array",
                      "items": {
                        "type": "string"
                      }
                    },
                    "d": {
                      "type": "object",
                      "properties": {
                        "e": {
                          "type": "float32"
                        },
                        "f": {
                          "type": "string"
                        }
                      },
                      "required": ["e"]
                    }
                  },
                  "required": ["a","b"]
                },
                "result": {
                  "property": {
                    "properties": {
                      "a": {
                        "type": "buf"
                      },
                      "detail": {
                        "type": "buf"
                      }
                    }
                  }
                }
              }
            ]
          }
        }
        "#;

        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_api_cmd_in_fail_1() {
        let manifest = r#"
        {
          "type": "app",
          "name": "default_app_cpp",
          "version": "0.1.0",
          "dependencies": [],
          "api": {
            "cmd_in": [
              {
                "name": "foo",
                "property": {
                  "//a": {
                    "type": "int8"
                  },
                  "b": {
                    "type": "uint8"
                  },
                  "c": {
                    "type": "array",
                    "items": {
                      "type": "string"
                    }
                  },
                  "d": {
                    "type": "object",
                    "properties": {
                      "e": {
                        "type": "float32"
                      }
                    }
                  }
                },
                "result": {
                  "property": {
                    "a": {
                      "type": "buf"
                    },
                    "detail": {
                      "type": "buf"
                    }
                  }
                }
              }
            ]
          }
        }
        "#;

        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_api_cmd_in_fail_2() {
        let manifest = r#"
        {
          "type": "app",
          "name": "default_app_cpp",
          "version": "0.1.0",
          "dependencies": [],
          "api": {
            "cmd_in": [
              {
                "name": "foo",
                "property": {
                  "a": {
                    "type": "int8"
                  },
                  "b": {
                    "type": "uint8"
                  },
                  "c": {
                    "type": "array",
                    "items": {
                      "type": "string"
                    }
                  },
                  "d": {
                    "type": "object",
                    "properties": {
                      "//e": {
                        "type": "float32"
                      }
                    }
                  }
                },
                "result": {
                  "property": {
                    "a": {
                      "type": "buf"
                    },
                    "detail": {
                      "type": "buf"
                    }
                  }
                }
              }
            ]
          }
        }
        "#;

        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_api_cmd_in_fail_3() {
        let manifest = r#"
        {
          "type": "app",
          "name": "default_app_cpp",
          "version": "0.1.0",
          "dependencies": [],
          "api": {
            "cmd_in": [
              {
                "name": "foo",
                "property": {
                  "a": {
                    "type": "int8"
                  },
                  "b": {
                    "type": "uint8"
                  },
                  "c": {
                    "type": "array",
                    "items": {
                      "type": "string"
                    }
                  },
                  "d": {
                    "type": "object",
                    "properties": {
                      "e": {
                        "type": "float32"
                      }
                    }
                  }
                },
                "result": {
                  "property": {
                    "//a": {
                      "type": "buf"
                    },
                    "detail": {
                      "type": "buf"
                    }
                  }
                }
              }
            ]
          }
        }
        "#;

        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_err());
    }

    #[test]
    fn test_manifest_validate_api_cmd_in_result_must_have_prop() {
        let manifest = r#"
        {
          "type": "extension",
          "name": "default_extension_cpp",
          "version": "0.1.0",
          "dependencies": [],
          "api": {
            "cmd_in": [
              {
                "name": "foo",
                "property": {
                  "a": {
                    "type": "int8"
                  },
                  "b": {
                    "type": "uint8"
                  },
                  "c": {
                    "type": "array",
                    "items": {
                      "type": "string"
                    }
                  },
                  "d": {
                    "type": "object",
                    "properties": {
                      "e": {
                        "type": "float32"
                      }
                    }
                  }
                },
                "result": {
                }
              }
            ]
          }
        }
        "#;

        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_err());
    }

    #[test]
    fn test_manifest_validate_api_cmd_in_has_additional_prop() {
        let manifest = r#"
        {
          "type": "extension",
          "name": "embedding",
          "version": "0.1.0",
  "dependencies": [
            {
              "type": "system",
              "name": "ten_runtime_python",
              "version": "0.2.2"
            }
          ],
          "api": {
            "property": {
              "api_key": {
                "type": "string"
              },
              "model": {
                "type": "string"
              }
            },
            "cmd_in": [
              {
                "name": "embed",
                "property": {
                  "input": {
                    "type": "string"
                  }
                },
                "status": {
                  "property": {
                    "output": {
                      "type": "string"
                    },
                    "code": {
                      "type": "string"
                    },
                    "message": {
                      "type": "string"
                    }
                  }
                }
              },
              {
                "name": "embed_batch",
                "property": {
                  "inputs": {
                    "type": "array",
                    "items": {
                      "type": "string"
                    }
                  }
                },
                "status": {
                  "property": {
                    "output": {
                      "type": "string"
                    },
                    "code": {
                      "type": "string"
                    },
                    "message": {
                      "type": "string"
                    }
                  }
                }
              }
            ],
            "cmd_out": []
          }
        }
        "#;

        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_err());

        let msg = result.unwrap_err().to_string();
        assert!(msg.contains(
            "Additional properties are not allowed ('status' was unexpected) @ /api/cmd_in/0"
        ));
    }

    #[test]
    fn test_validate_api_only_array_has_items() {
        let manifest = r#"
        {
          "type": "app",
          "name": "default_app_cpp",
          "version": "0.1.0",
          "dependencies": [],
          "api": {
            "cmd_in": [
              {
                "name": "foo",
                "property": {
                  "properties": {
                    "a": {
                      "type": "int8",
                      "items": {
                        "type": "string"
                      }
                    }
                  }
                }
              }
            ]
          }
        }
        "#;

        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_err());

        assert!(result
            .unwrap_err()
            .to_string()
            .contains("{\"required\":[\"items\"]} is not allowed for"));
    }

    #[test]
    fn test_validate_api_only_object_has_properties() {
        let manifest = r#"
        {
          "type": "app",
          "name": "default_app_cpp",
          "version": "0.1.0",
          "dependencies": [],
          "api": {
            "cmd_in": [
              {
                "name": "foo",
                "property": {
                  "properties": {
                    "a": {
                      "type": "string",
                      "properties": {
                        "a": {
                          "type": "string"
                        }
                      }
                    }
                  }
                }
              }
            ]
          }
        }
        "#;

        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_err());

        assert!(result
            .unwrap_err()
            .to_string()
            .contains("{\"required\":[\"properties\"]} is not allowed for"));
    }

    #[test]
    fn test_validate_interface_empty() {
        let manifest = r#"
        {
          "type": "extension",
          "name": "default_extension_cpp",
          "version": "0.1.0",
          "dependencies": [],
          "api": {
            "interface": []
          }
        }
        "#;

        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_additional_properties() {
        let manifest = r#"
        {
          "type": "extension",
          "name": "default_extension_cpp",
          "version": "0.1.0",
          "dependencies": [],
          "interface": []
        }
        "#;

        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_err());

        assert!(result.unwrap_err().to_string().contains("Additional properties are not allowed"));
    }

    #[test]
    fn test_validate_interface_wrong_type() {
        let manifest = r#"
        {
          "type": "extension",
          "name": "default_extension_cpp",
          "version": "0.1.0",
          "dependencies": [],
          "api": {
            "interface": "interface.json"
          }
        }
        "#;

        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_err());

        assert!(result.unwrap_err().to_string().contains("is not of type"));
    }

    #[test]
    fn test_validate_interface_with_relative_path_import_uri() {
        let manifest = r#"
        {
          "type": "extension",
          "name": "default_extension_cpp",
          "version": "0.1.0",
          "dependencies": [],
          "api": {
            "interface": [
              {
                "import_uri": "interface.json"
              }
            ]
          }
        }
        "#;

        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_interface_with_absolute_path_import_uri() {
        let manifest = r#"
        {
          "type": "extension",
          "name": "default_extension_cpp",
          "version": "0.1.0",
          "dependencies": [],
          "api": {
            "interface": [
              {
                "import_uri": "file:///tmp/interface.json"
              }
            ]
          }
        }
        "#;

        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_interface_with_remote_url() {
        let manifest = r#"
        {
          "type": "extension",
          "name": "default_extension_cpp",
          "version": "0.1.0",
          "dependencies": [],
          "api": {
            "interface": [
              {
                "import_uri": "https://example.com/interface.json"
              }
            ]
          }
        }
        "#;

        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_interface_combined_with_cmd_in() {
        let manifest = r#"
        {
          "type": "extension",
          "name": "default_extension_cpp",
          "version": "0.1.0",
          "dependencies": [],
          "api": {
            "interface": [
              {
                "import_uri": "https://example.com/interface.json"
              }
            ],
            "cmd_in": [
              {
                "name": "foo",
                "property": {}
              }
            ]
          }
        }
        "#;

        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_interface_with_extra_fields() {
        let manifest = r#"
        {
          "type": "extension",
          "name": "default_extension_cpp",
          "version": "0.1.0",
          "dependencies": [],
          "api": {
            "interface": [
              {
                "import_uri": "https://example.com/interface.json",
                "extra": "extra"
              }
            ]
          }
        }
        "#;

        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_err());

        assert!(result.unwrap_err().to_string().contains("Additional properties are not allowed"));
    }

    #[test]
    fn test_validate_interface_without_import_uri() {
        let manifest = r#"
        {
          "type": "extension",
          "name": "default_extension_cpp",
          "version": "0.1.0",
          "dependencies": [],
          "api": {
            "interface": [
              {}
            ]
          }
        }
        "#;

        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_err());

        assert!(result.unwrap_err().to_string().contains("is a required property"));
    }

    #[test]
    fn test_graph_msg_conversions() {
        let property = r#"
        {
          "ten": {
            "predefined_graphs": [{
              "name": "default",
              "auto_start": false,
              "graph": {
                "nodes": [{
                  "type": "extension",
                  "name": "test_extension_1",
                  "addon": "result_mapping_1__test_extension_1",
                  "extension_group": "result_mapping_1__extension_group"
                },{
                  "type": "extension",
                  "name": "test_extension_2",
                  "addon": "result_mapping_1__test_extension_2",
                  "extension_group": "result_mapping_1__extension_group"
                }],
                "connections": [{
                  "app": "msgpack://127.0.0.1:8001/",
                  "extension": "test_extension_1",
                  "cmd": [{
                    "name": "hello_world",
                    "dest": [{
                      "app": "msgpack://127.0.0.1:8001/",
                      "extension": "test_extension_2",
                      "msg_conversion": {
                        "type": "per_property",
                        "rules": [{
                          "path": "ten.name",
                          "conversion_mode": "fixed_value",
                          "value": "hello mapping"
                        },{
                          "path": "test_group.test_property_name",
                          "conversion_mode": "from_original",
                          "original_path": "test_property"
                        }],
                        "result": {
                          "type": "per_property",
                          "rules": [{
                            "path": "resp_group.resp_property_name",
                            "conversion_mode": "from_original",
                            "original_path": "resp_property"
                          }]
                        }
                      }
                    }]
                  }]
                }]
              }
            }]
          }
        }
        "#;

        let result = ten_validate_property_json_string(property);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_property_cmd_must_be_alphanumeric() {
        let property = r#"{
  "ten": {
    "predefined_graphs": [
      {
        "name": "default",
        "graph": {
          "nodes": [
            {
              "type": "extension",
              "name": "default_extension_cpp",
              "addon": "default_extension_cpp",
              "extension_group": "default_extension_group"
            }
          ],
          "connections": [
            {
              "extension": "default_extension_cpp",
              "cmd": [
                {
                  "name": "invalid command",
                  "dest": [
                    {
                      "extension": "default_extension_cpp"
                    }
                  ]
                }
              ]
            }
          ]
        }
      }
    ]
  }
}"#;

        let result = ten_validate_property_json_string(property);
        assert!(result.is_err());

        assert!(result.unwrap_err().to_string().contains("does not match"));
    }

    #[test]
    fn test_validate_property_json_valid() {
        let property = r#"
        {
          "ten": {
            "log": {
              "handlers": [
                {
                  "matchers": [
                    {
                      "level": "info"
                    }
                  ],
                  "formatter": {
                    "type": "json",
                    "colored": false
                  },
                  "emitter": {
                    "type": "file",
                    "config": {
                      "path": "api.log"
                    }
                  }
                }
              ]
            }
          },
          "a": 1,
          "b": "2",
          "c": [1, 2, 3],
          "d": {
            "e": 1.0
          }
        }
        "#;

        let result = ten_validate_property_json_string(property);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_property_key_can_be_any_string() {
        // Test that property keys with hyphens are now allowed
        let property = r#"
        {
          "invalid-key": 1
        }
        "#;

        let result = ten_validate_property_json_string(property);
        if let Err(e) = &result {
            println!("Error: {}", e);
        }
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_property_key_with_special_characters() {
        // Test property key with hyphens and special characters
        let property = r#"
        {
          "x-amzn-sagemaker-custom-attributes": "X-Path:/v1/chat/completions",
          "api-key": "test-value",
          "content-type": "application/json"
        }
        "#;

        let result = ten_validate_property_json_string(property);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_property_key_starting_with_number() {
        // Test property key starting with a number
        let property = r#"
        {
          "123": "value",
          "456abc": "another-value"
        }
        "#;

        let result = ten_validate_property_json_string(property);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_property_nested_object_with_non_alphanumeric_keys() {
        // Test nested objects with non-alphanumeric keys
        let property = r#"
        {
          "outer-key": {
            "inner-key": "value",
            "123": 456,
            "kebab-case-key": {
              "deep-nested-key": "deep-value"
            }
          }
        }
        "#;

        let result = ten_validate_property_json_string(property);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_graph_node_property_with_non_alphanumeric_keys() {
        // Test that graphNode property can have non-alphanumeric keys
        let property = r#"
        {
          "ten": {
            "predefined_graphs": [{
              "name": "default",
              "auto_start": true,
              "graph": {
                "nodes": [{
                  "type": "extension",
                  "name": "test_extension",
                  "addon": "test_addon",
                  "property": {
                    "server-port": 8080,
                    "x-custom-header": "header-value",
                    "123": "numeric-key",
                    "nested-object": {
                      "inner-key": "inner-value",
                      "456": 789
                    }
                  }
                }]
              }
            }]
          }
        }
        "#;

        let result = ten_validate_property_json_string(property);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_real_world_property_example() {
        // Test the actual property.json from the example directory
        let property = r#"
{
  "ten": {
    "log": {
      "handlers": [
        {
          "matchers": [
            {
              "level": "info"
            }
          ],
          "formatter": {
            "type": "plain",
            "colored": true
          },
          "emitter": {
            "type": "console",
            "config": {
              "stream": "stdout"
            }
          }
        }
      ]
    },
    "predefined_graphs": [
      {
        "name": "default",
        "auto_start": true,
        "graph": {
          "nodes": [
            {
              "type": "extension",
              "name": "aio_http_server_python",
              "addon": "aio_http_server_python",
              "extension_group": "test",
              "property": {
                "server_port": 8002,
                "header": {
                  "x-amzn-sagemaker-custom-attributes": "X-Path:/v1/chat/completions"
                },
                "123": "ahfiaos"
              }
            },
            {
              "type": "extension",
              "name": "simple_echo_cpp",
              "addon": "simple_echo_cpp",
              "extension_group": "default_extension_group"
            }
          ],
          "connections": [
            {
              "extension": "aio_http_server_python",
              "cmd": [
                {
                  "name": "test",
                  "dest": [
                    {
                      "extension": "simple_echo_cpp"
                    }
                  ]
                }
              ]
            }
          ]
        }
      }
    ]
  }
}
        "#;

        let result = ten_validate_property_json_string(property);
        if let Err(e) = &result {
            println!("Error: {}", e);
        }
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_manifest_lock_empty() {
        let manifest_lock = r#"{}"#;

        // The 'packages' field is required in the manifest lock file.
        let result = validate_manifest_lock_json_string(manifest_lock);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_manifest_lock_empty_packages() {
        let manifest_lock = r#"{
          "version": 1,
          "packages": []
        }"#;

        let result = validate_manifest_lock_json_string(manifest_lock);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_manifest_lock_invalid_lock_version() {
        let manifest_lock = r#"{
          "version": 0,
          "packages": []
        }"#;

        let result = validate_manifest_lock_json_string(manifest_lock);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_manifest_lock_duplicated_packages() {
        // NOTE: The 'type' combined with 'name' must be unique. But the json
        // schema check does not support this. The check should be done
        // in the code.
        let manifest_lock = r#"{
          "version": 1,
          "packages": [
            {
              "type": "extension",
              "name": "ext_a",
              "version": "1.0.0",
              "hash": "e8dc07a47927e9a650d23f77676b798e0856dd169fea70e7db57d57095261a68"
            },
            {
              "type": "extension",
              "name": "ext_a",
              "version": "1.0.0",
              "hash": "e8dc07a47927e9a650d23f77676b798e0856dd169fea70e7db57d57095261a68"
            }
          ]
        }"#;

        let result = validate_manifest_lock_json_string(manifest_lock);
        assert!(result.is_err());

        let err_reason = result.unwrap_err().to_string();
        assert!(err_reason.contains("has non-unique elements"));
    }

    #[test]
    fn test_validate_manifest_lock_missing_field_in_pkg() {
        // Miss hash field in the package.
        let manifest_lock = r#"{
          "version": 1,
          "packages": [
            {
              "type": "extension",
              "name": "ext_a",
              "version": "1.0.0"
            }
          ]
        }"#;

        let result = validate_manifest_lock_json_string(manifest_lock);
        assert!(result.is_err());

        let err_reason = result.unwrap_err().to_string();
        assert!(err_reason.contains("is a required property"));
    }

    #[test]
    fn test_validate_manifest_lock_invalid_version() {
        // The version field must be a fixed version but not a range.
        let manifest_lock = r#"{
          "version": 1,
          "packages": [
            {
              "type": "extension",
              "name": "ext_a",
              "version": ">1.0.0",
              "hash": "e8dc07a47927e9a650d23f77676b798e0856dd169fea70e7db57d57095261a68"
            }
          ]
        }"#;

        let result = validate_manifest_lock_json_string(manifest_lock);
        assert!(result.is_err());

        let err_reason = result.unwrap_err().to_string();
        assert!(err_reason.contains("does not match"));
    }

    #[test]
    fn test_validate_manifest_lock_pre_release_version() {
        // The pre-release version is allowed.
        let manifest_lock = r#"{
          "version": 1,
          "packages": [
            {
              "type": "extension",
              "name": "ext_a",
              "version": "0.1.0-rc.1",
              "hash": "e8dc07a47927e9a650d23f77676b798e0856dd169fea70e7db57d57095261a68"
            }
          ]
        }"#;

        let result = validate_manifest_lock_json_string(manifest_lock);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_manifest_lock_invalid_type() {
        // The type field must be one of the following: extension, system,
        // protocol, addon_loader.
        let manifest_lock = r#"{
          "version": 1,
          "packages": [
            {
              "type": "invalid_type",
              "name": "ext_a",
              "version": "0.1.0-rc.1",
              "hash": "e8dc07a47927e9a650d23f77676b798e0856dd169fea70e7db57d57095261a68"
            }
          ]
        }"#;

        let result = validate_manifest_lock_json_string(manifest_lock);
        assert!(result.is_err());

        let err_reason = result.unwrap_err().to_string();
        assert!(err_reason.contains("is not one of"));
    }

    #[test]
    fn test_validate_manifest_lock_addon_loader_type() {
        // The type field must be addon_loader.
        let manifest_lock = r#"{
          "version": 1,
          "packages": [
            {
              "type": "addon_loader",
              "name": "addon_loader_a",
              "version": "0.1.0-rc.1",
              "hash": "e8dc07a47927e9a650d23f77676b798e0856dd169fea70e7db57d57095261a68"
            }
          ]
        }"#;

        let result = validate_manifest_lock_json_string(manifest_lock);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_manifest_lock_empty_dependency() {
        let manifest_lock = r#"{
          "version": 1,
          "packages": [
            {
              "type": "extension",
              "name": "ext_a",
              "version": "1.0.0",
              "hash": "e8dc07a47927e9a650d23f77676b798e0856dd169fea70e7db57d57095261a68",
      "dependencies": []
            }
          ]
        }"#;

        let result = validate_manifest_lock_json_string(manifest_lock);
        assert!(result.is_err());

        let err_reason = result.unwrap_err().to_string();
        assert!(err_reason.contains("has less than 1 item"));
    }

    #[test]
    fn test_validate_manifest_lock_invalid_supports() {
        let manifest_lock = r#"{
          "version": 1,
          "packages": [
            {
              "type": "extension",
              "name": "ext_a",
              "version": "1.0.0",
              "hash": "e8dc07a47927e9a650d23f77676b798e0856dd169fea70e7db57d57095261a68",
              "supports": [
                {
                  "os": "linux",
                  "arch": "x63"
                }
              ]
            }
          ]
        }"#;

        let result = validate_manifest_lock_json_string(manifest_lock);
        assert!(result.is_err());

        let err_reason = result.unwrap_err().to_string();
        assert!(err_reason.contains("is not one of"));
    }

    #[test]
    fn test_validate_manifest_lock_duplicated_dependencies() {
        let manifest_lock = r#"{
          "version": 1,
          "packages": [
            {
              "type": "extension",
              "name": "ext_a",
              "version": "1.0.0",
              "hash": "e8dc07a47927e9a650d23f77676b798e0856dd169fea70e7db57d57095261a68",
      "dependencies": [
                {
                  "type": "extension",
                  "name": "ext_a"
                },
                {
                  "type": "extension",
                  "name": "ext_a"
                }
              ]
            }
          ]
        }"#;

        let result = validate_manifest_lock_json_string(manifest_lock);
        assert!(result.is_err());

        let err_reason = result.unwrap_err().to_string();
        assert!(err_reason.contains("has non-unique elements"));
    }

    #[test]
    fn test_validate_manifest_lock_success() {
        let manifest_lock = r#"{
        "version": 1,
        "packages": [
          {
            "type": "extension",
            "name": "ext_b",
            "version": "1.0.0",
            "hash": "e6d7ff0aefd1a0618c9f7d8c154b1b90c917390bd00d2a107eae616a36a99391",
    "dependencies": [
              {
                "type": "extension",
                "name": "ext_a"
              }
            ]
          },
          {
            "type": "extension",
            "name": "ext_1",
            "version": "2.0.0",
            "hash": "e64b5c3c66a3014f2c58299d663533eb984ac9e71aa50067f6f3c3b9d409ccdf",
    "dependencies": [
              {
                "type": "extension",
                "name": "ext_3"
              }
            ]
          },
          {
            "type": "extension",
            "name": "ext_3",
            "version": "1.0.0",
            "hash": "2c61c0fc8b3cd2da7457a779b2db423ae93c3b6cae7347cb979453f1ac17ccc0"
          },
          {
            "type": "extension",
            "name": "ext_a",
            "version": "1.2.2",
            "hash": "6fee978cd201b108211b52323a078c5222fd0bc545468b5989d7e42d0f5b7395"
          }
        ]
      }"#;

        let result = validate_manifest_lock_json_string(manifest_lock);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_exposed_messages_extension_subgraph_mutual_exclusion() {
        // Test that exposed_messages with both extension and subgraph fields
        // fails
        let property_json_with_both_fields = r#"
        {
            "ten": {
                "predefined_graphs": [
                    {
                        "name": "test_graph",
                        "graph": {
                            "exposed_messages": [
                                {
                                    "type": "cmd_in",
                                    "name": "test_cmd",
                                    "extension": "ext_a",
                                    "subgraph": "subgraph_1"
                                }
                            ]
                        }
                    }
                ]
            }
        }
        "#;

        let result = ten_validate_property_json_string(property_json_with_both_fields);
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("oneOf"));

        // Test that exposed_messages with neither extension nor subgraph fields
        // fails
        let property_json_with_neither_field = r#"{
  "ten": {
    "predefined_graphs": [
      {
        "name": "test_graph",
        "graph": {
          "exposed_messages": [
            {
              "type": "cmd_in",
              "name": "test_cmd"
            }
          ]
        }
      }
    ]
  }
}"#;

        let result = ten_validate_property_json_string(property_json_with_neither_field);
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("oneOf"));

        // Test that exposed_messages with only extension field succeeds
        let property_json_with_extension = r#"{
  "ten": {
    "predefined_graphs": [
      {
        "name": "test_graph",
        "graph": {
          "exposed_messages": [
            {
              "type": "cmd_in",
              "name": "test_cmd",
              "extension": "ext_a"
            }
          ]
        }
      }
    ]
  }
}"#;

        let result = ten_validate_property_json_string(property_json_with_extension);
        assert!(result.is_ok());

        // Test that exposed_messages with only subgraph field succeeds
        let property_json_with_subgraph = r#"{
  "ten": {
    "predefined_graphs": [
      {
        "name": "test_graph",
        "graph": {
          "exposed_messages": [
            {
              "type": "cmd_in",
              "name": "test_cmd",
              "subgraph": "subgraph_1"
            }
          ]
        }
      }
    ]
  }
}"#;

        let result = ten_validate_property_json_string(property_json_with_subgraph);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_exposed_properties_extension_subgraph_mutual_exclusion() {
        // Test that exposed_properties with both extension and subgraph fields
        // fails
        let property_json_with_both_fields = r#"{
  "ten": {
    "predefined_graphs": [
      {
        "name": "test_graph",
        "graph": {
          "exposed_properties": [
            {
              "name": "test_prop",
              "extension": "ext_a",
              "subgraph": "subgraph_1"
            }
          ]
        }
      }
    ]
  }
}"#;

        let result = ten_validate_property_json_string(property_json_with_both_fields);
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("oneOf"));

        // Test that exposed_properties with neither extension nor subgraph
        // fields fails
        let property_json_with_neither_field = r#"{
  "ten": {
    "predefined_graphs": [
      {
        "name": "test_graph",
        "graph": {
          "exposed_properties": [
            {
              "name": "test_prop"
            }
          ]
        }
      }
    ]
  }
}"#;

        let result = ten_validate_property_json_string(property_json_with_neither_field);
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("oneOf"));

        // Test that exposed_properties with only extension field succeeds
        let property_json_with_extension = r#"{
  "ten": {
    "predefined_graphs": [
      {
        "name": "test_graph",
        "graph": {
          "exposed_properties": [
            {
              "name": "test_prop",
              "extension": "ext_a"
            }
          ]
        }
      }
    ]
  }
}"#;

        let result = ten_validate_property_json_string(property_json_with_extension);
        assert!(result.is_ok());

        // Test that exposed_properties with only subgraph field succeeds
        let property_json_with_subgraph = r#"{
  "ten": {
    "predefined_graphs": [
      {
        "name": "test_graph",
        "graph": {
          "exposed_properties": [
            {
              "name": "test_prop",
              "subgraph": "subgraph_1"
            }
          ]
        }
      }
    ]
  }
}"#;

        let result = ten_validate_property_json_string(property_json_with_subgraph);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_import_uri_mutual_exclusion_with_nodes() {
        // Test that import_uri and nodes are mutually exclusive
        let property = r#"{
  "ten": {
    "predefined_graphs": [
      {
        "name": "default",
        "graph": {
          "import_uri": "test_graph.json",
          "nodes": [
            {
              "type": "extension",
              "name": "test_ext",
              "addon": "test_addon",
              "extension_group": "test_group"
            }
          ]
        }
      }
    ]
  }
}"#;

        let result = ten_validate_property_json_string(property);
        assert!(result.is_err());
        let msg = result.unwrap_err().to_string();
        assert!(msg.contains("oneOf"));
    }

    #[test]
    fn test_validate_import_uri_mutual_exclusion_with_connections() {
        // Test that import_uri and connections are mutually exclusive
        let property = r#"{
  "ten": {
    "predefined_graphs": [
      {
        "name": "default",
        "graph": {
          "import_uri": "test_graph.json",
          "connections": [
            {
              "extension": "test_ext",
              "cmd": [
                {
                  "name": "test_cmd",
                  "dest": [
                    {
                      "extension": "test_ext"
                    }
                  ]
                }
              ]
            }
          ]
        }
      }
    ]
  }
}"#;

        let result = ten_validate_property_json_string(property);
        assert!(result.is_err());
        let msg = result.unwrap_err().to_string();
        assert!(msg.contains("oneOf"));
    }

    #[test]
    fn test_validate_import_uri_mutual_exclusion_with_exposed_messages() {
        // Test that import_uri and exposed_messages are mutually exclusive
        let property = r#"{
  "ten": {
    "predefined_graphs": [
      {
        "name": "default",
        "graph": {
          "import_uri": "test_graph.json",
          "exposed_messages": [
            {
              "type": "cmd_in",
              "name": "test_msg",
              "extension": "test_ext"
            }
          ]
        }
      }
    ]
  }
}"#;

        let result = ten_validate_property_json_string(property);
        assert!(result.is_err());
        let msg = result.unwrap_err().to_string();
        assert!(msg.contains("oneOf"));
    }

    #[test]
    fn test_validate_import_uri_mutual_exclusion_with_exposed_properties() {
        // Test that import_uri and exposed_properties are mutually exclusive
        let property = r#"{
  "ten": {
    "predefined_graphs": [
      {
        "name": "default",
        "graph": {
          "import_uri": "test_graph.json",
          "exposed_properties": [
            {
              "name": "test_prop",
              "extension": "test_ext"
            }
          ]
        }
      }
    ]
  }
}"#;

        let result = ten_validate_property_json_string(property);
        assert!(result.is_err());
        let msg = result.unwrap_err().to_string();
        assert!(msg.contains("oneOf"));
    }

    #[test]
    fn test_validate_import_uri_without_conflicting_fields_succeeds() {
        // Test that import_uri alone is valid
        let property = r#"{
  "ten": {
    "predefined_graphs": [
      {
        "name": "default",
        "graph": {
          "import_uri": "test_graph.json"
        }
      }
    ]
  }
}"#;

        let result = ten_validate_property_json_string(property);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_graph_without_import_uri_succeeds() {
        // Test that a graph without import_uri but with other fields is valid
        let property = r#"{
  "ten": {
    "predefined_graphs": [
      {
        "name": "default",
        "graph": {
          "nodes": [
            {
              "type": "extension",
              "name": "test_ext",
              "addon": "test_addon",
              "extension_group": "test_group"
            }
          ],
          "connections": [
            {
              "extension": "test_ext",
              "cmd": [
                {
                  "name": "test_cmd",
                  "dest": [
                    {
                      "extension": "test_ext"
                    }
                  ]
                }
              ]
            }
          ],
          "exposed_messages": [
            {
              "type": "cmd_in",
              "name": "test_msg",
              "extension": "test_ext"
            }
          ],
          "exposed_properties": [
            {
              "name": "test_prop",
              "extension": "test_ext"
            }
          ]
        }
      }
    ]
  }
}"#;

        let result = ten_validate_property_json_string(property);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_graph_with_subgraph_specified_addon() {
        let property = r#"{
  "ten": {
    "predefined_graphs": [
      {
        "name": "default",
        "graph": {
          "nodes": [
            {
              "type": "subgraph",
              "name": "subgraph_1",
              "addon": "subgraph_1",
              "graph": {
                "import_uri": "graphs/test_graph.json"
              }
            }
          ]
        }
      }
    ]
  }
}"#;

        let result = ten_validate_property_json_string(property);
        // The subgraph with specified addon is invalid.
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_graph_with_extension_node_without_addon() {
        let property = r#"
        {
          "ten": {
            "predefined_graphs": [
              {
                "name": "default",
                "nodes": [
                  {
                    "type": "extension",
                    "name": "ext_a",
                  }
                ]
              }
            ]
          }
        }
        "#;

        let result = ten_validate_property_json_string(property);
        // The extension node without addon is invalid.
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_source_extension_subgraph_mutual_exclusion() {
        // Test that source with both extension and subgraph fields fails
        let property = r#"{
  "ten": {
    "predefined_graphs": [
      {
        "name": "default",
        "graph": {
          "nodes": [
            {
              "type": "extension",
              "name": "test_ext",
              "addon": "test_addon",
              "extension_group": "test_group"
            }
          ],
          "connections": [
            {
              "extension": "test_ext",
              "cmd": [
                {
                  "name": "test_cmd",
                  "source": [
                    {
                      "extension": "test_ext",
                      "subgraph": "test_subgraph"
                    }
                  ]
                }
              ]
            }
          ]
        }
      }
    ]
  }
}"#;

        let result = ten_validate_property_json_string(property);
        assert!(result.is_err());
        let msg = result.unwrap_err().to_string();
        assert!(msg.contains("oneOf"));
    }

    #[test]
    fn test_validate_source_extension_only() {
        // Test that source with only extension field succeeds
        let property = r#"{
  "ten": {
    "predefined_graphs": [
      {
        "name": "default",
        "graph": {
          "nodes": [
            {
              "type": "extension",
              "name": "test_ext",
              "addon": "test_addon",
              "extension_group": "test_group"
            }
          ],
          "connections": [
            {
              "extension": "test_ext",
              "cmd": [
                {
                  "name": "test_cmd",
                  "source": [
                    {
                      "extension": "test_ext"
                    }
                  ]
                }
              ]
            }
          ]
        }
      }
    ]
  }
}"#;

        let result = ten_validate_property_json_string(property);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_source_subgraph_only() {
        // Test that source with only subgraph field succeeds
        let property = r#"{
  "ten": {
    "predefined_graphs": [
      {
        "name": "default",
        "graph": {
          "nodes": [
            {
              "type": "extension",
              "name": "test_ext",
              "addon": "test_addon",
              "extension_group": "test_group"
            }
          ],
          "connections": [
            {
              "extension": "test_ext",
              "cmd": [
                {
                  "name": "test_cmd",
                  "source": [
                    {
                      "subgraph": "test_subgraph"
                    }
                  ]
                }
              ]
            }
          ]
        }
      }
    ]
  }
}"#;

        let result = ten_validate_property_json_string(property);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_source_with_app() {
        // Test that source with app field succeeds
        let property = r#"{
  "ten": {
    "predefined_graphs": [
      {
        "name": "default",
        "graph": {
          "nodes": [
            {
              "type": "extension",
              "name": "test_ext",
              "addon": "test_addon",
              "extension_group": "test_group"
            }
          ],
          "connections": [
            {
              "extension": "test_ext",
              "cmd": [
                {
                  "name": "test_cmd",
                  "source": [
                    {
                      "app": "msgpack://127.0.0.1:8001/",
                      "extension": "test_ext"
                    }
                  ]
                }
              ]
            }
          ]
        }
      }
    ]
  }
}"#;

        let result = ten_validate_property_json_string(property);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_source_with_invalid_field() {
        // Test that source with invalid additional field fails
        let property = r#"{
  "ten": {
    "predefined_graphs": [
      {
        "name": "default",
        "graph": {
          "nodes": [
            {
              "type": "extension",
              "name": "test_ext",
              "addon": "test_addon",
              "extension_group": "test_group"
            }
          ],
          "connections": [
            {
              "extension": "test_ext",
              "cmd": [
                {
                  "name": "test_cmd",
                  "source": [
                    {
                      "extension": "test_ext",
                      "invalid_field": "value"
                    }
                  ]
                }
              ]
            }
          ]
        }
      }
    ]
  }
}"#;

        let result = ten_validate_property_json_string(property);
        assert!(result.is_err());
        let msg = result.unwrap_err().to_string();
        assert!(msg.contains("Additional properties are not allowed"));
    }

    #[test]
    fn test_validate_api_property_with_string_description() {
        // Test that property with simple string description succeeds
        let manifest = r#"
        {
          "type": "extension",
          "name": "test_extension",
          "version": "0.1.0",
          "dependencies": [],
          "api": {
            "property": {
              "properties": {
                "api_key": {
                  "type": "string",
                  "description": "API key for authentication"
                },
                "timeout": {
                  "type": "int32",
                  "description": "Request timeout in milliseconds"
                }
              }
            }
          }
        }
        "#;

        let result = ten_validate_manifest_json_string(manifest);
        println!("result: {result:?}");
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_api_property_with_localized_description() {
        // Test that property with localizedText description succeeds
        let manifest = r#"
        {
          "type": "extension",
          "name": "test_extension",
          "version": "0.1.0",
          "dependencies": [],
          "api": {
            "property": {
              "properties": {
                "api_key": {
                  "type": "string",
                  "description": {
                    "locales": {
                      "en-US": {
                        "content": "API key for authentication"
                      },
                      "zh-CN": {
                        "content": "用于身份验证的 API 密钥"
                      }
                    }
                  }
                }
              }
            }
          }
        }
        "#;

        let result = ten_validate_manifest_json_string(manifest);
        println!("result: {result:?}");
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_cmd_in_property_with_string_description() {
        // Test that cmd_in property with string description succeeds
        let manifest = r#"
        {
          "type": "extension",
          "name": "test_extension",
          "version": "0.1.0",
          "dependencies": [],
          "api": {
            "cmd_in": [
              {
                "name": "tool_call",
                "property": {
                  "properties": {
                    "name": {
                      "type": "string",
                      "description": "tool name"
                    },
                    "args": {
                      "type": "string",
                      "description": "tool arguments"
                    }
                  },
                  "required": ["name"]
                }
              }
            ]
          }
        }
        "#;

        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_cmd_in_property_with_localized_description() {
        // Test that cmd_in property with localizedText description succeeds
        let manifest = r#"
        {
          "type": "extension",
          "name": "bingsearch_tool_python",
          "version": "0.2.0",
          "dependencies": [],
          "api": {
            "cmd_in": [
              {
                "name": "tool_call",
                "property": {
                  "properties": {
                    "name": {
                      "type": "string",
                      "description": "tool name"
                    },
                    "args": {
                      "type": "string",
                      "description": {
                        "locales": {
                          "en-US": {
                            "content": "tool arguments"
                          },
                          "zh-CN": {
                            "content": "工具参数"
                          }
                        }
                      }
                    }
                  },
                  "required": ["name"]
                }
              }
            ]
          }
        }
        "#;

        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_nested_object_property_with_description() {
        // Test nested object properties with descriptions
        let manifest = r#"
        {
          "type": "extension",
          "name": "test_extension",
          "version": "0.1.0",
          "dependencies": [],
          "api": {
            "cmd_in": [
              {
                "name": "configure",
                "property": {
                  "properties": {
                    "settings": {
                      "type": "object",
                      "description": "Configuration settings",
                      "properties": {
                        "host": {
                          "type": "string",
                          "description": {
                            "locales": {
                              "en-US": {
                                "content": "Server hostname"
                              },
                              "zh-CN": {
                                "content": "服务器主机名"
                              }
                            }
                          }
                        },
                        "port": {
                          "type": "int32",
                          "description": "Server port number"
                        }
                      }
                    }
                  }
                }
              }
            ]
          }
        }
        "#;

        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_array_items_with_description() {
        // Test array items with description
        let manifest = r#"
        {
          "type": "extension",
          "name": "test_extension",
          "version": "0.1.0",
          "dependencies": [],
          "api": {
            "property": {
              "properties": {
                "servers": {
                  "type": "array",
                  "description": "List of server configurations",
                  "items": {
                    "type": "object",
                    "description": "Server configuration",
                    "properties": {
                      "url": {
                        "type": "string",
                        "description": "Server URL"
                      }
                    }
                  }
                }
              }
            }
          }
        }
        "#;

        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_description_with_invalid_locale() {
        // Test that invalid locale format fails
        let manifest = r#"
        {
          "type": "extension",
          "name": "test_extension",
          "version": "0.1.0",
          "dependencies": [],
          "api": {
            "property": {
              "properties": {
                "api_key": {
                  "type": "string",
                  "description": {
                    "locales": {
                      "invalid_locale": {
                        "content": "Invalid locale format"
                      }
                    }
                  }
                }
              }
            }
          }
        }
        "#;

        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_err());
        let msg = result.unwrap_err().to_string();
        println!("Error message: {}", msg);
        // The invalid locale name should cause validation error
        assert!(
            msg.contains("oneOf")
                || msg.contains("does not match")
                || msg.contains("Property name")
        );
    }

    #[test]
    fn test_validate_description_localized_text_empty_locales() {
        // Test that localizedText with empty locales fails
        let manifest = r#"
        {
          "type": "extension",
          "name": "test_extension",
          "version": "0.1.0",
          "dependencies": [],
          "api": {
            "property": {
              "properties": {
                "api_key": {
                  "type": "string",
                  "description": {
                    "locales": {}
                  }
                }
              }
            }
          }
        }
        "#;

        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_err());
        let msg = result.unwrap_err().to_string();
        println!("Error message: {}", msg);
        // Empty locales object should fail validation due to oneOf constraint
        assert!(
            msg.contains("oneOf") || msg.contains("minProperties") || msg.contains("has less than")
        );
    }

    #[test]
    fn test_validate_description_localized_text_missing_content() {
        // Test that localizedText without content or import_uri fails
        let manifest = r#"
        {
          "type": "extension",
          "name": "test_extension",
          "version": "0.1.0",
          "dependencies": [],
          "api": {
            "property": {
              "properties": {
                "api_key": {
                  "type": "string",
                  "description": {
                    "locales": {
                      "en-US": {}
                    }
                  }
                }
              }
            }
          }
        }
        "#;

        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_err());
        let msg = result.unwrap_err().to_string();
        assert!(msg.contains("oneOf"));
    }

    #[test]
    fn test_validate_msg_dest_extension_with_app() {
        let property = r#"{
  "ten": {
    "predefined_graphs": [
      {
        "name": "test",
        "graph": {
          "connections": [
            {
              "extension": "test_ext",
              "cmd": [
                {
                  "name": "test_cmd",
                  "dest": [
                    {
                      "extension": "target_ext",
                      "app": "test_app"
                    }
                  ]
                }
              ]
            }
          ]
        }
      }
    ]
  }
}"#;
        let result = ten_validate_property_json_string(property);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_msg_dest_extension_with_msg_conversion() {
        let property = r#"{
  "ten": {
    "predefined_graphs": [
      {
        "name": "test",
        "graph": {
          "connections": [
            {
              "extension": "test_ext",
              "cmd": [
                {
                  "name": "test_cmd",
                  "dest": [
                    {
                      "extension": "target_ext",
                      "msg_conversion": {
                        "type": "per_property",
                        "rules": [
                          {
                            "path": "data",
                            "conversion_mode": "fixed_value",
                            "value": "test"
                          }
                        ]
                      }
                    }
                  ]
                }
              ]
            }
          ]
        }
      }
    ]
  }
}"#;
        let result = ten_validate_property_json_string(property);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_msg_dest_subgraph() {
        let property = r#"{
  "ten": {
    "predefined_graphs": [
      {
        "name": "test",
        "graph": {
          "connections": [
            {
              "extension": "test_ext",
              "cmd": [
                {
                  "name": "test_cmd",
                  "dest": [
                    {
                      "subgraph": "target_subgraph"
                    }
                  ]
                }
              ]
            }
          ]
        }
      }
    ]
  }
}"#;
        let result = ten_validate_property_json_string(property);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_msg_dest_selector() {
        let property = r#"{
  "ten": {
    "predefined_graphs": [
      {
        "name": "test",
        "graph": {
          "connections": [
            {
              "extension": "test_ext",
              "cmd": [
                {
                  "name": "test_cmd",
                  "dest": [
                    {
                      "selector": "target_selector"
                    }
                  ]
                }
              ]
            }
          ]
        }
      }
    ]
  }
}"#;
        let result = ten_validate_property_json_string(property);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_msg_dest_invalid_combination() {
        let property = r#"{
  "ten": {
    "predefined_graphs": [
      {
        "name": "test",
        "graph": {
          "connections": [
            {
              "extension": "test_ext",
              "cmd": [
                {
                  "name": "test_cmd",
                  "dest": [
                    {
                      "extension": "target_ext",
                      "subgraph": "target_subgraph"
                    }
                  ]
                }
              ]
            }
          ]
        }
      }
    ]
  }
}"#;
        let result = ten_validate_property_json_string(property);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_msg_source_extension_with_app() {
        let property = r#"{
  "ten": {
    "predefined_graphs": [
      {
        "name": "test",
        "graph": {
          "connections": [
            {
              "extension": "test_ext",
              "cmd": [
                {
                  "name": "test_cmd",
                  "source": [
                    {
                      "extension": "source_ext",
                      "app": "test_app"
                    }
                  ]
                }
              ]
            }
          ]
        }
      }
    ]
  }
}"#;
        let result = ten_validate_property_json_string(property);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_msg_source_subgraph() {
        let property = r#"{
  "ten": {
    "predefined_graphs": [
      {
        "name": "test",
        "graph": {
          "connections": [
            {
              "extension": "test_ext",
              "cmd": [
                {
                  "name": "test_cmd",
                  "source": [
                    {
                      "subgraph": "source_subgraph"
                    }
                  ]
                }
              ]
            }
          ]
        }
      }
    ]
  }
}"#;
        let result = ten_validate_property_json_string(property);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_msg_source_selector() {
        let property = r#"{
  "ten": {
    "predefined_graphs": [
      {
        "name": "test",
        "graph": {
          "connections": [
            {
              "extension": "test_ext",
              "cmd": [
                {
                  "name": "test_cmd",
                  "source": [
                    {
                      "selector": "source_selector"
                    }
                  ]
                }
              ]
            }
          ]
        }
      }
    ]
  }
}"#;
        let result = ten_validate_property_json_string(property);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_graph_node_extension() {
        let property = r#"{
  "ten": {
    "predefined_graphs": [
      {
        "name": "test",
        "graph": {
          "nodes": [
            {
              "type": "extension",
              "name": "test_ext",
              "addon": "test_addon",
              "extension_group": "test_group",
              "app": "test_app",
              "property": {
                "key1": "value1"
              }
            }
          ]
        }
      }
    ]
  }
}"#;
        let result = ten_validate_property_json_string(property);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_graph_node_subgraph() {
        let property = r#"{
  "ten": {
    "predefined_graphs": [
      {
        "name": "test",
        "graph": {
          "nodes": [
            {
              "type": "subgraph",
              "name": "test_subgraph",
              "graph": {
                "import_uri": "test.json"
              },
              "property": {
                "key1": "value1"
              }
            }
          ]
        }
      }
    ]
  }
}"#;
        let result = ten_validate_property_json_string(property);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_graph_node_extension_missing_required() {
        // missing addon
        let property = r#"
        {
          "ten": {
            "predefined_graphs": [{
              "name": "test",
              "nodes": [{
                "type": "extension",
                "name": "test_ext",
              }]
            }]
          }
        }
        "#;
        let result = ten_validate_property_json_string(property);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_graph_node_subgraph_missing_required() {
        // missing graph
        let property = r#"{
                            "ten": {
                              "predefined_graphs": [
                                {
                                  "name": "test",
                                  "graph": {
                                    "nodes": [
                                      {
                                        "type": "subgraph",
                                        "name": "test_subgraph"
                                      }
                                    ]
                                  }
                                }
                              ]
                            }
                          }"#;
        let result = ten_validate_property_json_string(property);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_graph_node_selector_missing_required() {
        // missing filter
        let property = r#"{
                            "ten": {
                              "predefined_graphs": [
                                {
                                  "name": "test",
                                  "graph": {
                                    "nodes": [
                                      {
                                        "type": "selector",
                                        "name": "test_selector"
                                      }
                                    ]
                                  }
                                }
                              ]
                            }
                          }"#;
        let result = ten_validate_property_json_string(property);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_selector_node_atomic_filter() {
        // Test atomic filter with exact operator
        let property = r#"{
                              "ten": {
                                "predefined_graphs": [
                                  {
                                    "name": "test",
                                    "graph": {
                                      "nodes": [
                                        {
                                          "type": "selector",
                                          "name": "test_selector",
                                          "filter": {
                                            "field": "name",
                                            "operator": "exact",
                                            "value": "test_extension"
                                          }
                                        }
                                      ]
                                    }
                                  }
                                ]
                              }
                            }"#;
        let result = ten_validate_property_json_string(property);
        assert!(result.is_ok());

        // Test atomic filter with regex operator
        let property = r#"{
                            "ten": {
                              "predefined_graphs": [
                                {
                                  "name": "test",
                                  "graph": {
                                    "nodes": [
                                      {
                                        "type": "selector",
                                        "name": "test_selector",
                                        "filter": {
                                          "field": "name",
                                          "operator": "regex",
                                          "value": "test.*"
                                        }
                                      }
                                    ]
                                  }
                                }
                              ]
                            }
                          }"#;
        let result = ten_validate_property_json_string(property);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_selector_node_compound_filter() {
        // Test AND filter
        let property = r#"{
                            "ten": {
                              "predefined_graphs": [
                                {
                                  "name": "test",
                                  "graph": {
                                    "nodes": [
                                      {
                                        "type": "selector",
                                        "name": "test_selector",
                                        "filter": {
                                          "and": [
                                            {
                                              "field": "name",
                                              "operator": "regex",
                                              "value": "test.*"
                                            },
                                            {
                                              "field": "type",
                                              "operator": "exact",
                                              "value": "extension"
                                            }
                                          ]
                                        }
                                      }
                                    ]
                                  }
                                }
                              ]
                            }
                          }"#;
        let result = ten_validate_property_json_string(property);
        assert!(result.is_ok());

        // Test OR filter
        let property = r#"{
                            "ten": {
                              "predefined_graphs": [
                                {
                                  "name": "test",
                                  "graph": {
                                    "nodes": [
                                      {
                                        "type": "selector",
                                        "name": "test_selector",
                                        "filter": {
                                          "or": [
                                            {
                                              "field": "name",
                                              "operator": "exact",
                                              "value": "test1"
                                            },
                                            {
                                              "field": "name",
                                              "operator": "exact",
                                              "value": "test2"
                                            }
                                          ]
                                        }
                                      }
                                    ]
                                  }
                                }
                              ]
                            }
                          }"#;
        let result = ten_validate_property_json_string(property);
        assert!(result.is_ok());

        // Test nested AND/OR filter
        let property = r#"{
                            "ten": {
                              "predefined_graphs": [
                                {
                                  "name": "test",
                                  "graph": {
                                    "nodes": [
                                      {
                                        "type": "selector",
                                        "name": "test_selector",
                                        "filter": {
                                          "and": [
                                            {
                                              "field": "type",
                                              "operator": "exact",
                                              "value": "extension"
                                            },
                                            {
                                              "or": [
                                                {
                                                  "field": "name",
                                                  "operator": "exact",
                                                  "value": "test1"
                                                },
                                                {
                                                  "field": "name",
                                                  "operator": "exact",
                                                  "value": "test2"
                                                }
                                              ]
                                            }
                                          ]
                                        }
                                      }
                                    ]
                                  }
                                }
                              ]
                            }
                          }"#;
        let result = ten_validate_property_json_string(property);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_selector_node_invalid_filter() {
        // Test missing required field in atomic filter
        let property = r#"{
                            "ten": {
                              "predefined_graphs": [
                                {
                                  "name": "test",
                                  "graph": {
                                    "nodes": [
                                      {
                                        "type": "selector",
                                        "name": "test_selector",
                                        "filter": {
                                          "field": "name",
                                          "operator": "exact"
                                        }
                                      }
                                    ]
                                  }
                                }
                              ]
                            }
                          }"#;
        let result = ten_validate_property_json_string(property);
        assert!(result.is_err());

        // Test empty AND array
        let property = r#"{
                            "ten": {
                              "predefined_graphs": [
                                {
                                  "name": "test",
                                  "graph": {
                                    "nodes": [
                                      {
                                        "type": "selector",
                                        "name": "test_selector",
                                        "filter": {
                                          "and": []
                                        }
                                      }
                                    ]
                                  }
                                }
                              ]
                            }
                          }"#;
        let result = ten_validate_property_json_string(property);
        assert!(result.is_err());

        // Test invalid operator
        let property = r#"{
                            "ten": {
                              "predefined_graphs": [
                                {
                                  "name": "test",
                                  "graph": {
                                    "nodes": [
                                      {
                                        "type": "selector",
                                        "name": "test_selector",
                                        "filter": {
                                          "field": "name",
                                          "operator": "contains",
                                          "value": "test"
                                        }
                                      }
                                    ]
                                  }
                                }
                              ]
                            }
                          }"#;
        let result = ten_validate_property_json_string(property);
        assert!(result.is_err());

        // Test empty value string
        let property = r#"{
                            "ten": {
                              "predefined_graphs": [
                                {
                                  "name": "test",
                                  "graph": {
                                    "nodes": [
                                      {
                                        "type": "selector",
                                        "name": "test_selector",
                                        "filter": {
                                          "field": "name",
                                          "operator": "exact",
                                          "value": ""
                                        }
                                      }
                                    ]
                                  }
                                }
                              ]
                            }
                          }"#;
        let result = ten_validate_property_json_string(property);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_selector_node_additional_properties() {
        // Test additional properties in selector
        let property = r#"{
                            "ten": {
                              "predefined_graphs": [
                                {
                                  "name": "test",
                                  "graph": {
                                    "nodes": [
                                      {
                                        "type": "selector",
                                        "name": "test_selector",
                                        "filter": {
                                          "field": "name",
                                          "operator": "exact",
                                          "value": "test",
                                          "extra": "invalid"
                                        }
                                      }
                                    ]
                                  }
                                }
                              ]
                            }
                          }"#;
        let result = ten_validate_property_json_string(property);
        assert!(result.is_err());

        // Test additional properties in selector node
        let property = r#"{
                            "ten": {
                              "predefined_graphs": [
                                {
                                  "name": "test",
                                  "graph": {
                                    "nodes": [
                                      {
                                        "type": "selector",
                                        "name": "test_selector",
                                        "filter": {
                                          "field": "name",
                                          "operator": "exact",
                                          "value": "test"
                                        },
                                        "extra": "invalid"
                                      }
                                    ]
                                  }
                                }
                              ]
                            }
                          }"#;
        let result = ten_validate_property_json_string(property);
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("Additional properties are not allowed"));
    }

    // Tests for interface.json API description support
    #[test]
    fn test_validate_interface_cmd_in_with_string_description() {
        // Test that cmd_in in interface.json with string description succeeds
        let interface = r#"
        {
          "cmd_in": [
            {
              "name": "search",
              "property": {
                "properties": {
                  "query": {
                    "type": "string",
                    "description": "Search query text"
                  },
                  "limit": {
                    "type": "int32",
                    "description": "Maximum number of results"
                  }
                },
                "required": ["query"]
              }
            }
          ]
        }
        "#;

        let result = ten_validate_interface_json_string(interface);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_interface_cmd_in_with_localized_description() {
        // Test that cmd_in in interface.json with localizedText description succeeds
        let interface = r#"
        {
          "cmd_in": [
            {
              "name": "execute",
              "property": {
                "properties": {
                  "action": {
                    "type": "string",
                    "description": {
                      "locales": {
                        "en-US": {
                          "content": "Action to execute"
                        },
                        "zh-CN": {
                          "content": "要执行的动作"
                        }
                      }
                    }
                  }
                }
              }
            }
          ]
        }
        "#;

        let result = ten_validate_interface_json_string(interface);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_interface_cmd_out_with_description() {
        // Test that cmd_out with description succeeds
        let interface = r#"
        {
          "cmd_out": [
            {
              "name": "result",
              "property": {
                "properties": {
                  "status": {
                    "type": "string",
                    "description": "Operation status"
                  },
                  "message": {
                    "type": "string",
                    "description": {
                      "locales": {
                        "en-US": {
                          "content": "Status message"
                        },
                        "zh-CN": {
                          "content": "状态消息"
                        }
                      }
                    }
                  }
                }
              },
              "result": {
                "property": {
                  "properties": {
                    "data": {
                      "type": "string",
                      "description": "Result data"
                    }
                  }
                }
              }
            }
          ]
        }
        "#;

        let result = ten_validate_interface_json_string(interface);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_interface_data_in_with_description() {
        // Test that data_in with description succeeds
        let interface = r#"
        {
          "data_in": [
            {
              "name": "input_data",
              "property": {
                "properties": {
                  "content": {
                    "type": "string",
                    "description": "Input content"
                  },
                  "metadata": {
                    "type": "object",
                    "description": {
                      "locales": {
                        "en-US": {
                          "content": "Metadata information"
                        },
                        "zh-CN": {
                          "content": "元数据信息"
                        }
                      }
                    },
                    "properties": {
                      "timestamp": {
                        "type": "int64",
                        "description": "Unix timestamp"
                      }
                    }
                  }
                }
              }
            }
          ]
        }
        "#;

        let result = ten_validate_interface_json_string(interface);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_interface_data_out_with_description() {
        // Test that data_out with description succeeds
        let interface = r#"
        {
          "data_out": [
            {
              "name": "output_data",
              "property": {
                "properties": {
                  "result": {
                    "type": "string",
                    "description": "Output result"
                  },
                  "confidence": {
                    "type": "float64",
                    "description": {
                      "locales": {
                        "en-US": {
                          "content": "Confidence score"
                        },
                        "zh-CN": {
                          "content": "置信度分数"
                        }
                      }
                    }
                  }
                }
              }
            }
          ]
        }
        "#;

        let result = ten_validate_interface_json_string(interface);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_interface_audio_frame_with_description() {
        // Test that audio_frame_in/out with description succeeds
        let interface = r#"
        {
          "audio_frame_in": [
            {
              "name": "audio_input",
              "property": {
                "properties": {
                  "sample_rate": {
                    "type": "int32",
                    "description": "Audio sample rate in Hz"
                  },
                  "channels": {
                    "type": "int32",
                    "description": {
                      "locales": {
                        "en-US": {
                          "content": "Number of audio channels"
                        },
                        "zh-CN": {
                          "content": "音频通道数"
                        }
                      }
                    }
                  }
                }
              }
            }
          ],
          "audio_frame_out": [
            {
              "name": "audio_output",
              "property": {
                "properties": {
                  "format": {
                    "type": "string",
                    "description": "Audio format"
                  }
                }
              }
            }
          ]
        }
        "#;

        let result = ten_validate_interface_json_string(interface);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_interface_video_frame_with_description() {
        // Test that video_frame_in/out with description succeeds
        let interface = r#"
        {
          "video_frame_in": [
            {
              "name": "video_input",
              "property": {
                "properties": {
                  "width": {
                    "type": "int32",
                    "description": "Video width in pixels"
                  },
                  "height": {
                    "type": "int32",
                    "description": {
                      "locales": {
                        "en-US": {
                          "content": "Video height in pixels"
                        },
                        "zh-CN": {
                          "content": "视频高度（像素）"
                        }
                      }
                    }
                  }
                }
              }
            }
          ],
          "video_frame_out": [
            {
              "name": "video_output",
              "property": {
                "properties": {
                  "fps": {
                    "type": "int32",
                    "description": "Frames per second"
                  }
                }
              }
            }
          ]
        }
        "#;

        let result = ten_validate_interface_json_string(interface);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_interface_result_property_with_description() {
        // Test that result properties with description succeed
        let interface = r#"
        {
          "cmd_in": [
            {
              "name": "process",
              "property": {
                "properties": {
                  "input": {
                    "type": "string",
                    "description": "Input data"
                  }
                }
              },
              "result": {
                "property": {
                  "properties": {
                    "output": {
                      "type": "string",
                      "description": "Processed output"
                    },
                    "error": {
                      "type": "string",
                      "description": {
                        "locales": {
                          "en-US": {
                            "content": "Error message if any"
                          },
                          "zh-CN": {
                            "content": "错误消息（如果有）"
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          ]
        }
        "#;

        let result = ten_validate_interface_json_string(interface);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_asr_interface() {
        let interface = r#"
{
    "property": {
        "properties": {
            "url": {
                "type": "string"
            },
            "headers": {
                "type": "object",
                "properties": {}
            },
            "params": {
                "type": "object",
                "properties": {}
            },
            "dump": {
                "type": "bool"
            },
            "dump_path": {
                "type": "string"
            }
        }
    },
    "audio_frame_in": [
        {
            "name": "pcm_frame",
            "property": {
                "properties": {
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "session_id": {
                                "type": "string"
                            }
                        }
                    }
                }
            }
        }
    ],
    "data_in": [
        {
            "name": "asr_finalize",
            "property": {
                "properties": {
                    "finalize_id": {
                        "type": "string"
                    },
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "session_id": {
                                "type": "string"
                            }
                        }
                    }
                }
            }
        }
    ],
    "data_out": [
        {
            "name": "asr_result",
            "property": {
                "properties": {
                    "id": {
                        "type": "string"
                    },
                    "text": {
                        "type": "string"
                    },
                    "final": {
                        "type": "bool"
                    },
                    "start_ms": {
                        "type": "int64"
                    },
                    "duration_ms": {
                        "type": "int64"
                    },
                    "language": {
                        "type": "string"
                    },
                    "words": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "word": {
                                    "type": "string"
                                },
                                "start_ms": {
                                    "type": "int64"
                                },
                                "duration_ms": {
                                    "type": "int64"
                                },
                                "stable": {
                                    "type": "bool"
                                }
                            }
                        }
                    },
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "session_id": {
                                "type": "string"
                            },
                            "asr_info": {
                                "type": "object",
                                "properties": {}
                            }
                        }
                    }
                }
            },
            "required": [
                "id",
                "text",
                "final",
                "start_ms",
                "duration_ms",
                "language"
            ]
        },
        {
            "name": "asr_finalize_end",
            "property": {
                "properties": {
                    "finalize_id": {
                        "type": "string"
                    },
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "session_id": {
                                "type": "string"
                            }
                        }
                    }
                }
            }
        },
        {
            "name": "error",
            "property": {
                "properties": {
                    "id": {
                        "type": "string"
                    },
                    "module": {
                        "type": "string"
                    },
                    "code": {
                        "type": "int64"
                    },
                    "message": {
                        "type": "string"
                    },
                    "vendor_info": {
                        "type": "object",
                        "properties": {
                            "vendor": {
                                "type": "string"
                            },
                            "code": {
                                "type": "string"
                            },
                            "message": {
                                "type": "string"
                            }
                        }
                    },
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "session_id": {
                                "type": "string"
                            }
                        }
                    }
                }
            },
            "required": [
                "module",
                "code",
                "message"
            ]
        },
        {
            "name": "metrics",
            "property": {
                "properties": {
                    "id": {
                        "type": "string"
                    },
                    "module": {
                        "type": "string"
                    },
                    "vendor": {
                        "type": "string"
                    },
                    "metrics": {
                        "type": "object",
                        "properties": {}
                    },
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "session_id": {
                                "type": "string"
                            }
                        }
                    }
                }
            },
            "required": [
                "module",
                "vendor",
                "metrics"
            ]
        },
        {
            "name": "connected",
            "property": {
                "properties": {
                    "id": {
                        "type": "string"
                    },
                    "module": {
                        "type": "string"
                    },
                    "vendor": {
                        "type": "string"
                    },
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "session_id": {
                                "type": "string"
                            }
                        }
                    }
                }
            }
        },
        {
            "name": "disconnected",
            "property": {
                "properties": {
                    "id": {
                        "type": "string"
                    },
                    "module": {
                        "type": "string"
                    },
                    "vendor": {
                        "type": "string"
                    },
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "session_id": {
                                "type": "string"
                            }
                        }
                    }
                }
            }
        }
    ],
    "cmd_in": [
        {
            "name": "update_configs",
            "property": {
                "properties": {
                    "url": {
                        "type": "string"
                    },
                    "headers": {
                        "type": "object",
                        "properties": {}
                    },
                    "params": {
                        "type": "object",
                        "properties": {}
                    },
                    "dump": {
                        "type": "bool"
                    }
                }
            },
            "result": {
                "property": {
                    "properties": {
                        "code": {
                            "type": "int64"
                        },
                        "message": {
                            "type": "string"
                        }
                    }
                }
            }
        }
    ]
}
"#;

        let result = ten_validate_interface_json_string(interface);
        println!("result: {:?}", result);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_tts_interface() {
        let interface = r#"
{
    "property": {
        "properties": {
            "url": {
                "type": "string"
            },
            "headers": {
                "type": "object",
                "properties": {}
            },
            "params": {
                "type": "object",
                "properties": {}
            },
            "dump": {
                "type": "bool"
            },
            "dump_path": {
                "type": "string"
            },
            "enable_words": {
                "type": "bool"
            }
        }
    },
    "audio_frame_out": [
        {
            "name": "pcm_frame",
            "property": {
                "properties": {
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "session_id": {
                                "type": "string"
                            },
                            "turn_id": {
                                "type": "int64"
                            }
                        }
                    }
                }
            }
        }
    ],
    "data_in": [
        {
            "name": "tts_text_input",
            "property": {
                "properties": {
                    "request_id": {
                        "type": "string"
                    },
                    "text": {
                        "type": "string"
                    },
                    "text_input_end": {
                        "type": "bool"
                    },
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "session_id": {
                                "type": "string"
                            },
                            "turn_id": {
                                "type": "int64"
                            }
                        }
                    }
                }
            },
            "required": [
                "request_id",
                "text"
            ]
        },
        {
            "name": "tts_flush",
            "property": {
                "properties": {
                    "flush_id": {
                        "type": "string"
                    },
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "session_id": {
                                "type": "string"
                            }
                        }
                    }
                }
            }
        }
    ],
    "data_out": [
        {
            "name": "tts_text_result",
            "property": {
                "properties": {
                    "request_id": {
                        "type": "string"
                    },
                    "text": {
                        "type": "string"
                    },
                    "start_ms": {
                        "type": "int64"
                    },
                    "duration_ms": {
                        "type": "int64"
                    },
                    "words": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "word": {
                                    "type": "string"
                                },
                                "start_ms": {
                                    "type": "int64"
                                },
                                "duration_ms": {
                                    "type": "int64"
                                }
                            },
                            "required": [
                                "word",
                                "start_ms",
                                "duration_ms"
                            ]
                        }
                    },
                    "text_result_end": {
                        "type": "bool"
                    },
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "session_id": {
                                "type": "string"
                            },
                            "turn_id": {
                                "type": "int64"
                            }
                        }
                    }
                }
            },
            "required": [
                "request_id",
                "text",
                "start_ms",
                "duration_ms",
                "words"
            ]
        },
        {
            "name": "tts_flush_end",
            "property": {
                "properties": {
                    "flush_id": {
                        "type": "string"
                    },
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "session_id": {
                                "type": "string"
                            }
                        }
                    }
                }
            }
        },
        {
            "name": "tts_audio_start",
            "property": {
                "properties": {
                    "request_id": {
                        "type": "string"
                    },
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "session_id": {
                                "type": "string"
                            },
                            "turn_id": {
                                "type": "int64"
                            }
                        }
                    }
                }
            }
        },
        {
            "name": "tts_audio_end",
            "property": {
                "properties": {
                    "request_id": {
                        "type": "string"
                    },
                    "request_event_interval_ms": {
                        "type": "int64"
                    },
                    "request_total_audio_duration_ms": {
                        "type": "int64"
                    },
                    "reason": {
                        "type": "int64"
                    },
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "session_id": {
                                "type": "string"
                            },
                            "turn_id": {
                                "type": "int64"
                            }
                        }
                    }
                }
            }
        },
        {
            "name": "error",
            "property": {
                "properties": {
                    "id": {
                        "type": "string"
                    },
                    "module": {
                        "type": "string"
                    },
                    "code": {
                        "type": "int64"
                    },
                    "message": {
                        "type": "string"
                    },
                    "vendor_info": {
                        "type": "object",
                        "properties": {
                            "vendor": {
                                "type": "string"
                            },
                            "code": {
                                "type": "string"
                            },
                            "message": {
                                "type": "string"
                            }
                        }
                    },
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "session_id": {
                                "type": "string"
                            },
                            "turn_id": {
                                "type": "int64"
                            }
                        }
                    }
                }
            },
            "required": [
                "module",
                "code",
                "message"
            ]
        },
        {
            "name": "metrics",
            "property": {
                "properties": {
                    "id": {
                        "type": "string"
                    },
                    "module": {
                        "type": "string"
                    },
                    "vendor": {
                        "type": "string"
                    },
                    "metrics": {
                        "type": "object",
                        "properties": {}
                    },
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "session_id": {
                                "type": "string"
                            },
                            "turn_id": {
                                "type": "int64"
                            }
                        }
                    }
                }
            },
            "required": [
                "module",
                "vendor",
                "metrics"
            ]
        }
    ],
    "cmd_in": [
        {
            "name": "update_configs",
            "property": {
                "properties": {
                    "url": {
                        "type": "string"
                    },
                    "headers": {
                        "type": "object",
                        "properties": {}
                    },
                    "params": {
                        "type": "object",
                        "properties": {}
                    },
                    "dump": {
                        "type": "bool"
                    },
                    "enable_words": {
                        "type": "bool"
                    }
                }
            },
            "result": {
                "property": {
                    "properties": {
                        "code": {
                            "type": "int64"
                        },
                        "message": {
                            "type": "string"
                        }
                    }
                }
            }
        }
    ]
}
"#;
        let result = ten_validate_interface_json_string(interface);
        println!("result: {:?}", result);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_manifest_top_level_description_must_be_localized() {
        // Test that top-level description does NOT support simple string (must be
        // localizedText)
        let manifest = r#"
        {
          "type": "extension",
          "name": "test_extension",
          "version": "0.1.0",
          "description": "This simple string should fail",
          "dependencies": []
        }
        "#;

        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_err());
        let error_msg = result.unwrap_err().to_string();
        // Should fail because description at top level requires localizedText format
        // (object type)
        assert!(error_msg.contains("is not of type \"object\""));
    }

    #[test]
    fn test_validate_api_description_supports_both_formats() {
        // Test that API description supports BOTH string and localizedText
        let manifest = r#"
        {
          "type": "extension",
          "name": "test_extension",
          "version": "0.1.0",
          "description": {
            "locales": {
              "en-US": {
                "content": "Top-level must be localized"
              }
            }
          },
          "dependencies": [],
          "api": {
            "property": {
              "properties": {
                "simple_prop": {
                  "type": "string",
                  "description": "Simple string description for API property"
                },
                "localized_prop": {
                  "type": "string",
                  "description": {
                    "locales": {
                      "en-US": {
                        "content": "Localized description for API property"
                      }
                    }
                  }
                }
              }
            }
          }
        }
        "#;

        let result = ten_validate_manifest_json_string(manifest);
        assert!(result.is_ok());
    }
}
