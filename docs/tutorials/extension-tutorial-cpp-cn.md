# Tutorial - 如何开发 C++ extension

## Overview

本教程介绍如何使用 C++ 开发一个 ASTRA extension, 以及调试和部署到 ASTRA
app 中运行. 本教程包含如下内容:

- 如何使用 arpm 创建一个 C++ extension 的开发工程.
- 如何使用 ASTRA API 来完成 extension 的功能, 如发送和接收消息.
- 如何编写单元测试用例, 如何调试代码.
- 如何在本地将 extension 部署到一个 app 中, 以及在 app 中做集成测试.
- 如何在 app 中调试 extension 代码.

<div class="note">

<div class="title">

Note

</div>

- 如无特殊说明, 本教程中的命令和代码均在 Linux 环境下执行. 因为 ASTRA
  在所有平台 (例如 Windows, Mac) 有著一致的开发思维与逻辑,
  因此本教程的内容也适合其他平台.

</div>

## 准备工作

- 下载最新的 arpm, 并配置好 PATH. 可通过如下命令检查是否配置成功:

  ``` shell
  $ arpm -h
  ```

  如果配置正常, 会显示 arpm 的帮助信息. 如下:

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

- 下载最新的 standalone_gn, 并配置好 PATH. 例如:

  <div class="note">

  <div class="title">

  Note

  </div>

  standalone_gn 是 ASTRA 平台的 C++ 构建系统. 为了方便开发者使用, ASTRA
  提供了一个 standalone_gn 工具链, 用来构建 C++ extension 工程.

  </div>

  ``` shell
  $ export PATH=/path/to/standalone_gn:$PATH
  ```

  可通过如下命令检查是否配置成功:

  ``` shell
  $ ag -h
  ```

  如果配置正常, 会显示 standalone_gn 的帮助信息. 如下:

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

  - gn 依赖 python3, 请确保 python 3.10 或以上版本已经安装.

  </div>

- 安装 C/C++ 编译器, 选择 clang/clang++ 或者 gcc/g++.

