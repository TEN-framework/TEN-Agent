//
// Copyright © 2025 Agora
// This file is part of TEN Framework, an open source project.
// Licensed under the Apache License, Version 2.0, with certain conditions.
// Refer to the "LICENSE" file in the root directory for more information.
//
use std::{
    ffi::OsString,
    fs,
    path::{Path, PathBuf},
    sync::Arc,
};

use actix_web::{web, HttpResponse, Responder};
use serde::{Deserialize, Serialize};

use super::{
    response::{ApiResponse, Status},
    DesignerState,
};

/// Checks that the already-canonicalized `candidate` is contained within
/// one of the canonicalized `allowed_roots`.
fn is_within_allowed_roots(candidate: &Path, allowed_roots: &[String]) -> bool {
    allowed_roots
        .iter()
        .filter_map(|root| fs::canonicalize(root).ok())
        .any(|canonical_root| candidate.starts_with(&canonical_root))
}

/// Why [`ensure_within_allowed_roots`] rejected a path.
enum PathRejection {
    /// `fs::canonicalize` failed outright, most commonly because nothing
    /// exists at `path` (a typo'd path, or a file removed after being
    /// listed). Not a confinement violation.
    Unresolvable(String),
    /// The path resolves, but outside of every loaded project root.
    OutsideAllowedRoots(String),
}

/// Canonicalizes `path` and checks that the result is contained within one
/// of the canonicalized `allowed_roots`. This confines the file-content API
/// to the directories of apps that are actually loaded, so a client cannot
/// escape via an absolute path or a `..` traversal.
fn ensure_within_allowed_roots(
    path: &Path,
    allowed_roots: &[String],
) -> Result<PathBuf, PathRejection> {
    if allowed_roots.is_empty() {
        return Err(PathRejection::OutsideAllowedRoots(
            "No project root is currently loaded, so no file path can be validated.".to_string(),
        ));
    }

    let canonical_path = fs::canonicalize(path).map_err(|e| {
        PathRejection::Unresolvable(format!("Failed to resolve path {}: {}", path.display(), e))
    })?;

    if is_within_allowed_roots(&canonical_path, allowed_roots) {
        Ok(canonical_path)
    } else {
        Err(PathRejection::OutsideAllowedRoots(format!(
            "Path {} is outside of any loaded project root.",
            canonical_path.display()
        )))
    }
}

/// Resolves `path` (which may not exist yet, e.g. the not-yet-created
/// parent directory of a new file) to what its canonical form will be, and
/// checks that it is contained within one of `allowed_roots`, without
/// creating anything on disk. Walks up to the nearest existing ancestor,
/// canonicalizes that (so any symlinks already on disk are resolved), then
/// re-applies the remaining, not-yet-created path components on top of it.
///
/// This must run before `fs::create_dir_all`, not after: that call
/// re-resolves any `..` left in its argument against the directories it
/// creates along the way, so a crafted path (e.g. `a/b/../../../etc`, where
/// only `a` exists and is an allowed root) can make it create directories
/// outside of every loaded root even though the final target is correctly
/// rejected afterwards.
fn resolve_prospective_path(path: &Path, allowed_roots: &[String]) -> Result<PathBuf, String> {
    if allowed_roots.is_empty() {
        return Err("No project root is currently loaded, so no file path can be validated."
            .to_string());
    }

    let mut existing_ancestor = path;
    let mut pending_components: Vec<OsString> = Vec::new();
    while !existing_ancestor.exists() {
        match existing_ancestor.file_name() {
            Some(name) => pending_components.push(name.to_os_string()),
            // A `..`/`.` component (or an empty path) with no existing
            // ancestor left to resolve it against; `fs::canonicalize` below
            // will fail on it, which is the correct outcome.
            None => break,
        }
        existing_ancestor = existing_ancestor.parent().unwrap_or_else(|| Path::new(""));
    }

    let canonical_ancestor = fs::canonicalize(existing_ancestor)
        .map_err(|e| format!("Failed to resolve path {}: {}", path.display(), e))?;

    let mut prospective_path = canonical_ancestor;
    for name in pending_components.into_iter().rev() {
        prospective_path.push(name);
    }

    if is_within_allowed_roots(&prospective_path, allowed_roots) {
        Ok(prospective_path)
    } else {
        Err(format!("Path {} is outside of any loaded project root.", prospective_path.display()))
    }
}

#[derive(Deserialize)]
pub struct GetFileContentRequestPayload {
    pub file_path: String,
}

#[derive(Serialize, Deserialize, Debug)]
struct GetFileContentResponseData {
    content: String,
}

