//
// Copyright © 2025 Agora
// This file is part of TEN Framework, an open source project.
// Licensed under the Apache License, Version 2.0, with certain conditions.
// Refer to the "LICENSE" file in the root directory for more information.
//
pub mod installed_paths;
pub mod template;

use std::{
    collections::HashMap,
    fs,
    path::{Path, PathBuf},
    sync::Arc,
};

use anyhow::{anyhow, Context, Result};
use console::Emoji;
use installed_paths::save_installed_paths;
use semver::Version;
use tempfile::NamedTempFile;
use ten_rust::pkg_info::{
    find_to_be_replaced_local_pkgs, find_untracked_local_packages, get_pkg_info_from_path,
    manifest::{
        dependency::ManifestDependency,
        support::{is_manifest_supports_compatible_with, ManifestSupport},
    },
    pkg_basic_info::PkgBasicInfo,
    pkg_type::PkgType,
    pkg_type_and_name::PkgTypeAndName,
    PkgInfo,
};
use tracing::instrument;

use super::{home::config::TmanConfig, registry::get_package};
use crate::{
    cmd::cmd_install::{InstallCommand, LocalInstallMode},
    fs::copy_folder_recursively,
    home::config::is_verbose,
    manifest_lock::{parse_manifest_lock_in_folder, write_pkg_lockfile, ManifestLock},
    output::TmanOutput,
    package_file::unpackage::extract_and_process_tpkg_file,
    pkg_info::manifest::to_file::patch_manifest_json_file,
    solver::solver_result::filter_solver_results_by_type_and_name,
};

#[instrument(skip_all, name = "install_local_pkg", fields(pkg_type = %get_pkg_type(pkg_info), pkg_name = %get_pkg_name(pkg_info), dest = %dest_dir_path))]
fn install_local_dependency_pkg_info(
    command_data: &InstallCommand,
    pkg_info: &PkgInfo,
    dest_dir_path: &String,
    out: Arc<Box<dyn TmanOutput>>,
) -> Result<()> {
    assert!(pkg_info.local_dependency_path.is_some(), "Should not happen.",);

    let src_path = pkg_info.local_dependency_path.as_ref().unwrap();
    let src_base_dir = pkg_info.local_dependency_base_dir.as_deref().unwrap_or("");

    let src_dir_path = Path::new(&src_base_dir)
        .join(src_path)
        .canonicalize()
        .with_context(|| format!("Failed to canonicalize path: {src_base_dir} + {src_path}"))?;

    let src_dir_path_metadata =
        fs::metadata(&src_dir_path).expect("Failed to get metadata for src_path");
    assert!(src_dir_path_metadata.is_dir(), "Source path must be a directory.");

    if Path::new(dest_dir_path).exists() {
        out.normal_line(&format!(
            "Destination directory '{dest_dir_path}' already exists. Skipping copy/link."
        ));
    } else {
        // Create all parent folders for `dest_dir`.
        let dest_path = Path::new(dest_dir_path);
        if let Some(parent) = dest_path.parent() {
            fs::create_dir_all(parent).with_context(|| {
                format!("Failed to create parent directories for '{dest_dir_path}'")
            })?;
        }

        match command_data.local_install_mode {
            LocalInstallMode::Invalid => panic!("Should not happen."),
            LocalInstallMode::Copy => {
                copy_folder_recursively(
                    &src_dir_path.to_string_lossy().to_string(),
                    dest_dir_path,
                )?;
            }
            LocalInstallMode::Link => {
                #[cfg(unix)]
                {
                    std::os::unix::fs::symlink(src_dir_path, dest_dir_path)
                        .map_err(|e| anyhow::anyhow!("Failed to create symlink: {}", e))?;
                }

                #[cfg(windows)]
                {
                    std::os::windows::fs::symlink_dir(src_dir_path, &dest_dir_path).map_err(
                        |e| anyhow::anyhow!("Failed to create directory symlink: {}", e),
                    )?;
                }
            }
        }
    }

    Ok(())
}