同时, 我们提供了一个基础的编译镜像, 在这个镜像里面,
上述的这些依赖都已经安装并配置完成. 可参考 github 中的
[ASTRA.ai](https://github.com/rte-design/ASTRA.ai) 项目.

## 创建 C++ extension 工程

### 基于模板创建

假设我们要创建的工程名为
<span class="title-ref">first_cxx_extension</span>, 可通过如下命令创建:

``` shell
$ arpm install extension default_extension_cpp --template-mode --template-data package_name=first_cxx_extension
```

<div class="note">

<div class="title">

Note

</div>

上述命令表示以 <span class="title-ref">default_extension_cpp</span>
为模板, 创建一个名为 <span class="title-ref">first_cxx_extension</span>
的 extension 工程.

- <span class="title-ref">--template-mode</span> 表示以模板的方式安装
  ASTRA package. 可以通过 <span class="title-ref">--template-data</span>
  指定模板的渲染参数.
- <span class="title-ref">extension</span> 是要安装的 ASTRA package
  类型. 目前 ASTRA 提供的有 app/extension_group/extension/system.
  在以下的 app 中测试 extension 的章节中, 会用到其他几种 package.
- <span class="title-ref">default_extension_cpp</span> 是 ASTRA
  默认提供的 C++ extension. 当然,
  开发者也可以指定商店中的其他可以用作模板的 C++ extension.

</div>

命令执行完成后, 在当前目录下会生成一个名为
<span class="title-ref">first_cxx_extension</span> 的目录,
该目录即是我们的 C++ extension 工程. 目录结构如下:

``` text
.
├── BUILD.gn
├── manifest.json
├── property.json
└── src
    └── main.cc
```

其中:

- <span class="title-ref">src/main.cc</span> 中包含了一个简单的
  extension 实现, 其中有调用 ASTRA 提供的 C++ API.
  在下一章节会介绍如何使用 ASTRA API.
- <span class="title-ref">manifest.json</span> 和
  <span class="title-ref">property.json</span> 是 ASTRA extension
  的标准配置文件. 其中, <span class="title-ref">manifest.json</span>
  中一般是用来声明 extension 的版本、依赖等 metadata 信息, 以及 schema
  的定义. <span class="title-ref">property.json</span> 则是用来声明
  extension 的业务配置.
- <span class="title-ref">BUILD.gn</span> 是 standalone_gn 的配置文件,
  用来编译 C++ extension 工程.

<span class="title-ref">property.json</span> 默认是空的 json 文件, 如:

``` json
{}
```

<span class="title-ref">manifest.json</span> 默认会包含
<span class="title-ref">rte_runtime</span> 依赖, 如:

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

- 请注意, 根据 ASTRA 的命名规范, <span class="title-ref">name</span>
  需要是 alphanumeric 型态, 因为在将 extension 集成到 app 时, 会根据
  extension name 来创建目录; 同时 ASTRA 会提供默认加载 extension
  目录下的 manifest.json 和 property.json 的功能.
- dependencies 是用来声明 extension 的依赖. 在安装 ASTRA package 时,
  arpm 会根据 dependencies 中的声明自动下载依赖包.
- api 是用来声明 extension 的 schema. 参考
  `usage of rte schema <usage_of_rte_schema_cn>`.

</div>

### 手动创建

开发者也可以手动创建一个 C++ extension 工程; 或者将已有的工程改造成
ASTRA extension 工程.

首先, 需要确保工程的输出目标是 shared library. 然后, 可以参考上述示例,
在工程根目录下创建 <span class="title-ref">property.json</span> 和
<span class="title-ref">manifest.json</span>. 并且
<span class="title-ref">manifest.json</span> 中要包含
<span class="title-ref">type</span>,
<span class="title-ref">name</span>,
<span class="title-ref">version</span>,
<span class="title-ref">language</span>,
<span class="title-ref">dependencies</span> 信息. 其中:

- type 必须是 extension.
- language 必须是 cpp.
- dependencies 中包含 rte_runtime.

最后, 是编译配置. ASTRA 提供的
<span class="title-ref">default_extension_cpp</span> 中使用
<span class="title-ref">standalone_gn</span> 作为构建工具链.
如果开发者使用其他的构建工具链, 可以参考
<span class="title-ref">BUILD.gn</span> 中的配置设置编译参数. 因为
<span class="title-ref">BUILD.gn</span> 中会有 ASTRA package 的目录结构,
所以我们在下一个章节 (下载依赖) 之后再介绍.

## 下载依赖

在 extension 工程目录下执行如下命令, 下载依赖:

``` shell
$ arpm install
```

命令执行成功后, 会在当前目录下生成一个
<span class="title-ref">.rte</span> 目录, 其中是当前 extension
的所有依赖.

<div class="note">

<div class="title">

Note

</div>

- extension 存在 开发态 和 运行态 两种模式. 开发态下, 主体是 extension,
  即根目录是 extension 的源码目录. 运行态下, 根目录是 app 的目录. 所以,
  两种模式下, 依赖的放置路径不一样. 这里的
  <span class="title-ref">.rte</span> 目录即是开发态下的依赖的根目录.

</div>

目录结构如下:

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

其中: \* <span class="title-ref">.rte/app/include</span>
是头文件的根目录. \* <span class="title-ref">.rte/app/lib</span> 是
ASTRA runtime 预编译的动态库的根目录.

如果是 运行态, extension 会被放置在 app 的
<span class="title-ref">addon/extension</span> 目录下; 同时,
动态库会被放置在 app 的 <span class="title-ref">lib</span> 目录下.
结构如下:

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

到目前为止, 一个 ASTRA C++ extension 的工程就创建好了.

## BUILD.gn

<span class="title-ref">default_extension_cpp</span> 的
<span class="title-ref">BUILD.gn</span> 内容如下:

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

首先看下 <span class="title-ref">rte_package</span> target,
这是在声明一个 ASTRA package 的构建目标.

- 这里的 <span class="title-ref">package_kind</span> 是
  <span class="title-ref">extension</span>;
  <span class="title-ref">build_type</span> 是
  <span class="title-ref">shared_library</span>.
  也就是预期的编译输出是一个 shared_library.
- <span class="title-ref">sources</span> 指定了编译的源文件. 所以,
  如果有多个源文件, 需要在 <span class="title-ref">sources</span>
  中添加.
- <span class="title-ref">configs</span> 指定了编译的构建参数.
  这里引用了当前文件定义的 <span class="title-ref">build_config</span>.

接着看下 <span class="title-ref">build_config</span> 的内容.

- <span class="title-ref">include_dirs</span> 是在定义头文件的搜索路径.
  - <span class="title-ref">include</span> 和
    <span class="title-ref">//include</span> 的区别是,
    <span class="title-ref">include</span> 是指当前 extension 目录下的
    <span class="title-ref">include</span> 目录. 而
    <span class="title-ref">//include</span> 是根据 执行编译命令 (即 ag
    gen ...) 的工作目录来定的. 所以, 如果在 extension 下执行编译, 就是
    extension 下的, 即与 <span class="title-ref">include</span> 一样.
    但如果在 app 下编译, 就是 app 下的
    <span class="title-ref">include</span> 目录了.
  - <span class="title-ref">.rte/app/include</span> 是为了在 extension
    单独开发编译场景下使用的, 也就是本教程正在介绍的场景. 也就是, 默认的
    <span class="title-ref">build_config</span> 中可以兼容
    开发态和运行态 的编译.
