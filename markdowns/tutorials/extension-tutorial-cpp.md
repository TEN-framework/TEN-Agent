# Overview

This tutorial introduces how to develop an ASTRA extension using C++, as well as how to debug and deploy it to run in an ASTRA app. This tutorial covers the following topics:

- How to create a C++ extension development project using arpm.
- How to use ASTRA API to implement the functionality of the extension, such as sending and receiving messages.
- How to write unit test cases and debug the code.
- How to deploy the extension locally to an app and perform integration testing within the app.
- How to debug the extension code within the app.

<div class="note">

<div class="title">

Note

</div>

 Unless otherwise specified, the commands and code in this tutorial are executed in a Linux environment. Since ASTRA has a consistent development approach and logic across all platforms (e.g., Windows, Mac), this tutorial is also suitable for other platforms.

</div>

## Preparation

- Download the latest arpm and configure the PATH. You can check if it is configured correctly with the following command:

  ``` shell
  $ arpm -h
  ```

  If the configuration is successful, it will display the help information for arpm as follows:

  ``` text
  Usage: arpm [OPTIONS] <COMMAND>

  Commands:
  install     Install a package. For more detailed usage, run 'install -h'
  publish     Publish a package. For more detailed usage, run 'publish -h'
  dev-server  Install a package. For more detailed usage, run 'dev-server -h'
  help        Print this message or the help of the given subcommand(s)

  Options:
      --config-file <CONFIG_FILE>  The location of config.json
  -h, --help                       Print help
  -V, --version                    Print version
  ```

- Download the latest standalone_gn and configure the PATH. For example:

  <div class="note">

  <div class="title">

  Note

  </div>

  standalone_gn is the C++ build system for the ASTRA platform. To facilitate developers, ASTRA provides a standalone_gn toolchain for building C++ extension projects.

  </div>

  ``` shell
  $ export PATH=/path/to/standalone_gn:$PATH
  ```

  You can check if the configuration is successful with the following command:

  ``` shell
  $ ag -h
  ```

  If the configuration is successful, it will display the help information for standalone_gn as follows:

  ``` text
  usage: ag [-h] [-v] [--verbose | --no-verbose] [--out_file OUT_FILE] [--out_dir OUT_DIR] command target_OS target_CPU build_type

  An easy-to-use Google gn wrapper

  positional arguments:
    command               possible commands are:
                          gen         build        rebuild            refs    clean
                          graph       uninstall    explain_build      desc    check
                          show_deps   show_input   show_input_output  path    args
    target_OS             possible OS values are:
                          win   mac   ios   android   linux
    target_CPU            possible values are:
                          x64   x64   arm   arm64
    build_type            possible values are:
                          debug   release

  options:
    -h, --help            show this help message and exit
    -v, --version         show program's version number and exit
    --verbose, --no-verbose
                          dump verbose outputs
    --out_file OUT_FILE   dump command output to a file
    --out_dir OUT_DIR     build output dir, default is 'out/'
  ```

  <div class="note">

  <div class="title">

  Note

  </div>

  - gn depends on python3, please make sure that Python 3.10 or above is installed.

  </div>

- Install a C/C++ compiler, either clang/clang++ or gcc/g++.