#[instrument(skip_all, name = "install_non_local_pkg", fields(pkg_type = %get_pkg_type(pkg_info), pkg_name = %get_pkg_name(pkg_info), version = %get_pkg_version(pkg_info), dest = %dest_dir_path))]
async fn install_non_local_dependency_pkg_info(
    tman_config: Arc<tokio::sync::RwLock<TmanConfig>>,
    pkg_info: &PkgInfo,
    dest_dir_path: &String,
    out: Arc<Box<dyn TmanOutput>>,
) -> Result<()> {
    let mut temp_file = NamedTempFile::new()?;
    get_package(
        tman_config,
        &get_pkg_type(pkg_info),
        &get_pkg_name(pkg_info),
        &get_pkg_version(pkg_info),
        &pkg_info.url,
        &mut temp_file,
        out,
    )
    .await?;

    match fs::symlink_metadata(dest_dir_path) {
        Ok(metadata) if metadata.file_type().is_symlink() => fs::remove_dir_all(dest_dir_path),
        Ok(metadata) if metadata.is_dir() => remove_dir_all::remove_dir_all(dest_dir_path),
        Ok(_) => fs::remove_file(dest_dir_path),
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => Ok(()),
        Err(err) => Err(err),
    }
    .with_context(|| format!("Failed to remove existing package path: {dest_dir_path}"))?;

    let mut installed_paths = extract_and_process_tpkg_file(temp_file.path(), dest_dir_path, None)?;

    // After installation (after decompression), check whether the content
    // of property.json is correct based on the decompressed
    // content.
    ten_rust::pkg_info::property::check_property_json_of_pkg(dest_dir_path).map_err(|e| {
        anyhow::anyhow!(
            "Failed to check property.json for {}:{}, {}",
            get_pkg_type(pkg_info),
            get_pkg_name(pkg_info),
            e
        )
    })?;

    // base_dir is also an installed_path.
    installed_paths.paths.push(".".to_string());

    save_installed_paths(&installed_paths, Path::new(&dest_dir_path))?;

    Ok(())
}

#[instrument(skip_all, name = "install_pkg_info", fields(pkg_type = %get_pkg_type(pkg_info), pkg_name = %get_pkg_name(pkg_info), version = %get_pkg_version(pkg_info), is_local = pkg_info.is_local_dependency))]
pub async fn install_pkg_info(
    tman_config: Arc<tokio::sync::RwLock<TmanConfig>>,
    command_data: &InstallCommand,
    pkg_info: &PkgInfo,
    base_dir: &Path,
    out: Arc<Box<dyn TmanOutput>>,
) -> Result<()> {
    if pkg_info.is_installed {
        if is_verbose(tman_config.clone()).await {
            out.normal_line(&format!(
                "{}:{} has already been installed.",
                get_pkg_type(pkg_info),
                get_pkg_name(pkg_info)
            ));
        }
        return Ok(());
    }

    let target_path = PathBuf::from(&base_dir).join(get_pkg_name(pkg_info));

    let dest_dir_path = target_path.to_string_lossy().to_string();

    if pkg_info.is_local_dependency {
        install_local_dependency_pkg_info(command_data, pkg_info, &dest_dir_path, out)?;
    } else {
        install_non_local_dependency_pkg_info(tman_config, pkg_info, &dest_dir_path, out).await?;
    }

    Ok(())
}

async fn update_package_manifest(
    base_pkg_info: &mut PkgInfo,
    added_dependency: &PkgInfo,
    // If `Some(...)` is passed in, it indicates `local_path` mode.
    local_path_if_any: Option<String>,
) -> Result<()> {
    let mut is_present = false;
    let mut updated_dependencies = Vec::new();

    // Process the struct field dependencies first as a cache.
    if let Some(ref dependencies) = base_pkg_info.manifest.dependencies {
        for dep in dependencies.iter() {
            match dep {
                ManifestDependency::RegistryDependency {
                    pkg_type,
                    name,
                    ..
                } => {
                    let manifest_dependency_type_and_name = PkgTypeAndName {
                        pkg_type: *pkg_type,
                        name: name.clone(),
                    };

                    if manifest_dependency_type_and_name == PkgTypeAndName::from(added_dependency) {
                        if !added_dependency.is_local_dependency {
                            is_present = true;
                            updated_dependencies.push(dep.clone());
                        }
                    } else {
                        updated_dependencies.push(dep.clone());
                    }
                }
                ManifestDependency::LocalDependency {
                    path, ..
                } => {
                    let manifest_dependency_pkg_info = match get_pkg_info_from_path(
                        Path::new(&path),
                        false,
                        false,
                        &mut None,
                        None,
                    )
                    .await
                    {
                        Ok(info) => info,
                        Err(_) => {
                            panic!("Failed to get package info from path: {path}");
                        }
                    };

                    if manifest_dependency_pkg_info.manifest.type_and_name.pkg_type
                        == get_pkg_type(added_dependency)
                        && manifest_dependency_pkg_info.manifest.type_and_name.name
                            == get_pkg_name(added_dependency)
                    {
                        if added_dependency.is_local_dependency {
                            assert!(
                                added_dependency.local_dependency_path.is_some(),
                                "Should not happen."
                            );

                            if path == added_dependency.local_dependency_path.as_ref().unwrap() {
                                is_present = true;
                                updated_dependencies.push(dep.clone());
                            }
                        }
                    } else {
                        updated_dependencies.push(dep.clone());
                    }
                }
            }
        }
    }

    // If the added dependency does not exist in the `manifest.json`, add
    // it.
    if !is_present {
        // If `local_path_if_any` has a value, create a local dependency.
        if let Some(local_path) = &local_path_if_any {
            let local_dep = ManifestDependency::LocalDependency {
                path: local_path.clone(),
                base_dir: Some("".to_string()),
            };
            updated_dependencies.push(local_dep.clone());
        } else {
            let registry_dep = ManifestDependency::from(added_dependency);
            updated_dependencies.push(registry_dep.clone());
        }
    };

    base_pkg_info.manifest.dependencies = Some(updated_dependencies);

    patch_manifest_json_file(&base_pkg_info.url, &base_pkg_info.manifest).await?;

    Ok(())
}

