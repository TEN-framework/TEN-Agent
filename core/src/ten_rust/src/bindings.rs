//
// Copyright © 2025 Agora
// This file is part of TEN Framework, an open source project.
// Licensed under the Apache License, Version 2.0, with certain conditions.
// Refer to the "LICENSE" file in the root directory for more information.
//
use std::ffi::{c_char, CStr, CString};

use tokio::runtime::Runtime;

use crate::{
    graph::{graph_info::GraphInfo, Graph},
    json_schema::ten_validate_graph_json_string,
    pkg_info::manifest::api::ManifestApi,
};

/// Frees a C string that was allocated by Rust.
///
/// # Safety
///
/// This function takes ownership of a raw pointer and frees it. The caller must
/// ensure that the pointer was originally allocated by Rust and that it is not
/// used after being freed. Passing a null pointer is safe, as the function will
/// simply return in that case.
#[no_mangle]
pub extern "C" fn ten_rust_free_cstring(ptr: *const c_char) {
    if ptr.is_null() {
        return;
    }
    unsafe {
        // Cast away const-ness to take ownership back and let it drop.
        let ptr = ptr as *mut c_char;
        let _ = CString::from_raw(ptr);
    }
}

/// Parses a JSON string into a GraphInfo and returns it as a JSON string.
///
/// This function takes a C string containing JSON, parses it into a GraphInfo
/// structure, validates and processes it, then serializes it back to JSON.
///
/// # Parameters
/// - `json_str`: A null-terminated C string containing the JSON representation
///   of a graph. Must not be NULL.
/// - `current_base_dir`: A null-terminated C string containing the current base
///   directory. Can be NULL if the current base directory is not known.
/// - `err_msg`: Pointer to a char* that will be set to an error message if the
///   function fails. Can be NULL if error details are not needed. If set, the
///   error message must be freed using `ten_rust_free_cstring()`.
///
/// # Returns
/// - On success: A pointer to a newly allocated C string containing the
///   processed graph JSON
/// - On failure: NULL pointer
///
/// # Safety
///
/// The caller must ensure that:
/// - `json_str` is a valid null-terminated C string
/// - `current_base_dir` is a valid null-terminated C string, or NULL
/// - The returned pointer (if not null) is freed using
///   `ten_rust_free_cstring()`
/// - If err_msg is not NULL, the error message (if set) must be freed using
///   `ten_rust_free_cstring()`
/// - The input string contains valid UTF-8 encoded JSON
///
/// # Memory Management
///
/// Both the returned string and error message (if set) are allocated by Rust
/// and must be freed by calling `ten_rust_free_cstring()` when no longer
/// needed.
///
/// # Example
/// ```c
/// const char* input_json = "{\"nodes\": []}";
/// const char* current_base_dir = "/path/to/current/base/dir";
/// char* err_msg = NULL;
/// const char* result =
///     ten_rust_predefined_graph_validate_complete_flatten(
///         input_json, current_base_dir, &err_msg);
/// if (result != NULL) {
///     printf("Processed graph: %s\n", result);
///     ten_rust_free_cstring(result);
/// } else if (err_msg != NULL) {
///     printf("Failed to process graph: %s\n", err_msg);
///     ten_rust_free_cstring(err_msg);
/// } else {
///     printf("Failed to process graph\n");
/// }
/// ```
#[no_mangle]
pub unsafe extern "C" fn ten_rust_predefined_graph_validate_complete_flatten(
    json_str: *const c_char,
    current_base_dir: *const c_char,
    err_msg: *mut *mut c_char,
) -> *const c_char {
    if json_str.is_null() {
        if !err_msg.is_null() {
            let err_msg_c_str = CString::new("json_str is null").unwrap();
            *err_msg = err_msg_c_str.into_raw();
        }
        return std::ptr::null();
    }

    // Convert C string to Rust string
    let json_str_c_str = CStr::from_ptr(json_str);
    let json_str_rust_str = match json_str_c_str.to_str() {
        Ok(s) => s,
        Err(e) => {
            if !err_msg.is_null() {
                let err_msg_c_str = CString::new(e.to_string()).unwrap();
                *err_msg = err_msg_c_str.into_raw();
            }
            return std::ptr::null(); // Invalid UTF-8
        }
    };

    let current_base_dir_rust_str = if current_base_dir.is_null() {
        None
    } else {
        let current_base_dir_c_str = CStr::from_ptr(current_base_dir);
        let current_base_dir_rust_str = match current_base_dir_c_str.to_str() {
            Ok(s) => s,
            Err(e) => {
                if !err_msg.is_null() {
                    let err_msg_c_str = CString::new(e.to_string()).unwrap();
                    *err_msg = err_msg_c_str.into_raw();
                }
                return std::ptr::null(); // Invalid UTF-8
            }
        };
        Some(current_base_dir_rust_str)
    };

    let rt = Runtime::new().unwrap();

    // Parse the JSON string into a Graph
    let mut graph_info = {
        match rt.block_on(GraphInfo::from_str_with_base_dir(
            json_str_rust_str,
            current_base_dir_rust_str,
        )) {
            Ok(g) => g,
            Err(e) => {
                if !err_msg.is_null() {
                    let err_msg_c_str = CString::new(e.to_string()).unwrap();
                    *err_msg = err_msg_c_str.into_raw();
                }
                return std::ptr::null(); // Parsing failed
            }
        }
    };

    // Serialize the graph back to JSON
    let json_output = match rt.block_on(graph_info.to_json_with_flattened_graph()) {
        Ok(json) => json,
        Err(e) => {
            if !err_msg.is_null() {
                let err_msg_c_str = CString::new(e.to_string()).unwrap();
                *err_msg = err_msg_c_str.into_raw();
            }
            return std::ptr::null(); // Serialization failed
        }
    };

    // Convert to C string
    match CString::new(json_output) {
        Ok(c_string) => c_string.into_raw(),
        Err(e) => {
            if !err_msg.is_null() {
                let err_msg_c_str = CString::new(e.to_string()).unwrap();
                *err_msg = err_msg_c_str.into_raw();
            }
            std::ptr::null() // Contains null bytes
        }
    }
}

