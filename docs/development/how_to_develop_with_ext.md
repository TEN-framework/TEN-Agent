---
title: Complete Guide to TEN Extension Development
_portal_target: development/how_to_develop_with_ext.md
---

TEN Framework provides rich extension templates to help developers quickly create extensions and complete the entire process from development to testing. This guide will demonstrate in detail how to use C++, Go, Python, and Node.js for the complete extension development workflow through practical operations.

## Pre-development Preparation

### Environment Requirements

Before starting extension development, please ensure your development environment is properly configured. Verify the installation with the following command:

```bash
tman --version
```

Under normal circumstances, you should see version information output similar to the following:

```bash
TEN Framework version: <version>
```

> **Important Note**: Please ensure you are using `tman` version >= 0.10.12. If your version is too low, please refer to the [Quick Start Guide](https://theten.ai/docs/ten_framework/getting-started/quick-start) to install the latest version.

### Development Workflow Overview

Regardless of which programming language you use, TEN extension development follows the following standardized workflow:

1. **Project Creation** - Generate extension project skeleton using official templates
2. **Dependency Installation** - Configure runtime environment and install necessary dependency packages
3. **Core Development** - Implement extension business logic and functional code
4. **Build and Test** - Compile project (if needed) and execute unit tests
5. **Debug and Optimize** - Use professional debugging tools to locate and solve problems

---

## C++ Extension Development

C++ extensions are suitable for application scenarios with extremely high performance requirements, such as real-time audio and video processing, high-frequency data computation, low-level system operations, etc.

### Create Project

Use the official C++ extension template provided by TEN to quickly create a new project:

```bash
tman create extension my_example_ext_cpp --template default_extension_cpp
```

After successful project creation, you will get the following complete project structure:

```bash
my_example_ext_cpp/
├── BUILD.gn              # GN build system configuration file
├── manifest.json         # Extension metadata and configuration information
├── property.json         # Extension properties and parameter configuration
├── src/
│   └── main.cc           # Extension core implementation code
├── tests/
│   ├── basic.cc          # Basic functionality test cases
│   └── gtest_main.cc     # Test framework program entry
├── include/              # Header file storage directory
├── tools/                # Auxiliary tools and scripts
└── .vscode/
    └── launch.json       # VSCode debugging configuration file
```

### Environment Configuration Verification

Enter the project directory and verify that the build tools are working properly:

```bash
cd my_example_ext_cpp
tgn --version
```

> **Expected Output**:

```bash
0.1.0
```

If the command cannot be executed, please refer to the [Quick Start Guide](https://theten.ai/docs/ten_framework/getting-started/quick-start) to check whether the TEN Framework development environment is correctly installed.

### Dependency Package Installation

Install all dependency packages required for extension runtime:

```bash
tman install --standalone
```

After successful installation, you will see detailed installation logs similar to the following:

```bash
📦  Get all installed packages...
🔍  Filter compatible packages...
🔒  Creating manifest-lock.json...
📥  Installing packages...
  [00:00:00] [########################################]       3/3       Done

🏆  Install successfully in 1 second
```

### Project Build

TEN framework provides two convenient build methods for you to choose from:

#### Method 1: Manual Step-by-step Build

```bash
# Step 1: Generate build configuration files (enable standalone test mode)
tgn gen linux x64 debug -- ten_enable_standalone_test=true

# Step 2: Execute project build
tgn build linux x64 debug
```

#### Method 2: Use tman Shortcut Command

```bash
tman run build
```

After the build is complete, check the generated executable test file:

```bash
ls -la bin/
# You should see: my_example_ext_cpp_test
```

### Run Tests

Verify that the extension functionality is working properly:

#### Method 1: Execute Test File Directly

```bash
./bin/my_example_ext_cpp_test
```

#### Method 2: Use tman Unified Command

```bash
tman run test
```

Example output when tests execute successfully:

```bash
Running main() from ../../../tests/gtest_main.cc
[==========] Running 1 test from 1 test case.
[----------] 1 test from Test
[ RUN      ] Test.Basic
[       OK ] Test.Basic (20 ms)
[==========] 1 test from 1 test case ran. (79 ms total)
[  PASSED  ] 1 test.
```

> **Success Indicator**: When you see `[  PASSED  ] 1 test.` it means all tests have passed.

### Core Code Structure Explanation

#### Extension Main Implementation (src/main.cc)

The core class of C++ extensions needs to inherit from the `ten::extension_t` base class and implement complete lifecycle management methods:

```cpp
class my_example_ext_cpp_t : public ten::extension_t {
 public:
  // Extension initialization phase - basic configuration and resource pre-allocation
  void on_init(ten::ten_env_t &ten_env) override;

  // Extension startup phase - officially start processing business logic
  void on_start(ten::ten_env_t &ten_env) override;

  // Command handler - handle command requests from other extensions or applications
  void on_cmd(ten::ten_env_t &ten_env, std::unique_ptr<ten::cmd_t> cmd) override;

  // Data handler - handle general data flow
  void on_data(ten::ten_env_t &ten_env, std::unique_ptr<ten::data_t> data) override;

  // Audio frame handler - handle real-time audio stream data
  void on_audio_frame(ten::ten_env_t &ten_env, std::unique_ptr<ten::audio_frame_t> frame) override;

  // Video frame handler - handle real-time video stream data
  void on_video_frame(ten::ten_env_t &ten_env, std::unique_ptr<ten::video_frame_t> frame) override;

  // Extension stop phase - clean up resources and graceful shutdown
  void on_stop(ten::ten_env_t &ten_env) override;
};
```

#### Test Framework Implementation (tests/basic.cc)

Use TEN-specific test framework to write complete unit tests:

```cpp
class my_example_ext_cpp_tester : public ten::extension_tester_t {
 public:
  void on_start(ten::ten_env_tester_t &ten_env) override {
    // Create command object for testing
    auto new_cmd = ten::cmd_t::create("foo");

    // Send command to extension and verify response results
    ten_env.send_cmd(std::move(new_cmd), [](/* callback parameters */) {
      // Verify the correctness of test results here
    });
  }
};
```

### Debug Environment Configuration

#### VSCode Integrated Debugging

1. Install the **CodeLLDB** extension plugin for VSCode
2. Set breakpoints in source code
3. Select the "standalone test (lldb, launch)" debug configuration
4. Press F5 to start debugging session

Debug configuration file `.vscode/launch.json` content:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "standalone test (lldb, launch)",
      "type": "lldb",
      "request": "launch",
      "program": "${workspaceFolder}/bin/my_example_ext_cpp_test",
      "cwd": "${workspaceFolder}"
    }
  ]
}
```

#### Command Line Debugging

Use the classic GDB debugger for command-line debugging:

```bash
gdb ./bin/my_example_ext_cpp_test
(gdb) run
(gdb) bt  # View complete function call stack
```

---

## Go Extension Development

Go extensions provide a good balance between high performance and development efficiency, particularly suitable for building network services, concurrent processing, microservice architecture and other application scenarios.

### Create Project

Create a new project using the Go extension template:

```bash
tman create extension my_example_ext_go --template default_extension_go --template-data class_name_prefix=Example
```

After successful project creation, it will display:

```bash
🏆  Package 'extension:my_example_ext_go' created successfully in '/path/to/your/project' in 1 second.
```

The complete project structure is as follows:

```bash
my_example_ext_go/
├── extension.go             # Extension core implementation code
├── go.mod                   # Go module dependency management configuration
├── manifest.json            # Extension metadata information
├── property.json            # Extension property configuration
├── README.md                # Project documentation
├── tests/                   # Test-related files
│   ├── basic_tester.go      # Test logic implementation
│   ├── basic_tester_test.go # Test case definition
│   ├── main_test.go         # Test program entry
│   └── bin/start            # Test startup script
└── .vscode/launch.json      # VSCode debug configuration
```

### Dependency Package Installation

Install dependency packages required for project runtime:

```bash
tman install --standalone
```

### Run Tests

Verify the correctness of extension functionality:

#### Method 1: Use Startup Script

```bash
./tests/bin/start
```

#### Method 2: Use tman Command

```bash
tman run test
```

Example output when tests execute successfully:

```bash
=== RUN   TestBasicExtensionTester
--- PASS: TestBasicExtensionTester (0.01s)
PASS
```

### Core Code Structure Explanation

#### Extension Implementation (extension.go)

Core implementation structure of Go extensions:

```go
import (
    ten "ten_framework/ten_runtime"
)

