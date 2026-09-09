//
// Copyright © 2025 Agora
// This file is part of TEN Framework, an open source project.
// Licensed under the Apache License, Version 2.0, with certain conditions.
// Refer to the "LICENSE" file in the root directory for more information.
//
#[cfg(test)]
mod tests {
    use std::{collections::HashMap, fs, sync::Arc};

    use actix_web::{test, web, App};
    use serde::{Deserialize, Serialize};
    use tempfile::tempdir;
    use ten_manager::{
        designer::{
            file_content::{get_file_content_endpoint, save_file_content_endpoint},
            response::{ApiResponse, Status},
            storage::in_memory::TmanStorageInMemory,
            DesignerState,
        },
        home::config::TmanConfig,
        output::cli::TmanOutputCli,
    };
    use ten_rust::base_dir_pkg_info::PkgsInfoInApp;

    #[derive(Serialize, Deserialize)]
    struct GetFileContentRequestPayload {
        file_path: String,
    }

    #[derive(Serialize, Deserialize)]
    struct SaveFileRequestPayload {
        file_path: String,
        content: String,
    }

    #[derive(Serialize, Deserialize)]
    struct GetFileContentResponseData {
        content: String,
    }

    // Builds a `DesignerState` whose `pkgs_cache` is seeded with the given
    // app base directories, mirroring the roots that would be present once
    // the designer has loaded one or more apps.
    fn build_state(allowed_roots: Vec<String>) -> web::Data<Arc<DesignerState>> {
        let mut pkgs_cache = HashMap::new();
        for root in allowed_roots {
            pkgs_cache.insert(root, PkgsInfoInApp::default());
        }

        web::Data::new(Arc::new(DesignerState {
            tman_config: Arc::new(tokio::sync::RwLock::new(TmanConfig::default())),
            storage_in_memory: Arc::new(tokio::sync::RwLock::new(TmanStorageInMemory::default())),
            out: Arc::new(Box::new(TmanOutputCli)),
            pkgs_cache: tokio::sync::RwLock::new(pkgs_cache),
            graphs_cache: tokio::sync::RwLock::new(HashMap::new()),
            persistent_storage_schema: Arc::new(tokio::sync::RwLock::new(None)),
        }))
    }

    #[actix_web::test]
    async fn test_get_file_content_within_root_succeeds() {
        let root = tempdir().unwrap();
        let file_path = root.path().join("inside.txt");
        fs::write(&file_path, "hello from inside the project").unwrap();

        let state = build_state(vec![root.path().to_string_lossy().to_string()]);

        let app = test::init_service(App::new().app_data(state.clone()).route(
            "/api/designer/v1/file-content",
            web::post().to(get_file_content_endpoint),
        ))
        .await;

        let req = test::TestRequest::post()
            .uri("/api/designer/v1/file-content")
            .set_json(GetFileContentRequestPayload {
                file_path: file_path.to_string_lossy().to_string(),
            })
            .to_request();

        let resp = test::call_service(&app, req).await;
        assert!(resp.status().is_success());

        let body = test::read_body(resp).await;
        let response: ApiResponse<GetFileContentResponseData> =
            serde_json::from_slice(&body).unwrap();

        assert_eq!(response.status, Status::Ok);
        assert_eq!(response.data.content, "hello from inside the project");
    }

    #[actix_web::test]
    async fn test_get_file_content_outside_root_is_rejected() {
        let root = tempdir().unwrap();
        let outside = tempdir().unwrap();
        let secret_path = outside.path().join("secret.txt");
        fs::write(&secret_path, "SECRET").unwrap();

        let state = build_state(vec![root.path().to_string_lossy().to_string()]);

        let app = test::init_service(App::new().app_data(state.clone()).route(
            "/api/designer/v1/file-content",
            web::post().to(get_file_content_endpoint),
        ))
        .await;

        let req = test::TestRequest::post()
            .uri("/api/designer/v1/file-content")
            .set_json(GetFileContentRequestPayload {
                file_path: secret_path.to_string_lossy().to_string(),
            })
            .to_request();

        let resp = test::call_service(&app, req).await;
        assert_eq!(resp.status(), actix_web::http::StatusCode::FORBIDDEN);
    }

    #[actix_web::test]
    async fn test_get_file_content_path_traversal_is_rejected() {
        let root = tempdir().unwrap();
        let outside = tempdir().unwrap();
        let secret_path = outside.path().join("secret.txt");
        fs::write(&secret_path, "SECRET").unwrap();

        let state = build_state(vec![root.path().to_string_lossy().to_string()]);

        let app = test::init_service(App::new().app_data(state.clone()).route(
            "/api/designer/v1/file-content",
            web::post().to(get_file_content_endpoint),
        ))
        .await;

        // Escape `root` via `..` into the sibling `outside` directory, the
        // same shape of attack as the `/etc/passwd` read in the report.
        let traversal_path =
            root.path().join("..").join(outside.path().file_name().unwrap()).join("secret.txt");

        let req = test::TestRequest::post()
            .uri("/api/designer/v1/file-content")
            .set_json(GetFileContentRequestPayload {
                file_path: traversal_path.to_string_lossy().to_string(),
            })
            .to_request();

        let resp = test::call_service(&app, req).await;
        assert_eq!(resp.status(), actix_web::http::StatusCode::FORBIDDEN);
    }

