#!/usr/bin/env sh

set -e

# Define the installation directory
INSTALL_DIR="$HOME/.ten-cli"

# Function to check and fix permissions
check_and_fix_permissions() {
    if [ ! -w "$INSTALL_DIR" ]; then
        echo "The installation directory $INSTALL_DIR is not writable."
        echo "Attempting to fix permissions using sudo..."
        sudo chown -R $(id -un) "$INSTALL_DIR"
        if [ $? -ne 0 ]; then
            echo "Failed to fix permissions. Please run the following command manually:"
            echo "sudo chown -R $(id -un) $INSTALL_DIR"
            exit 1
        fi
        echo "Permissions fixed."
    fi
}

# Create the installation directory
if [ ! -d "$INSTALL_DIR" ]; then
    mkdir -p "$INSTALL_DIR" || {
        echo "Failed to create $INSTALL_DIR. Please check your permissions."
        exit 1
    }
fi

# Check and fix permissions
check_and_fix_permissions

# Copy the main script
cp ten "$INSTALL_DIR/" || {
    echo "Failed to copy 'ten' to $INSTALL_DIR. Please check that the 'ten' file exists and you have the necessary permissions."
    exit 1
}

# Update the shebang line in the ten script
sed -i.bak "1s|.*|#!/usr/bin/env python3|" "$INSTALL_DIR/ten"

# Make the main script executable
chmod +x "$INSTALL_DIR/ten" || {
    echo "Failed to make $INSTALL_DIR/ten executable. Please check your permissions."
    exit 1
}

# Create symlinks for each language
ln -sf "$INSTALL_DIR/ten" "$INSTALL_DIR/ten-python"
ln -sf "$INSTALL_DIR/ten" "$INSTALL_DIR/ten-go"
ln -sf "$INSTALL_DIR/ten" "$INSTALL_DIR/ten-cpp"

# Determine the appropriate shell configuration file
detect_shell() {
    case "$(basename "$SHELL")" in
        zsh)
            echo "$HOME/.zshrc"
            ;;
        bash)
            echo "$HOME/.bashrc"
            ;;
        ksh)
            echo "$HOME/.kshrc"
            ;;
        fish)
            echo "$HOME/.config/fish/config.fish"
            ;;
        *)
            # Fall back to .profile if no match is found
            if [ -f "$HOME/.profile" ]; then
                echo "$HOME/.profile"
            else
                echo ""
            fi
            ;;
    esac
}

SHELL_CONFIG=$(detect_shell)

if [ -z "$SHELL_CONFIG" ]; then
    echo "Unable to determine shell configuration file. Please add the following line to your shell configuration file manually:"
    echo "export PATH=\"$INSTALL_DIR:\$PATH\""
    exit 1
fi

# Function to update shell configuration
update_shell_config() {
    local config_file="$1"
    local content="$2"
    
    if [ ! -f "$config_file" ]; then
        echo "$content" | sudo tee -a "$config_file" > /dev/null
        echo "Created $config_file with new content"
    elif ! grep -q "$content" "$config_file"; then
        echo "$content" | sudo tee -a "$config_file" > /dev/null
        echo "Updated $config_file with new content"
    else
        echo "Content already exists in $config_file"
    fi
}

# Check if PATH already contains the installation directory
if echo $PATH | grep -q "$INSTALL_DIR"; then
    echo "PATH already contains the installation directory"
else
    update_shell_config "$SHELL_CONFIG" "export PATH=\"$INSTALL_DIR:\$PATH\""
fi

# Apply changes to the current session
export PATH="$INSTALL_DIR:$PATH"

# Use exec to replace the current shell with a new one
exec "$SHELL"

# Provide instructions for the user
echo "Installation complete!"
echo "The 'ten' command should now be available in new terminal sessions."
echo "To use it in your current session, please run:"
echo " source $SHELL_CONFIG"
echo "or restart your terminal."

echo "To verify the installation, please run: ten --help"