In addition, we provide a base compilation image where all of the above dependencies are already installed and configured. You can refer to the [ASTRA.ai](https://github.com/rte-design/ASTRA.ai) project on GitHub.

## Creating C++ extension project

### Creating Based on Templates

Assuming we want to create a project named <span class="title-ref">first_cxx_extension</span>, we can use the following command to create it:

``` shell
$ arpm install extension default_extension_cpp --template-mode --template-data package_name=first_cxx_extension
```

<div class="note">

<div class="title">

Note

</div>

The above command indicates that we are installing an ASTRA package using the <span class="title-ref">default_extension_cpp</span> template to create an extension project named <span class="title-ref">first_cxx_extension</span>.

- <span class="title-ref">--template-mode</span> indicates installing the ASTRA package as a template. The template rendering parameters can be specified using <span class="title-ref">--template-data</span>.
- <span class="title-ref">extension</span> is the type of ASTRA package to install. Currently, ASTRA provides app/extension_group/extension/system packages. In the following sections on testing extensions in an app, we will use several other types of packages.
- <span class="title-ref">default_extension_cpp</span> is the default C++ extension provided by ASTRA. Developers can also specify other C++ extensions available in the store as templates.

</div>

After the command is executed, a directory named <span class="title-ref">first_cxx_extension</span> will be generated in the current directory, which is our C++ extension project. The directory structure is as follows:

``` text
.
├── BUILD.gn
├── manifest.json
├── property.json
└── src
  └── main.cc
```

Where:

- <span class="title-ref">src/main.cc</span> contains a simple implementation of the extension, including calls to the C++ API provided by ASTRA. We will discuss how to use the ASTRA API in the next section.
- <span class="title-ref">manifest.json</span> and <span class="title-ref">property.json</span> are the standard configuration files for ASTRA extensions. In <span class="title-ref">manifest.json</span>, metadata information such as the version, dependencies, and schema definition of the extension are typically declared. <span class="title-ref">property.json</span> is used to declare the business configuration of the extension.
- <span class="title-ref">BUILD.gn</span> is the configuration file for standalone_gn, used to compile the C++ extension project.

The <span class="title-ref">property.json</span> file is initially an empty JSON file, like this:

``` json
{}
```

The <span class="title-ref">manifest.json</span> file will include the <span class="title-ref">rte_runtime</span> dependency by default, like this:

``` json
{
  "type": "extension",
  "name": "first_cxx_extension",
  "version": "0.2.0",
  "language": "cpp",
  "dependencies": [
  {
    "type": "system",
    "name": "rte_runtime",
    "version": "0.2.0"
  }
  ],
  "api": {}
}
```

<div class="note">

<div class="title">

Note

</div>

- Please note that according to ASTRA's naming convention, the <span class="title-ref">name</span> should be alphanumeric. This is because when integrating the extension into an app, a directory will be created based on the extension name. ASTRA also provides the functionality to automatically load the manifest.json and property.json files from the extension directory.
- Dependencies are used to declare the dependencies of the extension. When installing ASTRA packages, arpm will automatically download the dependencies based on the declarations in the dependencies section.
- The api section is used to declare the schema of the extension. Refer to `usage of rte schema <usage_of_rte_schema_cn>`.

</div>

### Manual Creation

Developers can also manually create a C++ extension project or transform an existing project into an ASTRA extension project.

First, ensure that the project's output target is a shared library. Then, refer to the example above to create `property.json` and `manifest.json` in the project's root directory. The `manifest.json` should include information such as `type`, `name`, `version`, `language`, and `dependencies`. Specifically:

- `type` must be `extension`.
- `language` must be `cpp`.
- `dependencies` should include `rte_runtime`.

Finally, configure the build settings. The `default_extension_cpp` provided by ASTRA uses `standalone_gn` as the build toolchain. If developers are using a different build toolchain, they can refer to the configuration in `BUILD.gn` to set the compilation parameters. Since `BUILD.gn` contains the directory structure of the ASTRA package, we will discuss it in the next section (Downloading Dependencies).


## Download Dependencies

To download dependencies, execute the following command in the extension project directory:

``` shell
$ arpm install
```

After the command is executed successfully, a `.rte` directory will be generated in the current directory, which contains all the dependencies of the current extension.

<div class="note">

<div class="title">

Note

</div>

- There are two modes for extensions: development mode and runtime mode. In development mode, the root directory is the source code directory of the extension. In runtime mode, the root directory is the app directory. Therefore, the placement path of dependencies is different in these two modes. The `.rte` directory mentioned here is the root directory of dependencies in development mode.

</div>

The directory structure is as follows:

``` text
.
├── BUILD.gn
├── manifest.json
├── property.json
├── .rte
│   └── app
│       ├── addon
│       ├── include
│       └── lib
└── src
  └── main.cc
```

Where:
- `.rte/app/include` is the root directory for header files.
- `.rte/app/lib` is the root directory for precompiled dynamic libraries of ASTRA runtime.

If it is in runtime mode, the extension will be placed in the `addon/extension` directory of the app, and the dynamic libraries will be placed in the `lib` directory of the app. The structure is as follows:

``` text
.
├── BUILD.gn
├── manifest.json
├── property.json
├── addon
│   └── extension
│       └── first_cxx_extension
├── include
└── lib
```

So far, an ASTRA C++ extension project has been created.

## BUILD.gn

The content of `BUILD.gn` for `default_extension_cpp` is as follows:

``` python
import("//exts/rte/base_options.gni")
import("//exts/rte/rte_package.gni")

config("common_config") {
  defines = common_defines
  include_dirs = common_includes
  cflags = common_cflags
  cflags_c = common_cflags_c
  cflags_cc = common_cflags_cc
  cflags_objc = common_cflags_objc
  cflags_objcc = common_cflags_objcc
  libs = common_libs
  lib_dirs = common_lib_dirs
  ldflags = common_ldflags
}

config("build_config") {
  configs = [ ":common_config" ]

  # 1. The `include` refers to the `include` directory in current extension.
  # 2. The `//include` refers to the `include` directory in the base directory
  #    of running `ag gen`.
  # 3. The `.rte/app/include` is used in extension standalone building.
  include_dirs = [
  "include",
  "//include",
  "//include/nlohmann_json",
  ".rte/app/include",
  ".rte/app/include/nlohmann_json",
  ]

  lib_dirs = [
  "lib",
  "//lib",
  ".rte/app/lib",
  ]

  if (is_win) {
  libs = [
    "rte_runtime.dll.lib",
    "utils.dll.lib",
  ]
  } else {
  libs = [
    "rte_runtime",
    "utils",
  ]
  }
}