/// Validates a manifest API and returns it as a JSON string.
///
/// This function takes a C string containing JSON, parses it into a ManifestApi
/// structure, validates and flattens it, then serializes it back to JSON. If
/// flattening is not needed, it will still return a new copy of the input JSON.
///
/// # Parameters
/// - `manifest_api_json_str`: A null-terminated C string containing the JSON
///   representation of a manifest API. Must not be NULL.
/// - `current_base_dir`: A null-terminated C string containing the current base
///   directory. Must not be NULL.
/// - `err_msg`: Pointer to a char* that will be set to an error message if the
///   function fails. Can be NULL if error details are not needed. If set, the
///   error message must be freed using `ten_rust_free_cstring()`.
///
/// # Returns
/// - On success: A pointer to a newly allocated C string containing either the
///   flattened manifest API JSON or a copy of the input JSON. The caller is
///   responsible for freeing this string using `ten_rust_free_cstring()`.
/// - On failure: NULL pointer
///
/// # Safety
///
/// The caller must ensure that:
/// - `manifest_api_json_str` is a valid null-terminated C string
/// - `current_base_dir` is a valid null-terminated C string
/// - If err_msg is not NULL, the error message (if set) must be freed using
///   `ten_rust_free_cstring()`
/// - The input string contains valid UTF-8 encoded JSON
///
/// # Memory Management
///
/// Both the returned string (if not NULL) and error message (if set) are
/// allocated by Rust and must be freed by calling `ten_rust_free_cstring()`
/// when no longer needed.
///
/// # Example
/// ```c
/// const char* manifest_api_json_str = "{\"interface\": []}";
/// const char* current_base_dir = "/path/to/current/base/dir";
/// char* err_msg = NULL;
/// const char* result =
///     ten_rust_manifest_api_flatten(
///         manifest_api_json_str, current_base_dir, &err_msg);
/// if (result != NULL) {
///     printf("Processed manifest API: %s\n", result);
///     ten_rust_free_cstring(result);
/// } else if (err_msg != NULL) {
///     printf("Failed to process manifest API: %s\n", err_msg);
///     ten_rust_free_cstring(err_msg);
/// } else {
///     printf("Failed to process manifest API\n");
/// }
/// ```
#[no_mangle]
pub unsafe extern "C" fn ten_rust_manifest_api_flatten(
    manifest_api_json_str: *const c_char,
    current_base_dir: *const c_char,
    app_base_dir: *const c_char,
    err_msg: *mut *mut c_char,
) -> *const c_char {
    if manifest_api_json_str.is_null() {
        if !err_msg.is_null() {
            let err_msg_c_str = CString::new("manifest_api_json_str is null").unwrap();
            *err_msg = err_msg_c_str.into_raw();
        }
        return std::ptr::null();
    }

    // Convert C string to Rust string
    let manifest_api_json_str_c_str = CStr::from_ptr(manifest_api_json_str);
    let manifest_api_json_str_rust_str = match manifest_api_json_str_c_str.to_str() {
        Ok(s) => s,
        Err(e) => {
            if !err_msg.is_null() {
                let err_msg_c_str = CString::new(e.to_string()).unwrap();
                *err_msg = err_msg_c_str.into_raw();
            }
            return std::ptr::null(); // Invalid UTF-8
        }
    };

    // current_base_dir should be a valid null-terminated C string.
    let current_base_dir_rust_str = CStr::from_ptr(current_base_dir);
    let current_base_dir_rust_str = match current_base_dir_rust_str.to_str() {
        Ok(s) => s,
        Err(e) => {
            if !err_msg.is_null() {
                let err_msg_c_str = CString::new(e.to_string()).unwrap();
                *err_msg = err_msg_c_str.into_raw();
            }
            return std::ptr::null(); // Invalid UTF-8
        }
    };

    // app_base_dir should be a valid null-terminated C string.
    let app_base_dir_rust_str = CStr::from_ptr(app_base_dir);
    let app_base_dir_rust_str = match app_base_dir_rust_str.to_str() {
        Ok(s) => s,
        Err(e) => {
            if !err_msg.is_null() {
                let err_msg_c_str = CString::new(e.to_string()).unwrap();
                *err_msg = err_msg_c_str.into_raw();
            }
            return std::ptr::null(); // Invalid UTF-8
        }
    };

    // Parse the JSON string into a ManifestApi
    let mut manifest_api: ManifestApi = match serde_json::from_str(manifest_api_json_str_rust_str) {
        Ok(m) => m,
        Err(e) => {
            if !err_msg.is_null() {
                let err_msg_c_str = CString::new(e.to_string()).unwrap();
                *err_msg = err_msg_c_str.into_raw();
            }
            return std::ptr::null(); // Parsing failed
        }
    };

    let runtime = Runtime::new().unwrap();
    let flattened_api = runtime
        .block_on(manifest_api.get_flattened_api(current_base_dir_rust_str, app_base_dir_rust_str));

    if flattened_api.is_err() {
        if !err_msg.is_null() {
            let err_msg_c_str = CString::new(flattened_api.err().unwrap().to_string()).unwrap();
            *err_msg = err_msg_c_str.into_raw();
        }
        return std::ptr::null(); // Parsing failed
    }

    // If the flattened API is None, return the original manifest API.
    if flattened_api.as_ref().unwrap().is_none() {
        // Clone the manifest_api_json_str_rust_str and return the C string.
        let manifest_api_json_str_c_str = CString::new(manifest_api_json_str_rust_str).unwrap();
        return manifest_api_json_str_c_str.into_raw();
    }

    // Serialize the flattened API back to JSON
    let flattened_api_json_str = match serde_json::to_string(&flattened_api.unwrap()) {
        Ok(json) => json,
        Err(e) => {
            if !err_msg.is_null() {
                let err_msg_c_str = CString::new(e.to_string()).unwrap();
                *err_msg = err_msg_c_str.into_raw();
            }
            return std::ptr::null(); // Serialization failed
        }
    };

    // Convert to C string
    match CString::new(flattened_api_json_str) {
        Ok(c_string) => c_string.into_raw(),
        Err(e) => {
            if !err_msg.is_null() {
                let err_msg_c_str = CString::new(e.to_string()).unwrap();
                *err_msg = err_msg_c_str.into_raw();
            }
            std::ptr::null() // Contains null bytes
        }
    }
}