#[instrument(skip_all, name = "write_manifest_lock", fields(pkg_count = pkgs.len()))]
pub async fn write_pkgs_into_manifest_lock_file(
    pkgs: &Vec<&PkgInfo>,
    app_dir: &Path,
    out: Arc<Box<dyn TmanOutput>>,
) -> Result<()> {
    // Check if manifest-lock.json exists.
    let old_manifest_lock = parse_manifest_lock_in_folder(app_dir);
    if old_manifest_lock.is_err() {
        out.normal_line(&format!("{}  Creating manifest-lock.json...", Emoji("🔒", "")));
    }

    let new_manifest_lock = ManifestLock::from_locked_pkgs_info(pkgs).await?;

    let changed = write_pkg_lockfile(&new_manifest_lock, app_dir)?;

    // If the lock file is changed, print all changes.
    if changed && old_manifest_lock.is_ok() {
        out.normal_line(&format!("{}  Breaking manifest-lock.json...", Emoji("🔒", "")));

        new_manifest_lock.print_changes(&old_manifest_lock.ok().unwrap(), out);
    }

    Ok(())
}

pub async fn write_installing_pkg_into_manifest_file(
    pkg_info: &mut PkgInfo,
    solver_results: &[PkgInfo],
    pkg_type: &PkgType,
    pkg_name: &String,
    // If `Some(...)` is passed in, it indicates `local_path` mode.
    local_path_if_any: Option<String>,
) -> Result<()> {
    let suitable_pkgs = filter_solver_results_by_type_and_name(
        solver_results,
        Some(pkg_type),
        Some(pkg_name),
        true,
    )?;

    if suitable_pkgs.is_empty() {
        return Err(anyhow!("Failed to find any of {}:{}.", pkg_type, pkg_name,));
    }

    if suitable_pkgs.len() > 1 {
        return Err(anyhow!(
            "Found the possibility of multiple {}:{} being incorrect.",
            pkg_type,
            pkg_name
        ));
    }

    update_package_manifest(pkg_info, suitable_pkgs[0], local_path_if_any).await?;

    Ok(())
}

/// Filter out the packages in `all_pkgs` that meet the current environment's
/// requirements and treat them as candidates.
pub async fn filter_compatible_pkgs_to_candidates(
    tman_config: Arc<tokio::sync::RwLock<TmanConfig>>,
    all_pkgs: &Vec<PkgInfo>,
    all_candidates: &mut HashMap<PkgTypeAndName, HashMap<PkgBasicInfo, PkgInfo>>,
    support: &ManifestSupport,
    out: Arc<Box<dyn TmanOutput>>,
) -> Result<()> {
    for existed_pkg in all_pkgs.to_owned().iter_mut() {
        if is_verbose(tman_config.clone()).await {
            out.normal_line(&format!("Check support score for {existed_pkg:?}"));
        }

        let compatible_score =
            is_manifest_supports_compatible_with(&get_pkg_supports(existed_pkg), support);

        if compatible_score >= 0 {
            existed_pkg.compatible_score = compatible_score;

            if is_verbose(tman_config.clone()).await {
                out.normal_line(&format!(
                    "The existed {} package {} is compatible with the current system.",
                    get_pkg_type(existed_pkg),
                    get_pkg_name(existed_pkg)
                ));
            }

            all_candidates
                .entry((&*existed_pkg).into())
                .or_default()
                .insert((&*existed_pkg).into(), existed_pkg.clone());
        } else {
            // The existed package is not compatible with the current system, so
            // it should not be considered as a candidate.
            if is_verbose(tman_config.clone()).await {
                out.normal_line(&format!(
                    "The existed {} package {} is not compatible with the current system.",
                    get_pkg_type(existed_pkg),
                    get_pkg_name(existed_pkg)
                ));
            }
        }
    }

    Ok(())
}