- <span class="title-ref">lib_dirs</span> 是依赖库的搜索路径.
  <span class="title-ref">lib</span> 和
  <span class="title-ref">//lib</span> 的区别与
  <span class="title-ref">include</span> 类似.
- <span class="title-ref">libs</span> 是在定义依赖的库.
  <span class="title-ref">rte_runtime</span> 和
  <span class="title-ref">utils</span> 是 ASTRA 提供的库.

所以, 如果开发者使用其他的构建工具链, 可以参考上述的配置,
将编译参数设置到自己的构建工具链中. 如使用 g++ 编译:

``` shell
$ g++ -shared -fPIC -I.rte/app/include/ -L.rte/app/lib -lrte_runtime -lutils -Wl,-rpath=\$ORIGIN -Wl,-rpath=\$ORIGIN/../../../lib src/main.cc
```

这里 <span class="title-ref">rpath</span> 的设置也是考虑到 运行态 时,
extension 所依赖的 rte_runtime 是放置在
<span class="title-ref">app/lib</span> 目录下的.

## Extension 功能实现

对于开发者, 需要做两件事情:

- 创建一个 extension, 作为与 ASTRA runtime 交互的通道.
- 将该 extension 注册为 ASTRA 的外挂 (在 ASTRA 里被称为 addon),
  以便于通过声明式的方式在 graph 中使用该 extension.

### 创建 extension class

开发者创建的 extension, 需要继承
<span class="title-ref">rte::extension_t</span> 类. 该类的主要定义如下:

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

  // Use std::shared_ptr to enable the C++ extension to save the received C++
  // messages and use it later. And use 'const shared_ptr&' to indicate that
  // the C++ extension "might" take a copy and share ownership of the cmd.

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

其中, 包括四个生命周期函数和四个消息处理函数:

生命周期函数:

- on_init: 用于初始化 extension 实例, 比如设置 extension 的配置.
- on_start: 用于启动 extension 实例, 比如创建对外部服务的连接. 在
  <span class="title-ref">on_start</span> 完成之前, extension
  不会收到消息. 同时, 在 <span class="title-ref">on_start</span> 中,
  就可以通过 <span class="title-ref">rte.get_property</span> 相关的 API
  来获取 extension 的配置.
- on_stop: 用于停止 extension 实例, 比如关闭对外部服务的连接.
- on_deinit: 用于销毁 extension 实例, 比如释放内存资源.

消息处理函数:

- on_cmd/on_data/on_pcm_frame/on_image_frame:
  是用来接收四种类型的消息的回调函数. ASTRA 的消息类型, 可参考
  `message type and name <message_type_and_name_cn>`.

<span class="title-ref">rte::extension_t</span> 中提供了默认的实现,
开发者可以根据自己的需求来 override 这些方法.

### 注册 extension

在 extension 定义之后, 就需要将 extension 作为 addon 注册到 ASTRA
runtime 中. 例如,
<span class="title-ref">first_cxx_extension/src/main.cc</span>
中的注册代码如下:

``` C++
RTE_CPP_REGISTER_ADDON_AS_EXTENSION(first_cxx_extension, first_cxx_extension_extension_t);
```

- <span class="title-ref">RTE_CPP_REGISTER_ADDON_AS_EXTENSION</span> 是
  ASTRA runtime 提供的一个默认注册 extension addon 的宏定义.
  - 第一个参数是 addon 的名称, 是一个 addon 的唯一标识. 会被用于在 graph
    中通过声明式的方式来定义 extension. 如下:

    ``` json
    {
      "nodes": [
        {
          "type": "extension",
          "name": "extension_cxx",
          "addon": "first_cxx_extension",
          "extension_group": "default"
        }
      ]
    }
    ```

    这里的示例, 就是表示使用一个名称为
    <span class="title-ref">first_cxx_extension</span> 的 addon
    来创建一个 extension 实例, 名称为
    <span class="title-ref">extension_cxx</span>.

  - 第二个参数是 extension 的实现类. 即继承了
    <span class="title-ref">rte::extension_t</span> 的类名.

<div class="note">

<div class="title">

Note

</div>

- 需要特别注意的是, addon 的名称必须要唯一, 因为在 graph 中, 是将 addon
  的名称作为唯一索引来查找实现的.

</div>

### on_init