/// Validates the graph json string.
///
/// # Parameters
/// - `graph_json_str`: A null-terminated C string containing the JSON
///   representation of a graph. Must not be NULL.
/// - `err_msg`: Pointer to a char* that will be set to an error message if the
///   function fails. Can be NULL if error details are not needed. If set, the
///   error message must be freed using `ten_rust_free_cstring()`.
///
/// # Returns
/// - On success: true
/// - On failure: false
///
/// # Safety
///
/// The caller must ensure that:
/// - `graph_json_str` is a valid null-terminated C string
/// - If err_msg is not NULL, the error message (if set) must be freed using
///   `ten_rust_free_cstring()`
/// - The input string contains valid UTF-8 encoded JSON
///
/// # Memory Management
///
/// The error message (if set) is allocated by Rust and must be freed by
/// calling `ten_rust_free_cstring()` when no longer needed.
#[no_mangle]
pub unsafe extern "C" fn ten_rust_validate_graph_json_string(
    graph_json_str: *const c_char,
    err_msg: *mut *mut c_char,
) -> bool {
    if graph_json_str.is_null() {
        if !err_msg.is_null() {
            let err_msg_c_str = CString::new("graph_json_str is null").unwrap();
            *err_msg = err_msg_c_str.into_raw();
        }
        return false;
    }

    let c_graph_json_str = CStr::from_ptr(graph_json_str);
    let rust_graph_json_str = match c_graph_json_str.to_str() {
        Ok(s) => s,
        Err(e) => {
            if !err_msg.is_null() {
                let err_msg_c_str = CString::new(e.to_string()).unwrap();
                *err_msg = err_msg_c_str.into_raw();
            }
            return false; // Invalid UTF-8
        }
    };

    let result = Graph::from_str_and_validate(rust_graph_json_str);
    if result.is_err() {
        if !err_msg.is_null() {
            let err_msg_c_str = CString::new(result.err().unwrap().to_string()).unwrap();
            *err_msg = err_msg_c_str.into_raw();
        }
        return false;
    }

    let result = result.unwrap().static_check_for_pre_flatten_graph();
    if result.is_err() {
        if !err_msg.is_null() {
            let err_msg_c_str = CString::new(result.err().unwrap().to_string()).unwrap();
            *err_msg = err_msg_c_str.into_raw();
        }
        return false;
    }

    true
}