type ExampleExtension struct {
    ten.DefaultExtension
}

// Extension startup lifecycle
func (e *ExampleExtension) OnStart(tenEnv ten.TenEnv) {
    tenEnv.LogDebug("OnStart")
    tenEnv.OnStartDone()
}

// Command handling logic
func (e *ExampleExtension) OnCmd(tenEnv ten.TenEnv, cmd ten.Cmd) {
    tenEnv.LogDebug("OnCmd")
    cmdResult, _ := ten.NewCmdResult(ten.StatusCodeOk, cmd)
    tenEnv.ReturnResult(cmdResult, nil)
}

// Extension stop lifecycle
func (e *ExampleExtension) OnStop(tenEnv ten.TenEnv) {
    tenEnv.LogDebug("OnStop")
    tenEnv.OnStopDone()
}
```

#### Test Framework (tests/basic_tester.go)

Go extension test framework implementation:

```go
type BasicExtensionTester struct {
    ten.DefaultExtensionTester
}

func (tester *BasicExtensionTester) OnStart(tenEnvTester ten.TenEnvTester) {
    // Create command object for testing
    cmdTest, _ := ten.NewCmd("test")

    // Send command and handle response results
    tenEnvTester.SendCmd(cmdTest, func(tet ten.TenEnvTester, cr ten.CmdResult, err error) {
        if err != nil {
            panic(err)
        }
        statusCode, _ := cr.GetStatusCode()
        if statusCode != ten.StatusCodeOk {
            panic(statusCode)
        }
        tenEnvTester.StopTest(nil)
    })

    tenEnvTester.OnStartDone()
}
```

### Development Environment Optimization

To improve development experience and debugging convenience, it is recommended to create a `go.work` workspace file in the extension root directory:

```go
go 1.18