fn get_supports_str(pkg: &PkgInfo) -> String {
    let support_items: Vec<String> = get_pkg_supports(pkg)
        .iter()
        .filter_map(|s| match (s.os.as_ref(), s.arch.as_ref()) {
            (Some(os), Some(arch)) => Some(format!("{os:?}, {arch:?}").to_lowercase()),
            (Some(os), None) => Some(format!("{os:?}").to_lowercase()),
            (None, Some(arch)) => Some(format!("{arch:?}").to_lowercase()),
            (None, None) => None,
        })
        .collect();

    if !support_items.is_empty() {
        format!(" ({})", support_items.join(", "))
    } else {
        String::new()
    }
}

#[instrument(skip_all, name = "compare_with_installed", fields(
    solver_count = solver_results.len(),
    installed_count = all_installed_pkgs.len(),
    has_conflict = tracing::field::Empty
))]
pub fn compare_solver_results_with_installed_pkgs(
    solver_results: &[&PkgInfo],
    all_installed_pkgs: &[PkgInfo],
    out: Arc<Box<dyn TmanOutput>>,
) -> bool {
    let local_pkgs = all_installed_pkgs.iter().collect::<Vec<&PkgInfo>>();

    let untracked_local_pkgs: Vec<&PkgInfo> =
        find_untracked_local_packages(solver_results, &local_pkgs);

    if !untracked_local_pkgs.is_empty() {
        out.normal_line(&format!(
            "{}  The following local packages do not appear in the dependency tree:",
            Emoji("💡", "")
        ));
        for pkg in untracked_local_pkgs {
            out.normal_line(&format!(
                " {}:{}@{}",
                get_pkg_type(pkg),
                get_pkg_name(pkg),
                get_pkg_version(pkg)
            ));
        }
    }

    let to_be_replaced_local_pkgs: Vec<(&PkgInfo, &PkgInfo)> =
        find_to_be_replaced_local_pkgs(solver_results, &local_pkgs);

    let mut conflict = false;

    if !to_be_replaced_local_pkgs.is_empty() {
        conflict = true;

        out.normal_line(&format!("{}  The following packages will be replaced:", Emoji("🔄", "")));
        for (new_pkg, old_pkg) in to_be_replaced_local_pkgs {
            let old_supports_str = get_supports_str(old_pkg);
            let new_supports_str = get_supports_str(new_pkg);

            if old_supports_str != new_supports_str {
                out.normal_line(&format!(
                    " {}:{}@{}{} -> {}:{}@{}{}",
                    get_pkg_type(old_pkg),
                    get_pkg_name(old_pkg),
                    get_pkg_version(old_pkg),
                    old_supports_str,
                    get_pkg_type(new_pkg),
                    get_pkg_name(new_pkg),
                    get_pkg_version(new_pkg),
                    new_supports_str
                ));
            } else {
                out.normal_line(&format!(
                    " {}:{}@{} -> {}:{}@{}",
                    get_pkg_type(old_pkg),
                    get_pkg_name(old_pkg),
                    get_pkg_version(old_pkg),
                    get_pkg_type(new_pkg),
                    get_pkg_name(new_pkg),
                    get_pkg_version(new_pkg)
                ));
            }
        }
    }

    tracing::Span::current().record("has_conflict", conflict);
    conflict
}

// Helper function for accessing type and name and version
fn get_pkg_type(pkg: &PkgInfo) -> PkgType {
    pkg.manifest.type_and_name.pkg_type
}

fn get_pkg_name(pkg: &PkgInfo) -> String {
    pkg.manifest.type_and_name.name.clone()
}

fn get_pkg_version(pkg: &PkgInfo) -> Version {
    pkg.manifest.version.clone()
}

fn get_pkg_supports(pkg: &PkgInfo) -> Vec<ManifestSupport> {
    pkg.manifest.supports.clone().unwrap_or_default()
}