rte_package("first_cxx_extension") {
  package_type = "develop"  # develop | release
  package_kind = "extension"

  manifest = "manifest.json"
  property = "property.json"

  if (package_type == "develop") {
  # It's 'develop' package, therefore, need to build the result.
  build_type = "shared_library"

  sources = [ "src/main.cc" ]

  configs = [ ":build_config" ]
  }
}
```

Let's first take a look at the `rte_package` target, which declares a build target for an ASTRA package.

- The `package_kind` is set to `extension`, and the `build_type` is set to `shared_library`. This means that the expected output of the compilation is a shared library.
- The `sources` field specifies the source file(s) to be compiled. If there are multiple source files, they need to be added to the `sources` field.
- The `configs` field specifies the build configurations. It references the `build_config` defined in this file.

Next, let's look at the content of `build_config`.

- The `include_dirs` field defines the search paths for header files.
  - The difference between `include` and `//include` is that `include` refers to the `include` directory in the current extension directory, while `//include` is based on the working directory of the `ag gen` command. So, if the compilation is executed in the extension directory, it will be the same as `include`. But if it is executed in the app directory, it will be the `include` directory in the app.
  - `.rte/app/include` is used for standalone development and compilation of the extension, which is the scenario being discussed in this tutorial. In other words, the default `build_config` is compatible with both development mode and runtime mode compilation.
- The `lib_dirs` field defines the search paths for dependency libraries. The difference between `lib` and `//lib` is similar to `include`.
- The `libs` field defines the dependent libraries. `rte_runtime` and `utils` are libraries provided by ASTRA.

Therefore, if developers are using a different build toolchain, they can refer to the above configuration and set the compilation parameters in their own build toolchain. For example, if using g++ to compile:

``` shell
$ g++ -shared -fPIC -I.rte/app/include/ -L.rte/app/lib -lrte_runtime -lutils -Wl,-rpath=\$ORIGIN -Wl,-rpath=\$ORIGIN/../../../lib src/main.cc
```

The setting of `rpath` is also considered for the runtime mode, where the rte_runtime dependency of the extension is placed in the `app/lib` directory.

## Implementation of Extension Functionality

For developers, there are two things to do:

- Create an extension as a channel for interacting with ASTRA runtime.
- Register the extension as an addon in ASTRA, allowing it to be used in the graph through a declarative approach.

### Creating the Extension Class

The extension created by developers needs to inherit the `rte::extension_t` class. The main definition of this class is as follows:

``` C++
class extension_t {
protected:
  explicit extension_t(const std::string &name) {...}

  virtual void on_init(rte_t &rte, metadata_info_t &manifest,
                     metadata_info_t &property) {
    rte.on_init_done(manifest, property);
  }

  virtual void on_start(rte_t &rte) { rte.on_start_done(); }

  virtual void on_stop(rte_t &rte) { rte.on_stop_done(); }

  virtual void on_deinit(rte_t &rte) { rte.on_deinit_done(); }

  virtual void on_cmd(rte_t &rte, std::unique_ptr<cmd_t> cmd) {
    auto cmd_result = rte::cmd_result_t::create(RTE_STATUS_CODE_OK);
    cmd_result->set_property("detail", "default");
    rte.return_result(std::move(cmd_result), std::move(cmd));
  }

  virtual void on_data(rte_t &rte, std::unique_ptr<data_t> data) {}

  virtual void on_pcm_frame(rte_t &rte, std::unique_ptr<pcm_frame_t> frame) {}

  virtual void on_image_frame(rte_t &rte,
                              std::unique_ptr<image_frame_t> frame) {}
}
```

### Message Handling

ASTRA provides four types of messages: `cmd`, `data`, `image_frame`, and `pcm_frame`. Developers can handle these four types of messages by implementing the `on_cmd`, `on_data`, `on_image_frame`, and `on_pcm_frame` callback methods.

Taking `cmd` as an example, let's see how to receive and send messages.

Assume that `first_cxx_extension` receives a `cmd` with the name `hello`, which includes the following properties:

| name            | type   |
|-----------------|--------|
| app_id          | string |
| client_type     | int8   |
| payload         | object |
| payload.err_no  | uint8  |
| payload.err_msg | string |

The processing logic of `first_cxx_extension` for the `hello` cmd is as follows:

- If the `app_id` or `client_type` parameters are invalid, return an error:

  ``` json
  {
    "err_no": 1001,
    "err_msg": "Invalid argument."
  }
  ```

- If `payload.err_no` is greater than 0, return an error with the content from the `payload`.

- If `payload.err_no` is equal to 0, forward the `hello` cmd downstream for further processing. After receiving the processing result from the downstream extension, return the result.

#### Describing the Extension's Behavior in manifest.json

Based on the above description, the behavior of `first_cxx_extension` is as follows:

- It receives a `cmd` named `hello` with properties.
- It may send a `cmd` named `hello` with properties.
- It receives a response from a downstream extension, which includes error information.
- It returns a response to an upstream extension, which includes error information.

For an ASTRA extension, you can describe the above behavior in the `manifest.json` file of the extension, including:

- What messages the extension receives, their names, and the structure definition of their properties (schema definition).
- What messages the extension generates/sends, their names, and the structure definition of their properties.
- Additionally, for `cmd` type messages, a response definition is required (referred to as a result in ASTRA).

With these definitions, ASTRA runtime will perform validity checks based on the schema definition before delivering messages to the extension or when the extension sends messages through ASTRA runtime. It also helps the users of the extension to see the protocol definition.

The schema is defined in the `api` field of the `manifest.json` file. `cmd_in` defines the cmds that the extension will receive, and `cmd_out` defines the cmds that the extension will send.

<div class="note">

<div class="title">

Note

</div>

For the usage of schema, refer to: `usage of rte schema <usage_of_rte_schema_cn>`.

</div>

Based on the above description, the content of `manifest.json` for `first_cxx_extension` is as follows:

``` json
{
  "type": "extension",
  "name": "first_cxx_extension",
  "version": "0.2.0",
  "language": "cpp",
  "dependencies": [
    {
      "type": "system",
      "name": "rte_runtime",
      "version": "0.2.0"
    }
  ],
  "api": {
    "cmd_in": [
      {
        "name": "hello",
        "property": {
          "app_id": {
            "type": "string"
          },
          "client_type": {
            "type": "int8"
          },
          "payload": {
            "type": "object",
            "properties": {
              "err_no": {
                "type": "uint8"
              },
              "err_msg": {
                "type": "string"
              }
            }
          }
        },
        "required": ["app_id", "client_type"],
        "result": {
          "property": {
            "err_no": {
              "type": "uint8"
            },
            "err_msg": {
              "type": "string"
            }
          },
          "required": ["err_no"]
        }
      }
    ],
    "cmd_out": [
      {
        "name": "hello",
        "property": {
          "app_id": {
            "type": "string"
          },
          "client_type": {
            "type": "string"
          },
          "payload": {
            "type": "object",
            "properties": {
              "err_no": {
                "type": "uint8"
              },
              "err_msg": {
                "type": "string"
              }
            }
          }
        },
        "required": ["app_id", "client_type"],
        "result": {
          "property": {
            "err_no": {
              "type": "uint8"
            },
            "err_msg": {
              "type": "string"
            }
          },
          "required": ["err_no"]
        }
      }
    ]
  }
}
```