pub async fn get_file_content_endpoint(
    request_payload: web::Json<GetFileContentRequestPayload>,
    state: web::Data<Arc<DesignerState>>,
) -> Result<impl Responder, actix_web::Error> {
    let file_path = request_payload.file_path.clone();

    let allowed_roots: Vec<String> = state.pkgs_cache.read().await.keys().cloned().collect();

    let validated_path = match ensure_within_allowed_roots(Path::new(&file_path), &allowed_roots) {
        Ok(path) => path,
        Err(PathRejection::Unresolvable(err)) => {
            // Not a confinement violation (e.g. a typo'd path, or a file
            // deleted between listing and opening): preserve the prior
            // 400 Bad Request behavior instead of looking like a security
            // rejection.
            state.out.error_line(&format!("Error reading file at path {file_path}: {err}"));

            let response = ApiResponse {
                status: Status::Fail,
                data: (),
                meta: None,
            };

            return Ok(HttpResponse::BadRequest().json(response));
        }
        Err(PathRejection::OutsideAllowedRoots(err)) => {
            state.out.error_line(&format!("Rejected file read at path {file_path}: {err}"));

            let response = ApiResponse {
                status: Status::Fail,
                data: (),
                meta: None,
            };

            return Ok(HttpResponse::Forbidden().json(response));
        }
    };

    match fs::read_to_string(&validated_path) {
        Ok(content) => {
            let response = ApiResponse {
                status: Status::Ok,
                data: GetFileContentResponseData {
                    content,
                },
                meta: None,
            };
            Ok(HttpResponse::Ok().json(response))
        }
        Err(err) => {
            state.out.error_line(&format!("Error reading file at path {file_path}: {err}"));

            let response = ApiResponse {
                status: Status::Fail,
                data: (),
                meta: None,
            };

            Ok(HttpResponse::BadRequest().json(response))
        }
    }
}

#[derive(Serialize, Deserialize, Debug)]
pub struct SaveFileRequestPayload {
    file_path: String,
    content: String,
}

pub async fn save_file_content_endpoint(
    request_payload: web::Json<SaveFileRequestPayload>,
    state: web::Data<Arc<DesignerState>>,
) -> Result<impl Responder, actix_web::Error> {
    let file_path_str = request_payload.file_path.clone();
    let content = &request_payload.content; // Access the content field.

    let file_path = Path::new(&file_path_str);

    // The target file itself may not exist yet (e.g. a new file being
    // saved for the first time), and its parent directories may not exist
    // either. Resolve and confine the prospective parent to a loaded
    // project root BEFORE creating any directories: `fs::create_dir_all`
    // must never run on an unvalidated, attacker-supplied path (see
    // `resolve_prospective_path`).
    let allowed_roots: Vec<String> = state.pkgs_cache.read().await.keys().cloned().collect();
    let parent = file_path.parent().unwrap_or_else(|| Path::new("."));

    let canonical_parent = match resolve_prospective_path(parent, &allowed_roots) {
        Ok(path) => path,
        Err(err) => {
            state.out.error_line(&format!("Rejected file write at path {file_path_str}: {err}"));

            let response = ApiResponse {
                status: Status::Fail,
                data: (),
                meta: None,
            };

            return Ok(HttpResponse::Forbidden().json(response));
        }
    };

    if let Err(e) = fs::create_dir_all(&canonical_parent) {
        state.out.error_line(&format!(
            "Error creating directories for {}: {}",
            canonical_parent.display(),
            e
        ));

        let response = ApiResponse {
            status: Status::Fail,
            data: (),
            meta: None,
        };

        return Ok(HttpResponse::BadRequest().json(response));
    }

    let validated_path = match file_path.file_name() {
        Some(file_name) => canonical_parent.join(file_name),
        None => {
            state.out.error_line(&format!("Invalid file path: {file_path_str}"));

            let response = ApiResponse {
                status: Status::Fail,
                data: (),
                meta: None,
            };

            return Ok(HttpResponse::BadRequest().json(response));
        }
    };

    match fs::write(&validated_path, content) {
        Ok(_) => {
            let response = ApiResponse {
                status: Status::Ok,
                data: (),
                meta: None,
            };
            Ok(HttpResponse::Ok().json(response))
        }
        Err(err) => {
            state.out.error_line(&format!(
                "Error writing file at path {}: {}",
                validated_path.display(),
                err
            ));

            let response = ApiResponse {
                status: Status::Fail,
                data: (),
                meta: None,
            };

            Ok(HttpResponse::BadRequest().json(response))
        }
    }
}