/// Validates the graph json string and returns it as a JSON string.
///
/// # Parameters
/// - `json_str`: A null-terminated C string containing the JSON representation
///   of a graph. Must not be NULL.
/// - `current_base_dir`: A null-terminated C string containing the current base
///   directory. Can be NULL if the current base directory is not known.
/// - `err_msg`: Pointer to a char* that will be set to an error message if the
///   function fails. Can be NULL if error details are not needed. If set, the
///   error message must be freed using `ten_rust_free_cstring()`.
///
/// # Returns
/// - On success: A pointer to a newly allocated C string containing the
///   processed graph JSON
/// - On failure: NULL pointer
///
/// # Safety
///
/// The caller must ensure that:
/// - `json_str` is a valid null-terminated C string
/// - `current_base_dir` is a valid null-terminated C string, or NULL
/// - If err_msg is not NULL, the error message (if set) must be freed using
///   `ten_rust_free_cstring()`
/// - The input string contains valid UTF-8 encoded JSON
///
/// # Memory Management
///
/// Both the returned string (if not NULL) and error message (if set) are
/// allocated by Rust and must be freed by calling `ten_rust_free_cstring()`
/// when no longer needed.
#[no_mangle]
pub unsafe extern "C" fn ten_rust_graph_validate_complete_flatten(
    json_str: *const c_char,
    current_base_dir: *const c_char,
    src_loc_json_str: *const c_char,
    err_msg: *mut *mut c_char,
) -> *const c_char {
    if json_str.is_null() {
        if !err_msg.is_null() {
            let err_msg_c_str = CString::new("json_str is null").unwrap();
            *err_msg = err_msg_c_str.into_raw();
        }
        return std::ptr::null();
    }

    // Convert C string to Rust string
    let json_str_c_str = CStr::from_ptr(json_str);
    let json_str_rust_str = match json_str_c_str.to_str() {
        Ok(s) => s,
        Err(e) => {
            if !err_msg.is_null() {
                let err_msg_c_str = CString::new(e.to_string()).unwrap();
                *err_msg = err_msg_c_str.into_raw();
            }
            return std::ptr::null(); // Invalid UTF-8
        }
    };

    let current_base_dir_rust_str = if current_base_dir.is_null() {
        None
    } else {
        let current_base_dir_c_str = CStr::from_ptr(current_base_dir);
        let current_base_dir_rust_str = match current_base_dir_c_str.to_str() {
            Ok(s) => s,
            Err(e) => {
                if !err_msg.is_null() {
                    let err_msg_c_str = CString::new(e.to_string()).unwrap();
                    *err_msg = err_msg_c_str.into_raw();
                }
                return std::ptr::null(); // Invalid UTF-8
            }
        };
        Some(current_base_dir_rust_str)
    };

    let src_loc_json_str_rust_str = if src_loc_json_str.is_null() {
        None
    } else {
        let src_loc_json_str_c_str = CStr::from_ptr(src_loc_json_str);
        let src_loc_json_str_rust_str = match src_loc_json_str_c_str.to_str() {
            Ok(s) => s,
            Err(e) => {
                if !err_msg.is_null() {
                    let err_msg_c_str = CString::new(e.to_string()).unwrap();
                    *err_msg = err_msg_c_str.into_raw();
                }
                return std::ptr::null(); // Invalid UTF-8
            }
        };
        Some(src_loc_json_str_rust_str)
    };

    if let Err(e) = ten_validate_graph_json_string(json_str_rust_str) {
        tracing::warn!(
            "Graph JSON schema validation failed during start_graph handling, continuing: {e}"
        );
    }

    // Parse the JSON string into a Graph
    let graph = {
        let rt = Runtime::new().unwrap();
        let graph = match rt
            .block_on(Graph::from_str_with_base_dir(json_str_rust_str, current_base_dir_rust_str))
        {
            Ok(g) => g,
            Err(e) => {
                if !err_msg.is_null() {
                    let err_msg_c_str = CString::new(e.to_string()).unwrap();
                    *err_msg = err_msg_c_str.into_raw();
                }
                return std::ptr::null(); // Parsing failed
            }
        };

        // Flatten the graph
        let flattened_graph = match rt.block_on(graph.flatten_graph(current_base_dir_rust_str)) {
            Ok(g) => {
                if let Some(g) = g {
                    g
                } else {
                    graph
                }
            }
            Err(e) => {
                if !err_msg.is_null() {
                    let err_msg_c_str = CString::new(e.to_string()).unwrap();
                    *err_msg = err_msg_c_str.into_raw();
                }
                return std::ptr::null(); // Flattening failed
            }
        };

        // Inject graph_proxy from exposed messages
        match flattened_graph.inject_graph_proxy_from_exposed_messages(src_loc_json_str_rust_str) {
            Ok(g) => {
                if let Some(g) = g {
                    g
                } else {
                    flattened_graph
                }
            }
            Err(e) => {
                if !err_msg.is_null() {
                    let err_msg_c_str = CString::new(e.to_string()).unwrap();
                    *err_msg = err_msg_c_str.into_raw();
                }
                return std::ptr::null(); // Injecting graph_proxy failed
            }
        }
    };

    // Serialize the graph back to JSON
    let json_output = match serde_json::to_string(&graph) {
        Ok(json) => json,
        Err(e) => {
            if !err_msg.is_null() {
                let err_msg_c_str = CString::new(e.to_string()).unwrap();
                *err_msg = err_msg_c_str.into_raw();
            }
            return std::ptr::null(); // Serialization failed
        }
    };

    // Convert to C string
    match CString::new(json_output) {
        Ok(c_string) => c_string.into_raw(),
        Err(e) => {
            if !err_msg.is_null() {
                let err_msg_c_str = CString::new(e.to_string()).unwrap();
                *err_msg = err_msg_c_str.into_raw();
            }
            std::ptr::null() // Contains null bytes
        }
    }
}
