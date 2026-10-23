#!/bin/bash

# TEN Framework - TMAN Installation Script
# Purpose: Install the latest version of tman on Linux/macOS with auto-detection of OS and architecture

set -e

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored messages
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_debug() {
    echo -e "${BLUE}[DEBUG]${NC} $1"
}

# Check if tman is already installed
check_existing_tman() {
    if command -v tman &> /dev/null; then
        echo ""
        print_warn "tman is already installed on this system"

        # Get current version
        local current_version=$(tman --version 2>&1 || tman -v 2>&1 || echo "unknown")
        print_info "Current version: $current_version"
        print_info "Location: $(which tman)"
        echo ""

        # Ask user if they want to continue
        read -p "Do you want to reinstall/upgrade tman? [y/N]: " -n 1 -r
        echo ""

        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Installation cancelled by user"
            echo ""
            print_info "💡 Quick tips:"
            echo "  tman --version       # Check version"
            echo "  tman --help          # Show help"
            echo "  tman install         # Install project dependencies"
            echo ""
            exit 0
        fi

        echo ""
        print_info "Proceeding with installation..."
        echo ""
    fi
}

# Detect operating system
detect_os() {
    print_info "Detecting operating system..."

    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="mac"
    else
        print_error "Unsupported operating system: $OSTYPE"
        print_info "Supported systems: Linux, macOS"
        exit 1
    fi

    print_info "✓ Operating system: $OS"
}

# Detect CPU architecture
detect_arch() {
    print_info "Detecting CPU architecture..."

    local machine=$(uname -m)

    case "$machine" in
        x86_64|amd64)
            ARCH="x64"
            ;;
        aarch64|arm64)
            ARCH="arm64"
            ;;
        *)
            print_error "Unsupported architecture: $machine"
            print_info "Supported architectures: x86_64 (x64), aarch64/arm64"
            exit 1
            ;;
    esac

    print_info "✓ CPU architecture: $ARCH ($machine)"
}

# Detect system and architecture
detect_system() {
    detect_os
    detect_arch

    # Construct platform string for download
    PLATFORM="${OS}-release-${ARCH}"
    print_info "✓ Target platform: $PLATFORM"
}