#### Getting Request Data

In the `on_cmd` method, the first step is to retrieve the request data, which is the property in the cmd. We define a `request_t` class to represent the request data.

Create a file called `model.h` in the `include` directory of your extension project with the following content:

```cpp
#pragma once

#include "nlohmann/json.hpp"
#include <cstdint>
#include <string>

namespace first_cxx_extension_extension {

class request_payload_t {
public:
  friend void from_json(const nlohmann::json &j, request_payload_t &payload);

  friend class request_t;

private:
  uint8_t err_no;
  std::string err_msg;
};

class request_t {
public:
  friend void from_json(const nlohmann::json &j, request_t &request);

private:
  std::string app_id;
  int8_t client_type;
  request_payload_t payload;
};

} // namespace first_cxx_extension_extension
```

In the `src` directory, create a file called `model.cc` with the following content:

```cpp
#include "model.h"

namespace first_cxx_extension_extension {
void from_json(const nlohmann::json &j, request_payload_t &payload) {
  if (j.contains("err_no")) {
    j.at("err_no").get_to(payload.err_no);
  }

  if (j.contains("err_msg")) {
    j.at("err_msg").get_to(payload.err_msg);
  }
}

void from_json(const nlohmann::json &j, request_t &request) {
  if (j.contains("app_id")) {
    j.at("app_id").get_to(request.app_id);
  }

  if (j.contains("client_type")) {
    j.at("client_type").get_to(request.client_type);
  }

  if (j.contains("payload")) {
    j.at("payload").get_to(request.payload);
  }
}
} // namespace first_cxx_extension_extension
```

To parse the request data, you can use the `get_property` API provided by ASTRA. Here is an example of how to implement it:

```cpp
// model.h

class request_t {
public:
  void from_cmd(rte::cmd_t &cmd);

  // ...
}

// model.cc

void request_t::from_cmd(rte::cmd_t &cmd) {
  app_id = cmd.get_property_string("app_id");
  client_type = cmd.get_property_int8("client_type");

  auto payload_str = cmd.get_property_to_json("payload");
  if (!payload_str.empty()) {
    auto payload_json = nlohmann::json::parse(payload_str);
    from_json(payload_json, payload);
  }
}
```

To return a response, you need to create a `cmd_result_t` object and set the properties accordingly. Then, pass the `cmd_result_t` object to ASTRA runtime to return it to the requester. Here is an example:

```cpp
// model.h

class request_t {
public:
  bool validate(std::string *err_msg) {
    if (app_id.length() < 64) {
      *err_msg = "invalid app_id";
      return false;
    }

    return true;
  }
}

// main.cc

void on_cmd(rte::rte_t &rte, std::unique_ptr<rte::cmd_t> cmd) override {
  request_t request;
  request.from_cmd(*cmd);

  std::string err_msg;
  if (!request.validate(&err_msg)) {
    auto result = rte::cmd_result_t::create(RTE_STATUS_CODE_ERROR);
    result->set_property("err_no", 1);
    result->set_property("err_msg", err_msg.c_str());

    rte.return_result(std::move(result), std::move(cmd));
  }
}
```

In the example above, `rte::cmd_result_t::create` is used to create a `cmd_result_t` object with an error code. `result.set_property` is used to set the properties of the `cmd_result_t` object. Finally, `rte.return_result` is called to return the `cmd_result_t` object to the requester.


#### Passing Requests to Downstream Extensions

If an extension needs to send a message to another extension, it can call the `send_cmd()` API. Here is an example:

```cpp
void on_cmd(rte::rte_t &rte, std::unique_ptr<rte::cmd_t> cmd) override {
  request_t request;
  request.from_cmd(*cmd);

  std::string err_msg;
  if (!request.validate(&err_msg)) {
    // ...
  } else {
    rte.send_cmd(std::move(cmd));
  }
}
```