开发者可以在 on_init() 设置 extension 的配置, 如下:

``` C++
void on_init(rte::rte_t& rte, rte::metadata_info_t& manifest,
             rte::metadata_info_t& property) override {
  property.set(RTE_METADATA_JSON_FILENAME, "customized_property.json");
  rte.on_init_done(manifest, property);
}
```

- <span class="title-ref">property</span> 和
  <span class="title-ref">manifest</span> 都可以通过
  <span class="title-ref">set()</span> 方法定制配置内容.
  示例中的第一个参数
  <span class="title-ref">RTE_METADATA_JSON_FILENAME</span> 表示自定义的
  property 是以本地文件的方式存在的, 第二个参数即是文件的路径, 是相对于
  extension 的目录的. 所以上述示例中, 在 app 加载 extension 时, 会加载
  <span class="title-ref">\<app\>/addon/extension/first_cxx_extension/customized_property.json</span>.
- ASTRA <span class="title-ref">on_init</span>
  中提供了加载默认配置的逻辑, 如果开发者没有调用
  <span class="title-ref">property.set()</span>, 则会加载 extension
  目录下的 <span class="title-ref">property.json</span>; 同理,
  如果没有调用 <span class="title-ref">manifest.set()</span>, 则会加载
  extension 目录下的 <span class="title-ref">manifest.json</span>. 同时,
  如示例, 如果开发者调用了
  <span class="title-ref">property.set()</span>, 则不会默认加载
  <span class="title-ref">property.json</span> 了.
- <span class="title-ref">on_init</span> 是异步方法, 开发者需要主动调用
  <span class="title-ref">rte.on_init_done()</span> 来告知 ASTRA runtime
  预期的 <span class="title-ref">on_init</span> 完成了.

<div class="note">

<div class="title">

Note

</div>

- 请注意, <span class="title-ref">on_init_done()</span> 也是异步方法,
  也就是说, 在 <span class="title-ref">on_init_done()</span> 返回后,
  开发者依然不能使用 <span class="title-ref">rte.get_property()</span>
  来获取配置. 对于 extension 来说, 需要等待
  <span class="title-ref">on_start()</span> 回调方法中才可以.

</div>

### on_start

在 <span class="title-ref">on_start</span> 被调用时, 表示
<span class="title-ref">on_init_done()</span> 已经执行完成, extension 的
property 已经加载完成. 从这个时候开始, extension 就可以获取配置了. 如下:

``` C++
void on_start(rte::rte_t& rte) override {
  auto prop = rte.get_property_string("some_string");
  // do something

  rte.on_start_done();
}
```

- <span class="title-ref">rte.get_property_string()</span>
  是获取一个类型为 string 的 property, property name 是
  <span class="title-ref">some_string</span>. 如果 property 不存在, 或者
  类型不匹配, 会返回一个 error. 如果在 extension 的配置如下内容:

  ``` json
  {
    "some_string": "hello world"
  }
  ```

  那么, <span class="title-ref">prop</span> 的值就是
  <span class="title-ref">hello world</span>.

- 与 <span class="title-ref">on_init</span> 一致,
  <span class="title-ref">on_start</span> 也是异步方法,
  开发者需要主动调用 <span class="title-ref">rte.on_start_done()</span>
  来告知 ASTRA runtime 预期的 <span class="title-ref">on_start</span>
  完成了.

API 文档参考 `rte api doc <rte_platform_api_detail>`.

### 错误处理

如上一节示例, 如果 <span class="title-ref">some_string</span>
不存在或者类型不是 string,
<span class="title-ref">rte.get_property_string()</span> 会返回一个
error. 可以通过如下的方式来处理 error:

``` C++
void on_start(rte::rte_t& rte) override {
  rte::error_t err;
  auto prop = rte.get_property_string("some_string", &err);

  // error handling
  if (!err.is_success()) {
    RTE_LOGE("Failed to get property: %s", err.errmsg());
  }

  rte.on_start_done();
}
```

### 消息处理

ASTRA 提供了四种消息类型, 分别是 <span class="title-ref">cmd</span>,
<span class="title-ref">data</span>,
<span class="title-ref">image_frame</span>,
<span class="title-ref">pcm_frame</span>. 开发者可以通过实现
<span class="title-ref">on_cmd</span>,
<span class="title-ref">on_data</span>,
<span class="title-ref">on_image_frame</span>,
<span class="title-ref">on_pcm_frame</span> 回调方法来处理这四种消息.

以 cmd 为例说明如何接收和发送消息.

假设 <span class="title-ref">first_cxx_extension</span> 会收到一个
<span class="title-ref">name</span> 为
<span class="title-ref">hello</span> 的 cmd, 并且其中包含了如下的
property:

| name            | type   |
|-----------------|--------|
| app_id          | string |
| client_type     | int8   |
| payload         | object |
| payload.err_no  | uint8  |
| payload.err_msg | string |

property 列表

<span class="title-ref">first_cxx_extension</span> 对
<span class="title-ref">hello</span> cmd 的处理逻辑如下:

- 如果 <span class="title-ref">app_id</span> 或者
  <span class="title-ref">client_type</span> 参数不合法, 则返回错误:

  ``` json
  {
    "err_no": 1001,
    "err_msg": "Invalid argument."
  }
  ```

- 如果 <span class="title-ref">payload.err_no</span> 大于 0, 则返回错误,
  错误内容即是 <span class="title-ref">payload</span> 中的内容.

- 如果 <span class="title-ref">payload.err_no</span> 等于 0, 则将
  <span class="title-ref">hello</span> cmd 向后投递, 期望由下游
  extension 处理, 并且在收到下游 extension 的处理结果后, 将结果返回.

#### 在 manifest.json 中描述 extension 的行为

按照上述的描述, <span class="title-ref">first_cxx_extension</span>
的行为如下:

- 会收到一个 名称为 <span class="title-ref">hello</span> 的 cmd,
  同时包含 property.
- 可能会发出一个 名称为 <span class="title-ref">hello</span> 的 cmd,
  同样也包含了 property.
- 会从下游 extension 收到一个响应, 响应中包含了 error 信息.
- 会向上游返回一个响应, 响应中包含 error 信息.

对于 ASTRA extension, 可以在 extension 的
<span class="title-ref">manifest.json</span> 中描述上述的行为, 包括:

- extension 会收到什么消息, 消息的名称, property 的结构定义是什么,
  即定义 schema.
- extension 会产生/发出什么消息, 消息的名称, property 的结构的定义.
- 同时, 对 cmd 类型的消息, 需要有一个响应的定义 (在 ASTRA 中, 被称为
  result).

有了这些定义后, ASTRA runtime 在向 extension 投递消息前, 以及 extension
通过 ASTRA runtime 发出消息前, runtime 都会根据 schema
的定义做合法性校验. 同时, 也是方便 extension 的使用者, 可以看到
extension 的协议定义.

schema 是定义在 <span class="title-ref">manifest.json</span> 中的
<span class="title-ref">api</span> 字段.
<span class="title-ref">cmd_in</span> 中定义 extension 要接收的 cmd;
<span class="title-ref">cmd_out</span> 中定义 extension 要发出的 cmd.

<div class="note">

<div class="title">

Note

</div>

关于 schema 的使用, 参考:
`usage of rte schema <usage_of_rte_schema_cn>`.

</div>

按照上述的描述, <span class="title-ref">first_cxx_extension</span> 的
<span class="title-ref">manifest.json</span> 的内容如下:

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

#### 获取请求数据

在 <span class="title-ref">on_cmd</span> 中, 首先要获取到请求的数据, 即
cmd 中的 property. 我们预期定义一个 request_t 类用来表示请求的数据.

在 extension 工程目录下创建 <span class="title-ref">include</span> 目录,
在其中创建 <span class="title-ref">model.h</span> 文件, 内容如下:

``` C++
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

- 如上所述, 在 <span class="title-ref">BUILD.gn</span> 中, 已经默认将
  extension 的 <span class="title-ref">include</span>
  目录加入到头文件的搜索路径中了. 所以, 将新建的
  <span class="title-ref">model.h</span> 放置在
  <span class="title-ref">include</span> 目录下, 这样就可以直接在
  extension 代码中引用了.
- 这里采用 nlohmann json 库来做反序列化.

接着, 实现 <span class="title-ref">from_json</span> 方法, 用来将 json
数据反序列化为 request_t 对象. 在 <span class="title-ref">src</span>
目录下创建 <span class="title-ref">model.cc</span> 文件, 内容如下:

``` C++
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

这里增加了一个源文件, 我们需要将其添加到
<span class="title-ref">BUILD.gn</span> 中的
<span class="title-ref">sources</span> 列表中, 这样在编译 extension
时才能将其编译进去. 如:

``` python
sources = [ "src/main.cc", "src/model.cc" ]
```

<div class="note">

<div class="title">

Note

</div>

- <span class="title-ref">BUILD.gn</span> 中的
  <span class="title-ref">sources</span> 还有一个作用,
  就是增量编译的文件变更监听列表. 当
  <span class="title-ref">sources</span> 中的文件被编辑后, 在执行
  <span class="title-ref">ag build ...</span> 时,
  只会增量编译变化的源文件.

