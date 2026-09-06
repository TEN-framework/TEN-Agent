//
// Copyright © 2025 Agora
// This file is part of TEN Framework, an open source project.
// Licensed under the Apache License, Version 2.0, with certain conditions.
// Refer to the "LICENSE" file in the root directory for more information.
//
mod bindings;
mod definition;

extern crate anyhow;
extern crate jsonschema;
extern crate serde_json;

use std::path::Path;

use anyhow::Result;
use json5;
use jsonschema::Validator;

fn load_schema(content: &str) -> Validator {
    // Use json5 to strip comments from the json string.
    let schema_json: serde_json::Value = json5::from_str(content).unwrap();

    jsonschema::validator_for(&schema_json).unwrap()
}

/// Combines a schema with shared definitions by merging the $defs sections
fn load_schema_with_shared_definitions(
    schema_content: &str,
    shared_definitions: &str,
) -> Result<Validator> {
    // Parse both schemas
    let mut main_schema: serde_json::Value = json5::from_str(schema_content)?;
    let shared_schema: serde_json::Value = json5::from_str(shared_definitions)?;

    // Get the shared definitions
    if let Some(shared_defs) = shared_schema.get("$defs") {
        // Ensure the main schema has a $defs section
        if main_schema.get("$defs").is_none() {
            main_schema["$defs"] = serde_json::json!({});
        }

        // Merge shared definitions into main schema $defs
        if let Some(main_defs) = main_schema.get_mut("$defs").and_then(|v| v.as_object_mut()) {
            if let Some(shared_defs_obj) = shared_defs.as_object() {
                for (key, value) in shared_defs_obj {
                    main_defs.insert(key.clone(), value.clone());
                }
            }
        }
    }

    Ok(jsonschema::validator_for(&main_schema)?)
}

fn load_schema_with_extra_definitions(
    schema_content: &str,
    extra_definitions_schema: &str,
) -> Result<Validator> {
    let mut main_schema: serde_json::Value = json5::from_str(schema_content)?;
    let extra_schema: serde_json::Value = json5::from_str(extra_definitions_schema)?;

    if let Some(extra_defs) = extra_schema.get("$defs") {
        if main_schema.get("$defs").is_none() {
            main_schema["$defs"] = serde_json::json!({});
        }

        if let Some(main_defs) = main_schema.get_mut("$defs").and_then(|v| v.as_object_mut()) {
            if let Some(extra_defs_obj) = extra_defs.as_object() {
                for (key, value) in extra_defs_obj {
                    main_defs.insert(key.clone(), value.clone());
                }
            }
        }
    }

    Ok(jsonschema::validator_for(&main_schema)?)
}

fn validate_json_object(json: &serde_json::Value, schema_str: &str) -> Result<()> {
    let validator = load_schema(schema_str);

    match validator.validate(json) {
        Ok(()) => Ok(()),
        Err(_) => {
            let mut msgs = String::new();
            for error in validator.iter_errors(json) {
                msgs.push_str(&format!("{} @ {}\n", error, error.instance_path));
            }
            Err(anyhow::anyhow!("{}", msgs))
        }
    }
}

fn validate_json_object_with_shared_definitions(
    json: &serde_json::Value,
    schema_str: &str,
    shared_definitions: &str,
) -> Result<()> {
    let validator = load_schema_with_shared_definitions(schema_str, shared_definitions)?;

    match validator.validate(json) {
        Ok(()) => Ok(()),
        Err(_) => {
            let mut msgs = String::new();
            for error in validator.iter_errors(json) {
                msgs.push_str(&format!("{} @ {}\n", error, error.instance_path));
            }
            Err(anyhow::anyhow!("{}", msgs))
        }
    }
}