use (
    .
    .ten/app/ten_packages/system/ten_runtime_go/interface
)
```

### Debug Environment Configuration

#### VSCode Integrated Debugging

Make sure the official Go extension is installed, then use the following debug configuration:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "standalone test (go, launch)",
      "type": "go",
      "request": "launch",
      "mode": "test",
      "program": "${workspaceFolder}/tests/",
      "env": {
        "CGO_LDFLAGS": "-L${workspaceFolder}/.ten/app/ten_packages/system/ten_runtime/lib -L${workspaceFolder}/.ten/app/ten_packages/system/ten_runtime_go/lib -lten_runtime -lten_runtime_go",
        "LD_LIBRARY_PATH": "${workspaceFolder}/.ten/app/ten_packages/system/ten_runtime/lib:${workspaceFolder}/.ten/app/ten_packages/system/ten_runtime_go/lib"
      },
      "args": ["-test.v"]
    }
  ]
}
```

---

## Python Extension Development

Python extensions have the highest development efficiency, particularly suitable for rapid prototyping, AI/ML application integration, complex business logic implementation and other scenarios.

### Create Project

Create a project using the Python async extension template:

```bash
tman create extension my_example_ext_python --template default_async_extension_python --template-data class_name_prefix=Example
```

Complete project structure:

```bash
my_example_ext_python/
├── extension.py         # Extension core implementation code
├── addon.py             # Extension plugin registration entry
├── __init__.py          # Python package initialization file
├── requirements.txt     # Python dependency package list
├── manifest.json        # Extension metadata configuration
├── property.json        # Extension property configuration
├── tests/               # Test-related files
│   ├── test_basic.py    # Basic test cases
│   ├── conftest.py      # pytest configuration file
│   └── bin/start        # Test startup script
└── .vscode/launch.json  # VSCode debug configuration
```

### Dependency Package Installation

Install Python dependency packages required for the project:

```bash
tman install --standalone
```

### Run Tests

Verify Python extension functionality:

#### Method 1: Use Startup Script

```bash
./tests/bin/start
```

#### Method 2: Use tman Command

```bash
tman run test
```

Example output when tests execute successfully:

```bash
============================================ test session starts ============================================
platform linux -- Python 3.10.17, pytest-8.3.4, pluggy-1.5.0
tests/test_basic.py .                                                                                [100%]
============================================ 1 passed in 0.04s =======================================
```

### Core Code Structure Explanation

#### Extension Implementation (extension.py)

Python extensions recommend using modern async programming patterns for better performance and concurrent processing capabilities:

```python
from ten_runtime import (
    AudioFrame, VideoFrame, AsyncExtension, AsyncTenEnv,
    Cmd, StatusCode, CmdResult, Data
)

class ExampleExtension(AsyncExtension):
    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_init")

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_start")
        # TODO: Read configuration files here, initialize necessary resources

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        ten_env.log_debug(f"on_cmd name {cmd_name}")

        # TODO: Implement specific business logic processing here
        cmd_result = CmdResult.create(StatusCode.OK, cmd)
        await ten_env.return_result(cmd_result)

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_stop")
        # TODO: Clean up resources here, perform graceful shutdown
```

#### Plugin Registration Entry (addon.py)

Extension plugin registration and creation logic:

```python
from ten_runtime import Addon, register_addon_as_extension, TenEnv
from .extension import ExampleExtension

@register_addon_as_extension("my_example_ext_python")
class ExampleExtensionAddon(Addon):
    def on_create_instance(self, ten_env: TenEnv, name: str, context) -> None:
        ten_env.log_info("on_create_instance")
        ten_env.on_create_instance_done(ExampleExtension(name), context)
```

#### Test Implementation (tests/test_basic.py)

Complete async test framework implementation:

```python
from ten_runtime import (
    AsyncExtensionTester, AsyncTenEnvTester, Cmd, StatusCode,
    TenError, TenErrorCode
)

class ExtensionTesterBasic(AsyncExtensionTester):
    async def on_start(self, ten_env: AsyncTenEnvTester) -> None:
        # Create command object for testing
        new_cmd = Cmd.create("hello_world")

        ten_env.log_debug("send hello_world")
        result, err = await ten_env.send_cmd(new_cmd)

        # Verify the correctness of test results
        if (err is not None or result is None
            or result.get_status_code() != StatusCode.OK):
            ten_env.stop_test(TenError.create(
                TenErrorCode.ErrorCodeGeneric,
                "Failed to send hello_world"
            ))
        else:
            ten_env.stop_test()

def test_basic():
    tester = ExtensionTesterBasic()
    tester.set_test_mode_single("my_example_ext_python")
    err = tester.run()
    if err is not None:
        assert False, err.error_message()
```

### Debug Environment Configuration

#### VSCode Integrated Debugging

Make sure you have installed the Python extension and debugpy debugger, use the following configuration for debugging:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "standalone test (debugpy, launch)",
      "type": "debugpy",
      "request": "launch",
      "python": "/usr/bin/python3",
      "module": "pytest",
      "args": ["-s", "${workspaceFolder}/tests/test_basic.py"],
      "env": {
        "TEN_ENABLE_PYTHON_DEBUG": "true",
        "PYTHONPATH": "${workspaceFolder}/.ten/app/ten_packages/system/ten_runtime_python/lib:${workspaceFolder}/.ten/app/ten_packages/system/ten_runtime_python/interface:${workspaceFolder}"
      },
      "console": "integratedTerminal"
    }
  ]
}
```

---

## Node.js Extension Development

Node.js extensions provide a modern JavaScript/TypeScript development experience, particularly suitable for Web application integration, rapid prototyping, frontend technology stack extensions and other scenarios. Thanks to Node.js's async characteristics and rich ecosystem, developers can easily build efficient real-time applications.

### Create Project

Use the official Node.js extension template provided by TEN to quickly create a new project:

```bash
tman create extension my_example_ext_nodejs --template default_extension_nodejs --template-data class_name_prefix=Example
```

After successful project creation, you will get the following complete project structure:

```bash
my_example_ext_nodejs/
├── manifest.json         # Extension metadata and configuration information
├── property.json         # Extension properties and parameter configuration
├── package.json          # Node.js dependency package management configuration
├── tsconfig.json         # TypeScript compiler configuration
├── src/
│   └── index.ts          # Extension core implementation code
├── tests/                # Test-related files
│   ├── src/
│   │   ├── index.ts      # Tester implementation
│   │   ├── index.spec.ts # Test case definition
│   │   └── main.spec.ts  # Test framework configuration
│   ├── bin/start         # Test startup script
│   ├── package.json      # Test dependency configuration
│   └── tsconfig.json     # Test TypeScript configuration
├── tools/                # Auxiliary tools and scripts
└── .vscode/
    └── launch.json       # VSCode debug configuration file