</div>

对于 cmd/data/pcm_frame/image_frame 这些 ASTRA message 对象, 都可以设置
property; ASTRA 提供了 property 的 getter/setter 相关的 API.
获取请求数据的逻辑, 就是通过 get_property 的 API 来解析 cmd 中的
property. 如下:

``` C++
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

- <span class="title-ref">get_property_string()</span>,
  <span class="title-ref">get_property_int8()</span> 是获取指定类型的
  property 的特例化 API. 也就是, 使用
  <span class="title-ref">get_property_string()</span> 时, 预期该
  property 的类型是 string, 如果不是, 会返回 error.
- <span class="title-ref">get_property_to_json()</span> 返回的是一个
  json string, 是把 property 的值做 json
  <span class="title-ref">序列化</span> 后的数据. 该 API 返回的是 string
  的目的是 ASTRA runtime 不期望绑定任何一个 json 库的实现.
  开发者在获取到 json string 之后, 可以按需选择 json 库进行反序列化.
  这里使用的是 nlohmann json 库.

#### 返回响应

在解析完请求数据后, 我们就可以来实现上述处理流程的第一步, 如果参数异常,
返回错误响应. 所谓的 <span class="title-ref">响应</span>, 对于 ASTRA
来说, 是通过 <span class="title-ref">cmd_result_t</span> 来表示的. 所以,
返回响应, 在 ASTRA extension 中就是下面两个步骤:

- 创建一个 <span class="title-ref">cmd_result_t</span> 对象, 按需设置
  property.
- 将创建的 <span class="title-ref">cmd_result_t</span> 对象交给 ASTRA
  runtime, 由 runtime 返回给请求方.

实现如下:

``` C++
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

- <span class="title-ref">rte::cmd_result_t::create</span> 用来创建一个
  <span class="title-ref">cmd_result_t</span> 对象. 第一个参数是 错误码,
  可能的值有 <span class="title-ref">RTE_STATUS_CODE_OK</span> 或者
  <span class="title-ref">RTE_STATUS_CODE_ERROR</span>. 这里的错误码是
  ASTRA runtime 内置的, 主要是向 runtime 说明有没有处理成功. 对于开发者,
  也可以通过 <span class="title-ref">get_status_code()</span>
  获取该错误码. 当然, 也可以像示例中的这样,
  再定义一个更详细的业务上的错误码.
- <span class="title-ref">result.set_property()</span> 是向该
  <span class="title-ref">cmd_result_t</span> 对象中设置 property.
  property 以 key-value 的方式存在.
- <span class="title-ref">rte.return_result()</span> 就是将该
  <span class="title-ref">cmd_result_t</span> 返回给请求者.
  第一个参数是响应, 第二个参数是请求. ASTRA runtime
  会根据该请求所携带的资讯, 将响应返回给请求者.

#### 传递请求给下游 extension

如果 extension 要发送消息给其他 extension, 可以调用
<span class="title-ref">send_cmd()</span> API. 如下:

``` C++
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

- <span class="title-ref">send_cmd()</span> 中的第一个参数是请求的 cmd,
  第二个参数则是收到下游返回的
  <span class="title-ref">cmd_result_t</span> 的处理方法.
  第二个参数也可以不传, 表示不需要特别处理下游返回的结果,
  如果当初传出去的 cmd 是来自于更上游的 extension, 则 runtime
  将会自动的返回到上一级的 extension.

开发者也可以传入 response handler, 如下:

``` C++
rte.send_cmd(
    std::move(cmd),
    [](rte::rte_t &rte, std::unique_ptr<rte::cmd_result_t> result) {
      rte.return_result_directly(std::move(result));
    });