fn validate_json_object_with_extra_definitions(
    json: &serde_json::Value,
    schema_str: &str,
    extra_definitions_schema: &str,
) -> Result<()> {
    let validator = load_schema_with_extra_definitions(schema_str, extra_definitions_schema)?;

    match validator.validate(json) {
        Ok(()) => Ok(()),
        Err(_) => {
            let mut msgs = String::new();
            for error in validator.iter_errors(json) {
                msgs.push_str(&format!("{} @ {}\n", error, error.instance_path));
            }
            Err(anyhow::anyhow!("{}", msgs))
        }
    }
}

pub fn ten_validate_manifest_json_string(data: &str) -> Result<()> {
    let manifest_json: serde_json::Value = serde_json::from_str(data)?;
    validate_json_object_with_shared_definitions(
        &manifest_json,
        definition::MANIFEST_SCHEMA_DEFINITION,
        definition::SHARED_DEFINITIONS_SCHEMA,
    )
}

pub fn ten_validate_manifest_json_file(file_path: &str) -> Result<()> {
    let file = std::fs::File::open(file_path)?;
    let reader = std::io::BufReader::new(file);
    let manifest_json: serde_json::Value = serde_json::from_reader(reader)?;

    validate_json_object_with_shared_definitions(
        &manifest_json,
        definition::MANIFEST_SCHEMA_DEFINITION,
        definition::SHARED_DEFINITIONS_SCHEMA,
    )
}

pub fn validate_manifest_lock_json_string(data: &str) -> Result<()> {
    let manifest_lock_json: serde_json::Value = serde_json::from_str(data)?;
    validate_json_object(&manifest_lock_json, definition::MANIFEST_LOCK_SCHEMA_DEFINITION)
}

pub fn validate_manifest_lock_json_file(file_path: &str) -> Result<()> {
    let file = std::fs::File::open(file_path)?;
    let reader = std::io::BufReader::new(file);
    let manifest_lock_json: serde_json::Value = serde_json::from_reader(reader)?;

    validate_json_object(&manifest_lock_json, definition::MANIFEST_LOCK_SCHEMA_DEFINITION)
}

pub fn ten_validate_property_json_string(data: &str) -> Result<()> {
    let property_json: serde_json::Value = serde_json::from_str(data)?;
    validate_json_object_with_extra_definitions(
        &property_json,
        definition::PROPERTY_SCHEMA_DEFINITION,
        definition::GRAPH_SCHEMA_DEFINITION,
    )
}

pub fn ten_validate_property_json_file<P: AsRef<Path>>(file_path: P) -> Result<()> {
    let file = std::fs::File::open(file_path)?;
    let reader = std::io::BufReader::new(file);
    let property_json: serde_json::Value = serde_json::from_reader(reader)?;

    validate_json_object_with_extra_definitions(
        &property_json,
        definition::PROPERTY_SCHEMA_DEFINITION,
        definition::GRAPH_SCHEMA_DEFINITION,
    )
}

pub fn ten_validate_graph_json_string(data: &str) -> Result<()> {
    let graph_json: serde_json::Value = serde_json::from_str(data)?;
    validate_json_object(&graph_json, definition::GRAPH_SCHEMA_DEFINITION)
}

pub fn ten_validate_interface_json_string(data: &str) -> Result<()> {
    let interface_json: serde_json::Value = serde_json::from_str(data)?;
    validate_json_object_with_shared_definitions(
        &interface_json,
        definition::INTERFACE_SCHEMA_DEFINITION,
        definition::SHARED_DEFINITIONS_SCHEMA,
    )
}

pub fn ten_validate_interface_json_file<P: AsRef<Path>>(file_path: P) -> Result<()> {
    let file = std::fs::File::open(file_path)?;
    let reader = std::io::BufReader::new(file);
    let interface_json: serde_json::Value = serde_json::from_reader(reader)?;

    validate_json_object_with_shared_definitions(
        &interface_json,
        definition::INTERFACE_SCHEMA_DEFINITION,
        definition::SHARED_DEFINITIONS_SCHEMA,
    )
}