# Get latest version from GitHub
get_latest_version() {
    # All output redirected to stderr to keep stdout clean
    print_info "Fetching latest version information..." >&2

    # Try with timeout and retry
    local max_attempts=3
    local attempt=1
    local latest_version=""

    while [ $attempt -le $max_attempts ] && [ -z "$latest_version" ]; do
        if [ $attempt -gt 1 ]; then
            print_info "Retry attempt $attempt of $max_attempts..." >&2
            sleep 2
        fi

        # Use curl with timeout settings
        latest_version=$(curl -s --connect-timeout 10 --max-time 30 \
            https://api.github.com/repos/TEN-framework/ten-framework/releases/latest \
            | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/')

        attempt=$((attempt + 1))
    done

    if [ -z "$latest_version" ]; then
        print_warn "Unable to fetch latest version automatically" >&2
        print_info "This may be due to:" >&2
        print_info "  - Network timeout (GitHub API is slow or unreachable)" >&2
        print_info "  - GitHub API rate limit exceeded" >&2
        print_info "Using default version: 0.11.74" >&2
        latest_version="0.11.74"
    else
        print_info "✓ Latest version found: $latest_version" >&2
    fi

    # Only output version number to stdout
    echo "$latest_version"
}

# Download tman
download_tman() {
    local version=$1
    local download_url="https://github.com/TEN-framework/ten-framework/releases/download/${version}/tman-${PLATFORM}.zip"
    TMAN_TMP_DIR="/tmp/tman_install_$$"

    print_info "Starting download of tman ${version}..."
    print_info "Download URL: $download_url"

    # Create temporary directory
    mkdir -p "$TMAN_TMP_DIR"
    cd "$TMAN_TMP_DIR"

    # Try to download
    if ! curl -L -f -# -o "tman.zip" "$download_url"; then
        print_error "Download failed"
        print_info "Possible reasons:"
        print_info "1. Network connection issues"
        print_info "2. Invalid version number"
        print_info "3. Binary not available for your platform ($PLATFORM)"
        print_info ""
        print_info "Please visit the following URL to check available versions:"
        print_info "https://github.com/TEN-framework/ten-framework/releases"
        print_info ""
        print_info "Available platform formats:"
        print_info "  - tman-linux-release-x64.zip"
        print_info "  - tman-linux-release-arm64.zip"
        print_info "  - tman-mac-release-x64.zip"
        print_info "  - tman-mac-release-arm64.zip"
        rm -rf "$TMAN_TMP_DIR"
        exit 1
    fi

    print_info "✓ Download completed"
}

# Extract and install tman
install_tman() {
    print_info "Extracting files..."
    cd "$TMAN_TMP_DIR"

    if ! unzip -q tman.zip; then
        print_error "Extraction failed"
        exit 1
    fi

    # Find tman executable (usually in ten_manager/bin/tman)
    if [ -f "./ten_manager/bin/tman" ]; then
        tman_bin="./ten_manager/bin/tman"
    else
        # If not in standard location, try to find it
        tman_bin=$(find . -name "tman" -type f | head -n 1)
    fi

    if [ -z "$tman_bin" ]; then
        print_error "tman executable not found"
        print_info "Contents of extracted directory:"
        ls -laR
        exit 1
    fi

    print_info "✓ Found tman: $tman_bin"

    # Add execute permission
    chmod +x "$tman_bin"

    # Determine if we need to use sudo
    # Check if running as root (compatible with both Linux and macOS)
    current_uid=$(id -u)
    if [ "$current_uid" -eq 0 ]; then
        # Running as root, no need for sudo
        USE_SUDO=""
        print_info "Running as root user"
    else
        # Not running as root, need sudo
        USE_SUDO="sudo"
        print_info "Running as non-root user, will use sudo"
    fi

    # Ensure target directory exists
    if [ ! -d "/usr/local/bin" ]; then
        print_info "Creating /usr/local/bin directory..."
        $USE_SUDO mkdir -p /usr/local/bin
    fi

    # Install to /usr/local/bin
    if [ -n "$USE_SUDO" ]; then
        print_info "Installing tman to /usr/local/bin (requires sudo)..."
    else
        print_info "Installing tman to /usr/local/bin..."
    fi

    if ! $USE_SUDO cp "$tman_bin" /usr/local/bin/tman; then
        print_error "Installation failed"
        exit 1
    fi

    print_info "✓ Installation completed"

    # Change to a safe directory before cleaning up temp files
    # to avoid "getcwd() failed: No such file or directory" error
    cd /tmp

    print_info "Cleaning up temporary files..."
    rm -rf "$TMAN_TMP_DIR"
}

# Verify installation
verify_installation() {
    print_info "Verifying installation..."

    if command -v tman &> /dev/null; then
        tman_version=$(tman --version 2>&1 || tman -v 2>&1 || echo "Unable to get version info")
        print_info "✓ tman installed successfully!"
        print_info "  Version: $tman_version"
        print_info "  Location: $(which tman)"

        # Check PATH
        if [[ ":$PATH:" == *":/usr/local/bin:"* ]]; then
            print_info "  PATH configured: /usr/local/bin is in PATH"
        else
            print_warn "  /usr/local/bin is not in PATH"
            if [[ "$OS" == "mac" ]]; then
                print_info "  Please add the following to ~/.zshrc or ~/.bash_profile:"
            else
                print_info "  Please add the following to ~/.bashrc or ~/.profile:"
            fi
            echo ""
            echo "    export PATH=\"/usr/local/bin:\$PATH\""
            echo ""
        fi
    else
        print_error "tman not properly installed to PATH"
        print_info "Try manual check: ls -l /usr/local/bin/tman"
        exit 1
    fi
}

# Display usage
usage() {
    cat << EOF
Usage: $0 [VERSION]

Install TEN Framework TMAN tool with automatic OS and architecture detection.

Arguments:
  VERSION    Optional. Specify a version to install (e.g., 0.11.74)
             If not provided, the latest version will be downloaded.

Examples:
  $0              # Install latest version
  $0 0.11.74      # Install specific version

Supported Platforms:
  - Linux x64 (x86_64)
  - Linux ARM64 (aarch64)
  - macOS x64 (Intel)
  - macOS ARM64 (Apple Silicon)

EOF
}

# Main function
main() {
    # Check for help flag
    if [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]]; then
        usage
        exit 0
    fi

    echo "================================================"
    echo "  TEN Framework - TMAN Installation Script"
    echo "================================================"
    echo ""

    # Check if tman is already installed
    check_existing_tman

    # Detect system and architecture
    detect_system
    echo ""

    # Get version (can be specified via parameter)
    if [ -n "$1" ]; then
        version="$1"
        print_info "Using specified version: $version"
    else
        version=$(get_latest_version)
    fi
    echo ""

    # Download
    download_tman "$version"
    echo ""

    # Install
    install_tman
    echo ""

    # Verify
    verify_installation

    echo ""
    echo "================================================"
    print_info "🎉 Installation completed successfully!"
    echo "================================================"
    echo ""
    print_info "📌 Common commands:"
    echo "  tman --version       # Check version"
    echo "  tman --help          # Show help"
    echo "  tman install         # Install project dependencies"
    echo "  tman create <name>   # Create new project"
    echo ""

    if [[ "$OS" == "mac" ]]; then
        print_info "💡 Mac-specific tips:"
        echo "  - If you encounter library loading issues with Python extensions:"
        echo "    export DYLD_LIBRARY_PATH=/usr/local/opt/python@3.10/Frameworks/Python.framework/Versions/3.10/lib:\$DYLD_LIBRARY_PATH"
        echo ""
    fi
}

# Execute main function
main "$@"
