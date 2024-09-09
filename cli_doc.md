# TEN Framework CLI Documentation

## Table of Contents

1. [Installation](#installation)
2. [Usage](#usage)
3. [Commands](#commands)
   - [extension](#extension)
   - [build](#build)
   - [clean](#clean)
   - [docker-build](#docker-build)
   - [run-gd-server](#run-gd-server)
   - [run-server](#run-server)
   - [run-dev](#run-dev)
   - [run-services](#run-services)
   - [run-all](#run-all)
   - [stop-all](#stop-all)
4. [Getting Help](#getting-help)

## Installation

To install the TEN Framework CLI tool, follow these steps:

1. Clone the TEN Framework repository:

   ```
   git clone https://github.com/TEN-framework/astra.ai.git
   cd astra.ai
   ```

2. Run the installation script:

   ```
   chmod +x install_cli.sh
   ./install_cli.sh
   ```

3. The installation script will:

   - For macOS and Linux:

     - Install the `ten` script in `$HOME/.local/bin`
     - Make the script executable
     - Update your PATH in the appropriate shell configuration file (`.bashrc` or `.zshrc`)

   - For Windows:

     - Create a directory at `%USERPROFILE%\ten-cli`
     - Copy the `ten` script to this directory
     - Create a `ten.bat` file to run the Python script

4. After installation:

   - For macOS and Linux:

     - The script will automatically update your PATH
     - To use the `ten` command in your current session, run:
       ```
       source ~/.bashrc
       ```
       (or `~/.zshrc` if you're using zsh)
     - Alternatively, you can restart your terminal

   - For Windows:
     - Add the `%USERPROFILE%\ten-cli` directory to your PATH manually:
       1. Search for "Environment Variables" in the Start menu and open it
       2. Under "User variables", find the PATH variable and click Edit
       3. Click New and add the full path to the ten-cli directory
       4. Click OK to save the changes
     - Restart any open Command Prompt or PowerShell windows

5. Verify the installation by running:

   ```
   ten --help
   ```

   This should display the help message for the TEN Framework CLI.

Note: The installation script assumes that Python and pip are already installed on your system. Make sure you have Python installed before running the installation script.

If you encounter any permission issues during installation, you may need to use `sudo` for some operations on Linux, or run the script with administrator privileges on Windows.

## Usage

After installation, you can use the `ten` command followed by a subcommand and any necessary options. The basic syntax is:

```
ten <command> [options]
```

## Commands

### extension

Create a new extension for the TEN Framework.

Usage:

```
ten extension [name] [language]
ten extension --name <name> --language <language>
ten extension -n <name> -l <language>
```

Options:

- `name`: Name of the extension
- `language`: Programming language for the extension (python, go, cpp)

If you don't provide the name or language, the CLI will prompt you for this information.

### build

Build the project or specific components.

Usage:

```
ten build [target]
```

Options:

- `target`: Build target (all, agents, playground, server). Default is 'all'.

### clean

Clean build artifacts.

Usage:

```
ten clean
```

### docker-build

Build Docker images for the project.

Usage:

```
ten docker-build [target]
```

Options:

- `target`: Docker build target (all, playground, server). Default is 'all'.

### run-gd-server

Run the Graph Designer server.

Usage:

```
ten run-gd-server
```

### run-server

Run the main server.

Usage:

```
ten run-server
```

### run-dev

Build and run the server (development mode).

Usage:

```
ten run-dev
```

### run-services

Run specified services.

Usage:

```
ten run-services [services...] [--build]
```

Options:

- `services`: Names of services to run
- `--build`: Build containers when running services

### run-all

Run all services.

Usage:

```
ten run-all [--build]
```

Options:

- `--build`: Build containers when running all services

### stop-all

Stop all running services.

Usage:

```
ten stop-all
```

## Getting Help

You can get help on using the CLI in several ways:

1. General help:

   ```
   ten help
   ten --help
   ten -h
   ```

2. Command-specific help:

   ```
   ten <command> --help
   ```

   Replace `<command>` with any of the available commands.

3. Running `ten` without any arguments will also display the help message.