    #[actix_web::test]
    async fn test_get_file_content_missing_file_in_root_is_bad_request() {
        let root = tempdir().unwrap();

        // A path inside a loaded root, but nothing exists there (e.g. a
        // typo'd path, or a file removed between listing and opening).
        // This must be a 400, not a 403: it isn't a confinement violation.
        let file_path = root.path().join("does-not-exist.txt");

        let state = build_state(vec![root.path().to_string_lossy().to_string()]);

        let app = test::init_service(App::new().app_data(state.clone()).route(
            "/api/designer/v1/file-content",
            web::post().to(get_file_content_endpoint),
        ))
        .await;

        let req = test::TestRequest::post()
            .uri("/api/designer/v1/file-content")
            .set_json(GetFileContentRequestPayload {
                file_path: file_path.to_string_lossy().to_string(),
            })
            .to_request();

        let resp = test::call_service(&app, req).await;
        assert_eq!(resp.status(), actix_web::http::StatusCode::BAD_REQUEST);
    }

    #[actix_web::test]
    async fn test_get_file_content_with_no_loaded_root_is_rejected() {
        let root = tempdir().unwrap();
        let file_path = root.path().join("inside.txt");
        fs::write(&file_path, "hello").unwrap();

        // No app/project root has been loaded into `pkgs_cache`.
        let state = build_state(vec![]);

        let app = test::init_service(App::new().app_data(state.clone()).route(
            "/api/designer/v1/file-content",
            web::post().to(get_file_content_endpoint),
        ))
        .await;

        let req = test::TestRequest::post()
            .uri("/api/designer/v1/file-content")
            .set_json(GetFileContentRequestPayload {
                file_path: file_path.to_string_lossy().to_string(),
            })
            .to_request();

        let resp = test::call_service(&app, req).await;
        assert_eq!(resp.status(), actix_web::http::StatusCode::FORBIDDEN);
    }

    #[actix_web::test]
    async fn test_save_file_content_within_root_succeeds() {
        let root = tempdir().unwrap();
        let file_path = root.path().join("new_file.txt");

        let state = build_state(vec![root.path().to_string_lossy().to_string()]);

        let app = test::init_service(App::new().app_data(state.clone()).route(
            "/api/designer/v1/file-content",
            web::put().to(save_file_content_endpoint),
        ))
        .await;

        let req = test::TestRequest::put()
            .uri("/api/designer/v1/file-content")
            .set_json(SaveFileRequestPayload {
                file_path: file_path.to_string_lossy().to_string(),
                content: "written by the designer".to_string(),
            })
            .to_request();

        let resp = test::call_service(&app, req).await;
        assert!(resp.status().is_success());

        let saved = fs::read_to_string(&file_path).unwrap();
        assert_eq!(saved, "written by the designer");
    }

    #[actix_web::test]
    async fn test_save_file_content_outside_root_is_rejected() {
        let root = tempdir().unwrap();
        let outside = tempdir().unwrap();
        let target_path = outside.path().join("pwned.txt");

        let state = build_state(vec![root.path().to_string_lossy().to_string()]);

        let app = test::init_service(App::new().app_data(state.clone()).route(
            "/api/designer/v1/file-content",
            web::put().to(save_file_content_endpoint),
        ))
        .await;

        let req = test::TestRequest::put()
            .uri("/api/designer/v1/file-content")
            .set_json(SaveFileRequestPayload {
                file_path: target_path.to_string_lossy().to_string(),
                content: "PWNED".to_string(),
            })
            .to_request();

        let resp = test::call_service(&app, req).await;
        assert_eq!(resp.status(), actix_web::http::StatusCode::FORBIDDEN);
        assert!(fs::metadata(&target_path).is_err());
    }

    #[actix_web::test]
    async fn test_save_file_content_path_traversal_is_rejected() {
        let root = tempdir().unwrap();
        let outside = tempdir().unwrap();
        let target_path = outside.path().join("pwned.txt");

        let state = build_state(vec![root.path().to_string_lossy().to_string()]);

        let app = test::init_service(App::new().app_data(state.clone()).route(
            "/api/designer/v1/file-content",
            web::put().to(save_file_content_endpoint),
        ))
        .await;

        // Escape `root` via `..` into the sibling `outside` directory.
        let traversal_path =
            root.path().join("..").join(outside.path().file_name().unwrap()).join("pwned.txt");

        let req = test::TestRequest::put()
            .uri("/api/designer/v1/file-content")
            .set_json(SaveFileRequestPayload {
                file_path: traversal_path.to_string_lossy().to_string(),
                content: "PWNED".to_string(),
            })
            .to_request();

        let resp = test::call_service(&app, req).await;
        assert_eq!(resp.status(), actix_web::http::StatusCode::FORBIDDEN);
        assert!(fs::metadata(&target_path).is_err());
    }

    #[actix_web::test]
    async fn test_save_file_content_outside_root_with_nonexistent_parent_chain_is_rejected() {
        let root = tempdir().unwrap();
        let outside = tempdir().unwrap();

        // Unlike `test_save_file_content_outside_root_is_rejected`, none of
        // `outside`'s `a/b/c` subdirectories exist yet, so a validation
        // that only runs after `fs::create_dir_all` would let that call
        // create them outside of every loaded root before the write
        // itself is rejected.
        let target_path = outside.path().join("a").join("b").join("c").join("pwned.txt");

        let state = build_state(vec![root.path().to_string_lossy().to_string()]);

        let app = test::init_service(App::new().app_data(state.clone()).route(
            "/api/designer/v1/file-content",
            web::put().to(save_file_content_endpoint),
        ))
        .await;

        let req = test::TestRequest::put()
            .uri("/api/designer/v1/file-content")
            .set_json(SaveFileRequestPayload {
                file_path: target_path.to_string_lossy().to_string(),
                content: "PWNED".to_string(),
            })
            .to_request();

        let resp = test::call_service(&app, req).await;
        assert_eq!(resp.status(), actix_web::http::StatusCode::FORBIDDEN);
        assert!(fs::metadata(&target_path).is_err());
        assert!(fs::metadata(outside.path().join("a")).is_err());
    }
}