The first parameter in `send_cmd()` is the command of the request, and the second parameter is the handler for the returned `cmd_result_t`. The second parameter can also be omitted, indicating that no special handling is required for the returned result. If the command was originally sent from a higher-level extension, the runtime will automatically return it to the upper-level extension.

Developers can also pass a response handler, like this:

```cpp
rte.send_cmd(
    std::move(cmd),
    [](rte::rte_t &rte, std::unique_ptr<rte::cmd_result_t> result) {
      rte.return_result_directly(std::move(result));
    });
```

In the example above, the `return_result_directly()` method is used in the response handler. You can see that this method differs from `return_result()` in that it does not pass the original command object. This is mainly because:

- For ASTRA message objects (cmd/data/pcm_frame/image_frame), ownership is transferred to the extension in the message callback method, such as `on_cmd()`. This means that once the extension receives the command, the ASTRA runtime will not perform any read/write operations on it. When the extension calls the `send_cmd()` or `return_result()` API, it means that the extension is returning the ownership of the command back to the ASTRA runtime for further processing, such as message delivery. After that, the extension should not perform any read/write operations on the command.
- The `result` in the response handler (i.e., the second parameter of `send_cmd()`) is returned by the downstream extension, and at this point, the result is already bound to the command, meaning that the runtime has the return path information for the result. Therefore, there is no need to pass the command object again.

Of course, developers can also process the result in the response handler.

So far, an example of a simple command processing logic is complete. For other message types such as data, you can refer to the ASTRA API documentation.

## Deploying Locally to an App for Integration Testing

arpm provides the ability to publish to a local registry, allowing you to perform integration testing locally without uploading the extension to the central repository. Unlike GO extensions, for C++ extensions, there are no strict requirements on the app's programming language. It can be GO, C++, or Python.

The deployment process may vary for different apps. The specific steps are as follows:

- Set up the arpm local registry.
- Upload the extension to the local registry.
- Download the app from the central repository (<span class="title-ref">default_app_cpp</span>/<span class="title-ref">default_app_go</span>) for integration testing.
- For C++ apps:
  - Install the <span class="title-ref">first_cxx_extension</span> in the app directory.
  - Compile in the app directory. At this point, both the app and the extension will be compiled into the <span class="title-ref">out/linux/x64/app/default_app_cpp</span> directory.
  - Install the required dependencies in <span class="title-ref">out/linux/x64/app/default_app_cpp</span>. The working directory for testing is the current directory.
- For GO apps:
  - Install the <span class="title-ref">first_cxx_extension</span> in the app directory.
  - Compile in the <span class="title-ref">addon/extension/first_cxx_extension</span> directory, as the GO and C++ compilation toolchains are different.
  - Install the dependencies in the app directory. The working directory for testing is the app directory.
- Configure the graph in the app's <span class="title-ref">manifest.json</span>, specifying the recipient of the message as <span class="title-ref">first_cxx_extension</span>, and send test messages.

### Uploading the Extension to the Local Registry

First, create a temporary <span class="title-ref">config.json</span> file to set up the arpm local registry. For example, the contents of <span class="title-ref">/tmp/code/config.json</span> are as follows:

```json
{
  "registry": [
    "file:///tmp/code/repository"
  ]
}
```

This sets the local directory <span class="title-ref">/tmp/code/repository</span> as the arpm local registry.

<div class="note">

<div class="title">

Note

</div>

- Be careful not to place it in <span class="title-ref">~/.arpm/config.json</span>, as it will affect the subsequent download of dependencies from the central repository.

</div>

Then, in the <span class="title-ref">first_cxx_extension</span> directory, execute the following command to upload the extension to the local registry:

```shell
$ arpm --config-file /tmp/code/config.json publish
```

After the command completes, the uploaded extension can be found in the <span class="title-ref">/tmp/code/repository/extension/first_cxx_extension/0.1.0</span> directory.

### Prepare app for testing (C++)

1. Install <span class="title-ref">default_app_cpp</span> as the test app in an empty directory.