```

### Environment Configuration Verification

Enter the project directory and verify the development environment:

```bash
cd my_example_ext_nodejs
node --version
npm --version
```

> **Expected Output**:

```bash
v18.0.0 or higher
8.0.0 or higher
```

### Dependency Package Installation

Install all dependency packages required for extension runtime:

```bash
tman install --standalone
```

After successful installation, you will see detailed installation logs similar to the following:

```bash
📦  Get all installed packages...
🔍  Filter compatible packages...
🔒  Creating manifest-lock.json...
📥  Installing packages...
  [00:00:00] [########################################]       2/2       Done

🏆  Install successfully in 1 second
```

> **Important Note**: `tman install --standalone` will create a `.ten/app/ten_packages/extension/my_example_ext_nodejs/` directory in the project directory. Subsequent build and test operations need to be performed in this directory.

### Project Build

Node.js extensions are developed using TypeScript and need to install standalone mode dependencies first, then compile to JavaScript:

#### Method 1: Manual Build

```bash
# Enter the extension installation directory
cd .ten/app/ten_packages/extension/my_example_ext_nodejs

# Install standalone mode Node.js dependencies
npm run standalone-install

# Compile TypeScript code
npm run build
```

#### Method 2: Use tman Shortcut Command

```bash
tman run build
```

After the build is complete, check the generated compilation results:

```bash
ls -la .ten/app/ten_packages/extension/my_example_ext_nodejs/build/
# You should see: index.js and related mapping files
```

### Run Tests

Verify that the extension functionality is working properly:

#### Method 1: Use Startup Script

```bash
# Enter the extension installation directory
cd .ten/app/ten_packages/extension/my_example_ext_nodejs

# Run tests
./tests/bin/start
```

#### Method 2: Use tman Unified Command

```bash
tman run test
```

Example output when tests execute successfully:

```bash
MyExtensionTester onStart
MyExtensionTester onStop
MyExtensionTester onDeinit
deinit done
  ✓ case1 (1010ms)
MyExtensionTester onStart
MyExtensionTester onStop
MyExtensionTester onDeinit
deinit done
  ✓ case2 (1010ms)

  2 passing (2s)
```

> **Success Indicator**: When you see all test cases showing `✓` and finally displaying `passing`, it means all tests have passed.

### Core Code Structure Explanation

#### Extension Main Implementation (src/index.ts)

The core class of Node.js extensions needs to inherit from the `Extension` base class and implement complete lifecycle management methods:

```typescript
import {
  Addon,
  RegisterAddonAsExtension,
  Extension,
  TenEnv,
  Cmd,
  CmdResult,
  StatusCode,
} from "ten-runtime-nodejs";

class DefaultExtension extends Extension {
  constructor(name: string) {
    super(name);
  }

  // Extension configuration phase - read and validate configuration parameters
  async onConfigure(_tenEnv: TenEnv): Promise<void> {
    console.log("DefaultExtension onConfigure");
  }

  // Extension initialization phase - basic configuration and resource pre-allocation
  async onInit(_tenEnv: TenEnv): Promise<void> {
    console.log("DefaultExtension onInit");
  }

  // Extension startup phase - officially start processing business logic
  async onStart(_tenEnv: TenEnv): Promise<void> {
    console.log("DefaultExtension onStart");
  }

  // Command handler - handle command requests from other extensions or applications
  async onCmd(tenEnv: TenEnv, cmd: Cmd): Promise<void> {
    console.log("DefaultExtension onCmd", cmd.getName());

    const cmdResult = CmdResult.Create(StatusCode.OK, cmd);
    cmdResult.setPropertyString("detail", "This is a demo");
    tenEnv.returnResult(cmdResult);
  }

  // Extension stop phase - clean up resources and graceful shutdown
  async onStop(_tenEnv: TenEnv): Promise<void> {
    console.log("DefaultExtension onStop");
  }

  // Extension destruction phase - final cleanup and resource release
  async onDeinit(_tenEnv: TenEnv): Promise<void> {
    console.log("DefaultExtension onDeinit");
  }
}
```

#### Plugin Registration Entry

Extension plugin registration and creation logic:

```typescript
@RegisterAddonAsExtension("default_extension_nodejs")
class DefaultExtensionAddon extends Addon {
  async onCreateInstance(
    _tenEnv: TenEnv,
    instanceName: string,
  ): Promise<Extension> {
    return new DefaultExtension(instanceName);
  }
}
```

#### Test Framework Implementation (tests/src/index.ts)

Use TEN-specific test framework to write complete unit tests:

```typescript
import { ExtensionTester, TenEnvTester } from "ten-runtime-nodejs";

export class MyExtensionTester extends ExtensionTester {
  async onStart(tenEnvTester: TenEnvTester) {
    console.log("MyExtensionTester onStart");

    // Simulate async operations and test logic
    new Promise((resolve) => {
      setTimeout(() => {
        resolve(true);
      }, 1000);
    }).then(() => {
      // Stop test and return results
      tenEnvTester.stopTest();
    });
  }

  async onStop(tenEnvTester: TenEnvTester) {
    console.log("MyExtensionTester onStop");
  }

  async onDeinit(tenEnvTester: TenEnvTester) {
    console.log("MyExtensionTester onDeinit");
  }
}
```

#### Test Case Definition (tests/src/index.spec.ts)

Use Mocha test framework to write specific test cases:

```typescript
import assert from "assert";
import { MyExtensionTester } from "./index.js";

const test_addon_name = "default_extension_nodejs";

describe("MyExtensionTester", () => {
  it("case1", async () => {
    const extensionTester = new MyExtensionTester();
    extensionTester.setTestModeSingle(test_addon_name, "{}");
    const result = await extensionTester.run();
    assert(result === null, "result should be null");

    console.log("deinit done");
  });

  it("case2", async () => {
    const extensionTester = new MyExtensionTester();
    extensionTester.setTestModeSingle(test_addon_name, "{}");
    const result = await extensionTester.run();
    assert(result === null, "result should be null");

    console.log("deinit done");
  });
});
```

### TypeScript Configuration

Node.js extensions use modern TypeScript configuration, supporting the latest language features:

```json
{
  "compilerOptions": {
    "allowJs": false,
    "composite": true,
    "module": "NodeNext",
    "target": "es6",
    "moduleResolution": "NodeNext",
    "outDir": "build",
    "removeComments": false,
    "sourceMap": true,
    "noImplicitAny": true,
    "noImplicitThis": true,
    "noImplicitReturns": true,
    "strictNullChecks": true,
    "experimentalDecorators": true,
    "emitDecoratorMetadata": true,
    "rootDir": "src",
    "strict": true,
    "forceConsistentCasingInFileNames": true,
  },
  "exclude": [
    "node_modules"
  ],
  "include": [
    "src/**/*"
  ]
}
```

### Debug Environment Configuration

#### VSCode Integrated Debugging

Make sure you have installed the official Node.js extension, then use the following debug configuration:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "standalone test (nodejs) (mocha, launch)",
      "type": "node",
      "request": "launch",
      "program": "node_modules/mocha/bin/_mocha",
      "stopOnEntry": true,
      "args": [
        "--no-timeouts",
        "--package",
        "package.json",
      ],
      "cwd": "${workspaceFolder}/tests",
      "env": {
        "NODE_PATH": "../.ten/app/ten_packages/system/ten_runtime_nodejs/lib:$NODE_PATH",
      },
      "runtimeArgs": [
        "--expose-gc",
        "--loader",
        "ts-node/esm",
        "--no-warnings",
      ]
    }
  ]
}
```

#### Command Line Debugging

Use Node.js built-in debugger for command-line debugging:

```bash
# Enter the extension installation directory
cd .ten/app/ten_packages/extension/my_example_ext_nodejs

# Start debug mode
node --inspect-brk ./tests/bin/start

# Or use Chrome DevTools
node --inspect ./tests/bin/start
```

### Complete Development Process Summary

To help developers get started quickly, here is a complete Node.js extension development process summary:

```bash
# 1. Create extension project
tman create extension my_example_ext_nodejs --template default_extension_nodejs --template-data class_name_prefix=Example

# 2. Enter project directory
cd my_example_ext_nodejs

# 3. Install dependencies
tman install --standalone

# 4. Enter extension installation directory
cd .ten/app/ten_packages/extension/my_example_ext_nodejs

# 5. Install standalone mode dependencies
npm run standalone-install

# 6. Build project
npm run build

# 7. Run tests
./tests/bin/start
```

> **Working Directory Note**:
>
> - Extension source code is located in the `src/` folder at the project root directory
> - Actual build, test, and run operations are performed in the `.ten/app/ten_packages/extension/my_example_ext_nodejs/` directory
> - This design ensures extension independence and proper dependency management

### Development Best Practices

#### Async Programming

Node.js extensions fully utilize async programming patterns for better performance:

```typescript
// Recommended: Use async/await
async onCmd(tenEnv: TenEnv, cmd: Cmd): Promise<void> {
  try {
    const result = await processCommand(cmd);
    const cmdResult = CmdResult.Create(StatusCode.OK, cmd);
    cmdResult.setPropertyString("result", result);
    tenEnv.returnResult(cmdResult);
  } catch (error) {
    const cmdResult = CmdResult.Create(StatusCode.ERROR, cmd);
    cmdResult.setPropertyString("error", error.message);
    tenEnv.returnResult(cmdResult);
  }
}
```

#### Error Handling

Implement comprehensive error handling mechanisms:

```typescript
async onCmd(tenEnv: TenEnv, cmd: Cmd): Promise<void> {
  try {
    // Business logic processing
    const result = await this.handleBusinessLogic(cmd);

    const cmdResult = CmdResult.Create(StatusCode.OK, cmd);
    cmdResult.setPropertyString("data", JSON.stringify(result));
    tenEnv.returnResult(cmdResult);
  } catch (error) {
    console.error("Command processing error:", error);

    const cmdResult = CmdResult.Create(StatusCode.ERROR, cmd);
    cmdResult.setPropertyString("error", error.message);
    tenEnv.returnResult(cmdResult);
  }
}
```

---

---

## LLM Extension Development

TEN Framework provides two base classes for building LLM extensions that plug into the voice-assistant pipeline. Both live in the `ten_ai_base` system package.

| Base class | Protocol | Best for |
|------------|----------|----------|
| `AsyncLLMBaseExtension` | Streaming text-in / text-out, tool dispatch | Chat-completion providers (OpenAI, xAI Grok, Bedrock, …) |
| `AsyncLLMToolBaseExtension` | Tool registration + result return | Custom tools called by an LLM extension |

### Building an LLM extension with `AsyncLLMBaseExtension`

`AsyncLLMBaseExtension` handles the conversation loop, memory management, user-join/leave commands, and flush. You only implement three methods.

```python
# my_llm_python/extension.py
from typing import AsyncGenerator
from ten_ai_base.llm import AsyncLLMBaseExtension
from ten_ai_base.types import (
    LLMCallCompletionArgs,
    LLMDataCompletionArgs,
    LLMToolMetadata,
)
from ten_runtime.async_ten_env import AsyncTenEnv
from .client import MyLLMClient, MyLLMConfig


class MyLLMExtension(AsyncLLMBaseExtension):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.config: MyLLMConfig | None = None
        self.client: MyLLMClient | None = None

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("on_start")
        await super().on_start(ten_env)

        self.config = await MyLLMConfig.create_async(ten_env=ten_env)
        if not self.config.api_key:
            ten_env.log_warn("api_key not set, LLM will not respond")
            return

        self.client = MyLLMClient(ten_env, self.config)

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("on_stop")
        await super().on_stop(ten_env)

    # ------------------------------------------------------------------ #
    # Called for each user message that enters the conversation queue.     #
    # Stream text tokens back via self.send_text_output().                #
    # ------------------------------------------------------------------ #
    async def on_data_chat_completion(
        self, ten_env: AsyncTenEnv, **kargs: LLMDataCompletionArgs
    ) -> None:
        messages = kargs.get("messages", [])
        if not messages:
            ten_env.log_error("no messages in request")
            return
        if not self.client:
            raise RuntimeError("client not initialised")

        async for token in self.client.stream_chat(messages):
            self.send_text_output(ten_env, token, end_of_segment=False)

        # Signal end of this turn.
        self.send_text_output(ten_env, "", end_of_segment=True)

    # ------------------------------------------------------------------ #
    # Called when another extension (e.g. main_python) issues a           #
    # synchronous call_chat_completion command.                           #
    # ------------------------------------------------------------------ #
    async def on_call_chat_completion(
        self, ten_env: AsyncTenEnv, **kargs: LLMCallCompletionArgs
    ) -> str:
        messages = kargs.get("messages", [])
        if not self.client:
            raise RuntimeError("client not initialised")
        result = await self.client.chat(messages)
        return result.to_json()

    # ------------------------------------------------------------------ #
    # Called when a tool extension registers its metadata.               #
    # Delegate to the base class to add the tool to the available set.   #
    # ------------------------------------------------------------------ #
    async def on_tools_update(
        self, ten_env: AsyncTenEnv, tool: LLMToolMetadata
    ) -> None:
        return await super().on_tools_update(ten_env, tool)
```

Key points:

- `send_text_output(ten_env, text, end_of_segment)` — emit a text token to the downstream TTS extension. Call with `end_of_segment=True` and empty text to close the turn.
- `self.available_tools` — list of `LLMToolMetadata` registered by connected tool extensions. Pass this to your API client when building the request.
- `on_data_chat_completion` runs in a cancellable async task managed by the base class. If a flush arrives mid-stream, the task is cancelled automatically.
- Call `await super().on_start(ten_env)` and `await super().on_stop(ten_env)` — the base class wires up the data queue and command handlers.

**Extension addon registration (`addon.py`):**

```python
from ten_runtime import Addon, register_addon_as_extension, TenEnv
from .extension import MyLLMExtension


@register_addon_as_extension("my_llm_python")
class MyLLMExtensionAddon(Addon):
    def on_create_instance(self, ten_env: TenEnv, name: str, context) -> None:
        ten_env.log_info("on_create_instance")
        ten_env.on_create_instance_done(MyLLMExtension(name), context)
```

---

### Building a tool extension with `AsyncLLMToolBaseExtension`

Tool extensions register their schema with connected LLM extensions and handle tool-call invocations.

```python
# my_tool_python/extension.py
import json
from ten_ai_base.llm_tool import AsyncLLMToolBaseExtension
from ten_ai_base.types import LLMToolMetadata, LLMToolParameter, LLMToolResult
from ten_runtime.async_ten_env import AsyncTenEnv


class WebSearchToolExtension(AsyncLLMToolBaseExtension):
    def get_tool_metadata(self, ten_env: AsyncTenEnv) -> list[LLMToolMetadata]:
        return [
            LLMToolMetadata(
                name="web_search",
                description="Search the web and return a summary of the top results.",
                parameters=[
                    LLMToolParameter(
                        name="query",
                        type="string",
                        description="The search query.",
                        required=True,
                    ),
                    LLMToolParameter(
                        name="max_results",
                        type="integer",
                        description="Maximum number of results to return (default 3).",
                        required=False,
                    ),
                ],
            )
        ]

    async def run_tool(
        self, ten_env: AsyncTenEnv, name: str, args: dict
    ) -> LLMToolResult | None:
        if name != "web_search":
            return None

        query = args.get("query", "")
        max_results = int(args.get("max_results", 3))

        ten_env.log_info(f"web_search: query={query!r} max_results={max_results}")

        # Replace with a real search client call.
        results = await self._do_search(query, max_results)
        summary = "\n".join(f"- {r['title']}: {r['snippet']}" for r in results)

        return LLMToolResult(
            type="llmresult",
            content=summary,
        )

    async def _do_search(self, query: str, max_results: int) -> list[dict]:
        # Stub — replace with actual search API call.
        return [{"title": "Example", "snippet": f"Result for {query!r}"}]
```

Key points:

- `get_tool_metadata` is called once at startup. Return one `LLMToolMetadata` per tool your extension provides.
- `run_tool` is called by the base class when the connected LLM requests a tool call. Return `LLMToolResult(type="llmresult", content=<str>)` to feed the result back to the LLM, or `LLMToolResult(type="requery", content=<str>)` to append extra context and re-run the LLM call.
- Return `None` for unrecognised tool names.

**Graph wiring in `property.json`:**

Connect the tool extension to the LLM extension in the graph so that tool registration and invocations are routed correctly:

```json
{
  "ten": {
    "nodes": [
      { "type": "extension", "name": "my_llm_python",      "addon": "my_llm_python" },
      { "type": "extension", "name": "my_tool_python",     "addon": "my_tool_python" }
    ],
    "connections": [
      {
        "extension": "my_tool_python",
        "cmd": [
          { "name": "tool_register", "dest": [{ "extension": "my_llm_python" }] }
        ]
      },
      {
        "extension": "my_llm_python",
        "cmd": [
          { "name": "tool_call", "dest": [{ "extension": "my_tool_python" }] }
        ]
      }
    ]
  }
}
```

---

### Real-world references

The following extensions in this repository are good starting points for understanding the full implementation:

| Extension | Base class | Notes |
|-----------|------------|-------|
| `ai_agents/agents/ten_packages/extension/grok_python` | `AsyncLLMBaseExtension` | xAI Grok streaming, tool dispatch, reasoning token handling |
| `ai_agents/agents/ten_packages/extension/openai_llm2_python` | `AsyncLLM2BaseExtension` | OpenAI LLM2 protocol, think-block parsing |
| `ai_agents/agents/ten_packages/extension/bingsearch_tool_python` | `AsyncLLMToolBaseExtension` | Bing web-search tool, `requery` result type |

---

## Development Summary

By following the complete development process provided in this guide, you can efficiently develop, test, and debug TEN extensions. Whether you choose C++, Go, Python, or Node.js, TEN Framework provides you with a complete toolchain and best practices to help you fully leverage the powerful features of TEN Framework and build high-performance, high-reliability extension applications.

Each language has its unique advantages and applicable scenarios:

- **C++**: Suitable for scenarios with extremely high performance requirements, such as real-time audio and video processing, high-frequency computation
- **Go**: Provides a balance between high performance and development efficiency, suitable for network services, concurrent processing
- **Python**: Has the highest development efficiency, particularly suitable for AI/ML applications, rapid prototyping
- **Node.js**: Provides modern Web development experience, suitable for frontend technology stack extensions, real-time applications

Please choose the most suitable development solution based on your specific needs and team technology stack. During the development process, it is recommended to fully utilize the debugging tools and testing frameworks provided by TEN Framework to ensure the quality and stability of your extensions.