```

- 在示例中的处理方法中, 使用到了
  <span class="title-ref">return_result_directly()</span> 方法.
  可以看到该方法与 <span class="title-ref">return_result()</span>
  的差别是少传递了请求的 cmd_t 对象. 主要是因为两个方面:
  - 对于 ASTRA 的消息对象 -- cmd/data/pcm_frame/image_frame, 存在
    ownership 的概念. 即在 extension 的消息回调方法中, 如
    <span class="title-ref">on_cmd()</span>, 是表示 ASTRA runtime 将该
    cmd 的所有权转移给了 extension; 也就是说, 在 extension 获取到 cmd
    后, ASTRA runtime 不会对 cmd 产生读写行为. 同时, 在 extension 调用
    <span class="title-ref">send_cmd()</span> 或者
    <span class="title-ref">return_result()</span> API后, 表示 extension
    将 cmd 的所有权归还给了 ASTRA runtime, 由 runtime 做后续的处理,
    如消息的投递. 之后, extension 就不该对 cmd 产生读写行为.
  - response handler (即 send_cmd 的第二个参数) 中的
    <span class="title-ref">result</span> 是由下游返回的, 这时 result
    已经和 cmd 存在绑定关系, 即 runtime 是有 result 的返回路径信息的.
    所以无需再传递 cmd 对象.

当然, 开发者在 response handler 中也可以对 result 进行处理.

目前为止, 一个简单的 cmd 处理逻辑的示例就完成了. 对于 data
等其他消息类型, 可参考 ASTRA API 文档.

## 本地部署到 app, 集成测试

arpm 提供了 <span class="title-ref">publish</span> 到 local registry
的能力, 所以可以利用这两个功能在不将 extension 上传至中心仓库的情况下,
在本地完成集成测试. 不像 GO extension, 对于 C++ extension 来说, 对 app
的开发语言就没有强要求. 可以是 GO, C++ 或者 Python.

对于不同的 app, 部署的流程有些差异, 具体步骤如下:

- 设置 arpm local registry.
- 将 extension 上传至 local registry.
- 从中心仓库下载 app (<span class="title-ref">default_app_cpp</span>/
  <span class="title-ref">default_app_go</span>), 作为集成测试环境.
- 对于 C++ app:
  - 在 app 目录下安装
    <span class="title-ref">first_cxx_extension</span>.
  - 在 app 目录下执行编译. 此时, app 和 extension 都会被编译到
    <span class="title-ref">out/linux/x64/app/default_app_cpp</span>
    目录下.
  - 这时, 需要在
    <span class="title-ref">out/linux/x64/app/default_app_cpp</span>
    安装需要的依赖. 同时测试的工作目录是在当前目录下.
- 对于 GO app:
  - 在 app 目录下安装
    <span class="title-ref">first_cxx_extension</span>.
  - 需要到
    <span class="title-ref">addon/extension/first_cxx_extension</span>
    目录下执行编译. 因为 GO 和 C++ 的编译工具链不同.
  - 在 app 目录下安装依赖. 同时测试的工作目录是 app 目录.
- 在 app 的 <span class="title-ref">manifest.json</span> 中配置 graph,
  指定消息的接收者为 <span class="title-ref">first_cxx_extension</span>,
  发送测试消息.

### 上传 extension 至 local registry

首先, 创建一个临时的 <span class="title-ref">config.json</span>,
用于设置 arpm 的 local registry. 比如
<span class="title-ref">/tmp/code/config.json</span> 的内容如下:

``` json
{
  "registry": [
    "file:///tmp/code/repository"
  ]
}
```

即将本地目录 <span class="title-ref">/tmp/code/repository</span> 设置为
arpm 的 local registry.

<div class="note">

<div class="title">

Note

</div>

- 注意不能放置在 <span class="title-ref">~/.arpm/config.json</span> 中,
  否则会影响后续从中心仓库下载依赖.

</div>

然后, 在 <span class="title-ref">first_cxx_extension</span>
目录下执行如下命令, 将 extension 上传至 local registry:

``` shell
$ arpm --config-file /tmp/code/config.json publish
```

执行完成后, 在
<span class="title-ref">/tmp/code/repository/extension/first_cxx_extension/0.1.0</span>
目录就是上传的 extension.

### 准备测试 app (C++)

1.  在一空白目录下, 安装 <span class="title-ref">default_app_cpp</span>
    作为测试 app.

> ``` shell
> $ arpm install app default_app_cpp
> ```
>
> 命令执行成功后, 在当前目录下会有一个
> <span class="title-ref">default_app_cpp</span> 的目录.
>
> <div class="note">
>
> <div class="title">
>
> Note
>
> </div>
>
> - 在安装 app 时, 其中的依赖会自动安装.
>
> </div>

2.  在 app 目录下, 安装我们要测试的
    <span class="title-ref">first_cxx_extension</span>.

> 执行如下命令:
>
> ``` shell
> $ arpm --config-file /tmp/code/config.json install extension first_cxx_extension
> ```
>
> 命令执行完成后, 在 <span class="title-ref">addon/extension</span>
> 目录下会有 <span class="title-ref">first_cxx_extension</span>.
>
> <div class="note">
>
> <div class="title">
>
> Note
>
> </div>
>
> - 需要注意的是, 因为
>   <span class="title-ref">first_cxx_extension</span> 是在 local
>   registry 中, 需要跟 publish 时一样, 通过
>   <span class="title-ref">--config-file</span> 指定配置了 local
>   registry 的配置文件路径.
>
> </div>

3.  增加一个 extension, 作为消息的生产者.

> <span class="title-ref">first_cxx_extension</span> 预期会收到一个
> <span class="title-ref">hello</span> cmd,
> 所以我们需要一个消息的生产者. 一种方式是可以增加一个 extension,
> 作为消息的生产者. 为了方便产生测试消息, 可以在生产者的 extension
> 中集成 http server.
>
> 首先, 可以基于 <span class="title-ref">default_extension_cpp</span>
> 创建一个 http server extension. 在 app 目录下执行如下命令:
>
> ``` shell
> $ arpm install extension default_extension_cpp --template-mode --template-data package_name=http_server
> ```
>
> http server 的主要功能: \* 在 extension 的
> <span class="title-ref">on_start()</span> 中启动一个线程, 运行 http
> server. \* 被接收到的请求转换成 ASTRA cmd, 名称为
> <span class="title-ref">hello</span>, 然后调用
> <span class="title-ref">send_cmd()</span> 将消息发出. \*
> 预期会收到一个 <span class="title-ref">cmd_result_t</span> 响应,
> 将其中的内容写入到 http response.
>
> 这里选用 <span class="title-ref">cpp-httplib</span>
> (<https://github.com/yhirose/cpp-httplib>) 作为 http server 的实现.
>
> 首先, 将 <span class="title-ref">httplib.h</span> 下载至 extension 的
> <span class="title-ref">include</span> 目录下. 然后, 在
> <span class="title-ref">src/main.cc</span> 下增加 http server 的实现.
> 示例代码如下:
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
>
> 这里在 <span class="title-ref">on_start()</span> 中创建了一个新的线程,
> 来运行 http server, 因为不能阻塞 extension thread. 这样的话,
> 请求转换的 cmd 就是从 <span class="title-ref">srv_thread</span>
> 产生并发送的了. 在 ASTRA runtime 中, 为了保证线程安全, 提供了
> <span class="title-ref">rte_proxy_t</span>, 即如果有需要在 extension
> thread 之外的线程调用 <span class="title-ref">send_cmd()</span>
> 等方法, 需要通过 <span class="title-ref">rte_proxy_t::notify()</span>
> 传递.
>
> 这里也展示了如何在 <span class="title-ref">on_stop()</span>
> 中销毁外部资源. 对于 extension 来说, 应该在
> <span class="title-ref">on_stop_done()</span> 之前将
> <span class="title-ref">rte_proxy_t</span> 释放, 即停止外部线程.

1.  配置 graph.

> 在 app 的 <span class="title-ref">manifest.json</span> 中配置
> <span class="title-ref">predefined_graph</span>, 指定
> <span class="title-ref">http_server</span> 产生的
> <span class="title-ref">hello</span> cmd, 发送给
> <span class="title-ref">first_cxx_extension</span>. 如:
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

5.  编译 app.

> 在 app 目录下执行如下命令:
>
> ``` shell
> $ ag gen linux x64 debug
> $ ag build linux x64 debug
> ```
>
> 编译完成后, 在
> <span class="title-ref">out/linux/x64/app/default_app_cpp</span>
> 目录下会产生 app 和 extension 的编译输出.
>
> 这时, 还不能直接运行, 还缺少 extension_group 的依赖.

6.  安装 extension group.

> 需要切换到编译输出目录下.
>
> ``` shell
> $ cd out/linux/x64/app/default_app_cpp
> ```
>
> 安装 extension_group.
>
> ``` shell
> $ arpm install extension_group default_extension_group
> ```

7.  启动 app

> 在编译输出目录下, 执行如下命令:
>
> ``` shell
> $ ./bin/default_app_cpp
> ```
>
> 启动完成后, 这时就可以像 http server 发送消息测试了. 比如通过 curl
> 发送如下请求, 发送一条非法的 app_id 的消息.
>
> ``` shell
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
> 预期会返回 <span class="title-ref">invalid app_id</span> 的响应信息.

## 在 app 中调试 extension

### app (C++)

C++ app 是编译输出为一个可执行文件, 并且
<span class="title-ref">rpath</span> 设置好了. 所以 C++ app 的调试只需在
<span class="title-ref">.vscode/launch.json</span> 中增加如下配置即可:

``` json
"configurations": [
      {
          "name": "app (C/C++) (lldb, launch)",
          "type": "lldb",
          "request": "launch",
          "program": "${workspaceFolder}/out/linux/x64/app/default_app_cpp/bin/default_app_cpp",
          "args": [],
          "cwd": "${workspaceFolder}/out/linux/x64/app/default_app_cpp"
      }
  ]
```