> ``` shell
> $ arpm install app default_app_cpp
> ```
>
> After the command is successfully executed, there will be a directory named <span class="title-ref">default_app_cpp</span> in the current directory.
>
> <div class="note">
>
> <div class="title">
>
> Note
>
> </div>
>
> - When installing an app, its dependencies will be automatically installed.
>
> </div>

2. Install <span class="title-ref">first_cxx_extension</span> that we want to test in the app directory.

> Execute the following command:
>
> ``` shell
> $ arpm --config-file /tmp/code/config.json install extension first_cxx_extension
> ```
>
> After the command is completed, there will be a <span class="title-ref">first_cxx_extension</span> directory in the <span class="title-ref">addon/extension</span> directory.
>
> <div class="note">
>
> <div class="title">
>
> Note
>
> </div>
>
> - It is important to note that since <span class="title-ref">first_cxx_extension</span> is in the local registry, the configuration file path with the local registry specified by <span class="title-ref">--config-file</span> needs to be the same as when publishing.
>
> </div>

3. Add an extension as a message producer.

> <span class="title-ref">first_cxx_extension</span> is expected to receive a <span class="title-ref">hello</span> cmd, so we need a message producer. One way is to add an extension as a message producer. To conveniently generate test messages, an http server can be integrated into the producer's extension.
>
> First, create an http server extension based on <span class="title-ref">default_extension_cpp</span>. Execute the following command in the app directory:
>
> ``` shell
> $ arpm install extension default_extension_cpp --template-mode --template-data package_name=http_server
> ```
>
> The main functionality of the http server is:
> * Start a thread running the http server in the extension's <span class="title-ref">on_start()</span>.
> * Convert incoming requests into ASTRA cmds named <span class="title-ref">hello</span> and send them using <span class="title-ref">send_cmd()</span>.
> * Expect to receive a <span class="title-ref">cmd_result_t</span> response and write its content to the http response.
>
> Here, we use <span class="title-ref">cpp-httplib</span> (<https://github.com/yhirose/cpp-httplib>) as the implementation of the http server.
>
> First, download <span class="title-ref">httplib.h</span> and place it in the <span class="title-ref">include</span> directory of the extension. Then, add the implementation of the http server in <span class="title-ref">src/main.cc</span>. Here is an example code:
>
> ``` C++
> #include "httplib.h"
> #include "nlohmann/json.hpp"
> #include "rte_runtime/binding/cpp/rte.h"
>
> namespace http_server_extension {
>
> class http_server_extension_t : public rte::extension_t {
> public:
>   explicit http_server_extension_t(const std::string &name)
>       : extension_t(name) {}
>
>   void on_start(rte::rte_t &rte) override {
>     rte_proxy = rte::rte_proxy_t::create(rte);
>     srv_thread = std::thread([this] {
>       server.Get("/health",
>                 [](const httplib::Request &req, httplib::Response &res) {
>                   res.set_content("OK", "text/plain");
>                 });
>
>       // Post handler, receive json body.
>       server.Post("/hello", [this](const httplib::Request &req,
>                                   httplib::Response &res) {
>         // Receive json body.
>         auto body = nlohmann::json::parse(req.body);
>         body["rte"]["name"] = "hello";
>
>         auto cmd = rte::cmd_t::create_from_json(body.dump().c_str());
>         auto cmd_shared =
>             std::make_shared<std::unique_ptr<rte::cmd_t>>(std::move(cmd));
>
>         std::condition_variable *cv = new std::condition_variable();
>
>         auto response_body = std::make_shared<std::string>();
>
>         rte_proxy->notify([cmd_shared, response_body, cv](rte::rte_t &rte) {
>           rte.send_cmd(
>               std::move(*cmd_shared),
>               [response_body, cv](rte::rte_t &rte,
>                                   std::unique_ptr<rte::cmd_result_t> result) {
>                 auto err_no = result->get_property_uint8("err_no");
>                 if (err_no > 0) {
>                   auto err_msg = result->get_property_string("err_msg");
>                   response_body->append(err_msg);
>                 } else {
>                   response_body->append("OK");
>                 }
>
>                 cv->notify_one();
>               });
>         });
>
>         std::unique_lock<std::mutex> lk(mtx);
>         cv->wait(lk);
>         delete cv;
>
>         res.set_content(response_body->c_str(), "text/plain");
>       });
>
>       server.listen("0.0.0.0", 8001);
>     });
>
>     rte.on_start_done();
>   }
>
>   void on_stop(rte::rte_t &rte) override {
>     // Extension stop.
>
>     server.stop();
>     srv_thread.join();
>     delete rte_proxy;
>
>     rte.on_stop_done();
>   }
>
> private:
>   httplib::Server server;
>   std::thread srv_thread;
>   rte::rte_proxy_t *rte_proxy{nullptr};
>   std::mutex mtx;
> };
>
> RTE_CPP_REGISTER_ADDON_AS_EXTENSION(http_server, http_server_extension_t);
>
> } // namespace http_server_extension
> ```

Here, a new thread is created in `on_start()` to run the http server because we don't want to block the extension thread. This way, the converted cmd requests are generated and sent from `srv_thread`. In the ASTRA runtime, to ensure thread safety, we use `rte_proxy_t` to pass calls like `send_cmd()` from threads outside the extension thread. 

This code also demonstrates how to clean up external resources in `on_stop()`. For an extension, you should release the `rte_proxy_t` before `on_stop_done()`, which stops the external thread.

1. Configure the graph.

In the app's `manifest.json`, configure `predefined_graph` to specify that the `hello` cmd generated by `http_server` should be sent to `first_cxx_extension`. For example:

>
> ``` json
> "predefined_graphs": [
>   {
>     "name": "testing",
>     "auto_start": true,
>     "nodes": [
>       {
>         "type": "extension_group",
>         "name": "http_thread",
>         "addon": "default_extension_group"
>       },
>       {
>         "type": "extension",
>         "name": "http_server",
>         "addon": "http_server",
>         "extension_group": "http_thread"
>       },
>       {
>         "type": "extension",
>         "name": "first_cxx_extension",
>         "addon": "first_cxx_extension",
>         "extension_group": "http_thread"
>       }
>     ],
>     "connections": [
>       {
>         "extension_group": "http_thread",
>         "extension": "http_server",
>         "cmd": [
>           {
>             "name": "hello",
>             "dest": [
>               {
>                 "extension_group": "http_thread",
>                 "extension": "first_cxx_extension"
>               }
>             ]
>           }
>         ]
>       }
>     ]
>   }
> ]
> ```


5. Compile the app.

> Execute the following commands in the app directory:
>
> ```shell
> $ ag gen linux x64 debug
> $ ag build linux x64 debug
> ```
>
> After the compilation is complete, the compilation output for the app and extension will be generated in the directory <span class="title-ref">out/linux/x64/app/default_app_cpp</span>.
>
> However, it cannot be run directly at this point as it is missing the dependencies of the extension group.

6. Install the extension group.

> Switch to the compilation output directory.
>
> ```shell
> $ cd out/linux/x64/app/default_app_cpp
> ```
>
> Install the extension group.
>
> ```shell
> $ arpm install extension_group default_extension_group
> ```

7. Start the app.

> In the compilation output directory, execute the following command:
>
> ```shell
> $ ./bin/default_app_cpp
> ```
>
> After the app starts, you can now test it by sending messages to the http server. For example, use curl to send a request with an invalid app_id:
>
> ```shell
> $ curl --location 'http://127.0.0.1:8001/hello' \
>   --header 'Content-Type: application/json' \
>   --data '{
>       "app_id": "123",
>       "client_type": 1,
>       "payload": {
>           "err_no": 0
>       }
>   }'
> ```
>
> The expected response should be "invalid app_id".


## Debugging extension in an app

### App (C++)

A C++ app is compiled into an executable file with the correct `rpath` set. Therefore, debugging a C++ app only requires adding the following configuration to `.vscode/launch.json`:

``` json
"configurations": [
  {
      "name": "App (C/C++) (lldb, launch)",
      "type": "lldb",
      "request": "launch",
      "program": "${workspaceFolder}/out/linux/x64/app/default_app_cpp/bin/default_app_cpp",
      "args": [],
      "cwd": "${workspaceFolder}/out/linux/x64/app/default_app_cpp"
  }
  ]
```
