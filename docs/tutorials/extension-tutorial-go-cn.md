# Tutorial - 如何开发 GO extension

## Overview

介绍如何使用 GO 语言开发一个 ASTRA extension, 以及调试和部署到 app
中运行. 本教程包含如下内容:

- 如何使用 arpm 创建一个 GO extension 开发工程.
- 如何使用 ASTRA API 来完成 extension 的功能, 如发送和接收消息.
- 如何要使用 cgo, 该如何配置.
- 如何编写单元测试用例, 如何调试代码.
- 如何在本地将 extension 部署到一个 app 中, 在 app 中做集成测试.
- 如何在 app 中调试 extension 代码.

<div class="note">

<div class="title">

Note

</div>

- 如无特殊说明, 本教程中的命令和代码均在 Linux 环境下执行. 其他平台类似.

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

- 安装 GO 1.20 或以上版本, 推荐最新版本.

  <div class="note">

  <div class="title">

  Note

  </div>

  - ASTRA GO API 会使用到 cgo, 所以请确保默认开启 cgo.
    可以通过如下命令检查:

    ``` shell
    $ go env CGO_ENABLED
    ```

    如果返回 1, 则表示 cgo 默认开启. 否则, 通过如下命令开启 cgo:

    ``` shell
    $ go env -w CGO_ENABLED=1
    ```

  </div>

## 创建 GO extension 工程

GO extension 其实就是一个 go module 工程, 只是为了满足 ASTRA extension
的要求, 需要一些依赖和配置文件. 同时, ASTRA 默认提供了一个 GO extension
的模板工程, 开发者可以通过该模板工程快速创建一个 GO extension 工程.

### 基于模板创建

假设我们要创建的工程名为
<span class="title-ref">first_go_extension</span>, 可通过如下命令创建:

``` shell
$ arpm install extension default_extension_go --template-mode --template-data package_name=first_go_extension
```

<div class="note">

<div class="title">

Note

</div>

上述命令表示以 <span class="title-ref">default_extension_go</span>
为模板, 创建一个名为 <span class="title-ref">first_go_extension</span>
的 extension 工程.

- <span class="title-ref">--template-mode</span> 表示以模板的方式安装
  ASTRA package. 可以通过 <span class="title-ref">--template-data</span>
  指定模板的渲染参数.
- <span class="title-ref">extension</span> 是要安装的 ASTRA package
  类型. 目前 ASTRA 提供的有 app/extension_group/extension/system. 在 app
  中测试 extension 的章节中, 会用到其他几种 package.
- <span class="title-ref">default_extension_go</span> 是 ASTRA
  默认提供的 GO extension. 当然,
  开发者也可以指定商店中的其他可以作为模板使用的 GO extension.

</div>

命令执行完成后, 在当前目录下会生成一个名为
<span class="title-ref">first_go_extension</span> 的目录,
该目录下即是我们的 GO extension 工程. 目录结构如下:

``` text
.
├── default_extension.go
├── go.mod
├── manifest.json
└── property.json
```

其中:

- <span class="title-ref">default_extension.go</span> 中包含了一个简单的
  extension 实现, 其中有调用 ASTRA GO API. 在下一章节会介绍如何使用
  ASTRA API.
- <span class="title-ref">manifest.json</span> 和
  <span class="title-ref">property.json</span> 是 ASTRA extension
  的标准配置文件. 其中, <span class="title-ref">manifest.json</span>
  中一般是用来声明 extension 的版本、依赖等 metadata 信息; 以及 schema
  定义. <span class="title-ref">property.json</span> 中一般是用来声明
  extension 的业务配置.

<span class="title-ref">property.json</span> 默认是空的 json 文件, 如:

``` json
{}
```

<span class="title-ref">manifest.json</span> 默认会包含
<span class="title-ref">rte_runtime_go</span> 依赖, 如:

``` json
{
  "type": "extension",
  "name": "first_go_extension",
  "version": "0.1.0",
  "language": "go",
  "dependencies": [
    {
      "type": "system",
      "name": "rte_runtime_go",
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
  目录下的 <span class="title-ref">manifest.json</span> 和
  <span class="title-ref">property.json</span> 的功能.
- dependencies 中声明当前 extension 的依赖. 在安装 ASTRA package 时,
  arpm 会根据 dependencies 中的声明自动下载依赖包.
- api 是用来声明 extension 的 schema. 参考
  `usage of rte schema <usage_of_rte_schema_cn>`.

</div>

ASTRA GO API 没有发布, 需要通过 arpm 安装到本地. 所以,
<span class="title-ref">go.mod</span> 中是采用了
<span class="title-ref">replace</span> 的方式引入 ASTRA GO API. 如:

``` GO
replace agora.io/rte => ../../../interface
```

在 extension 被安装到 app 中时, 是放置在
<span class="title-ref">addon/extension/</span> 目录下的, 同时, ASTRA GO
API 是被安装在 app 根目录下的, 预期的目录结构如下:

``` text
.
├── addon
│   └── extension
│       └── first_go_extension
│           ├── default_extension.go
│           ├── go.mod
│           ├── manifest.json
│           └── property.json
├── go.mod
├── go.sum
├── interface
│   └── rtego
└── main.go
```

所以, extension go.mod 中的 <span class="title-ref">replace</span>
是指向的 app 目录下的 <span class="title-ref">interface</span> 目录.

### 手动创建

开发者也可以通过 <span class="title-ref">go init</span> 命令创建一个 go
module 工程, 然后参考上述示例创建
<span class="title-ref">manifest.json</span> 和
<span class="title-ref">property.json</span>.

这里暂时不要添加 ASTRA GO API 的依赖, 因为本地还没有需要的
<span class="title-ref">interface</span> 目录, 需要通过
<span class="title-ref">arpm</span> 安装依赖之后才可以添加.

所以, 对于新创建的 go module 或者 已有的 go module 工程, 切换成
extension 工程, 只需要如下步骤:

- 在工程目录下创建 <span class="title-ref">property.json</span>,
  按需添加 extension 的配置.
- 在工程目录下创建 <span class="title-ref">manifest.json</span>, 写明
  <span class="title-ref">type</span>,
  <span class="title-ref">name</span>,
  <span class="title-ref">version</span>,
  <span class="title-ref">language</span>,
  <span class="title-ref">dependencies</span> 等信息. 注意,
  这些信息都是必须的.
  - <span class="title-ref">type</span> 为
    <span class="title-ref">extension</span>.
  - <span class="title-ref">language</span> 为
    <span class="title-ref">go</span>.
  - <span class="title-ref">dependencies</span> 需要添加对
    <span class="title-ref">rte_runtime_go</span> 的依赖.
    按需添加其他依赖.

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
├── default_extension.go
├── go.mod
├── manifest.json
├── property.json
└── .rte
    └── app
        ├── addon
        ├── include
        ├── interface
        └── lib
```

其中: <span class="title-ref">.rte/app/interface</span> 就是 ASTRA GO
API 的module.

所以, 在开发态, extension 的 <span class="title-ref">go.mod</span>
应该改成如下:

``` GO
replace agora.io/rte => ./.rte/app/interface
```

如果是按照上一章节中的 <span class="title-ref">手动创建</span> 的方式,
还需要在 extension 目录下执行如下命令:

``` shell
$ go get agora.io/rte
```

预期应该有如下输出:

``` shell
go: added agora.io/rte v0.0.0-00010101000000-000000000000
```

到目前为止, 一个 ASTRA GO extension 的工程就创建好了.

## Extension 功能实现

对于开发者, 需要做两件事情:

- 创建一个 extension, 作为与 ASTRA runtime 交互的通道.
- 将该 extension 注册为外挂 (在 ASTRA 里被称为 addon),
  以便于通过声明式的方式是 graph 中使用该 extension.

### 创建 extension struct

开发者创建的 extension, 需要实现
<span class="title-ref">rtego.Extension</span> 接口. 该接口定义如下:

``` GO
type Extension interface {
  OnInit(
    rte Rte,
    manifest MetadataInfo,
    property MetadataInfo,
  )
  OnStart(rte Rte)
  OnStop(rte Rte)
  OnDeinit(rte Rte)
  OnCmd(rte Rte, cmd Cmd)
  OnData(rte Rte, data Data)
  OnImageFrame(rte Rte, imageFrame ImageFrame)
  OnPcmFrame(rte Rte, pcmFrame PcmFrame)
}
```

其中, 包括四个生命周期函数和四个消息处理函数:

生命周期函数:

- OnInit: 用于初始化 extension 实例, 比如设置 extension 的配置.
- OnStart: 用于启动 extension 实例, 比如创建对外部服务的连接.
  在启动完成之前, extension 不会收到消息. 同时, 在 OnStart 中,
  就可以通过 <span class="title-ref">rte.GetProperty</span> 相关的 API
  来获取 extension 的配置.
- OnStop: 用于停止 extension 实例, 比如关闭对外部服务的连接.
- OnDeinit: 用于销毁 extension 实例, 比如释放内存资源.

消息处理函数:

- OnCmd/OnData/OnImageFrame/OnPcmFrame:
  是用来接收四种类型的消息的回调函数. ASTRA 的消息类型, 可参考
  `message type and name <message_type_and_name_cn>`.

对于 extension 的实现来说, 可能只关注其中一部分消息类型. 所以,
为了方便开发者实现, ASTRA 提供了一个默认的
<span class="title-ref">DefaultExtension</span>. 这样开发者有两种选择,
一是直接实现 <span class="title-ref">rtego.Extension</span> 接口;
二是内嵌 <span class="title-ref">DefaultExtension</span>, 然后 override
需要的方法.

例如, <span class="title-ref">default_extension_go</span>
模板中就是通过内嵌 <span class="title-ref">DefaultExtension</span>
的方式. 如下:

``` GO
type defaultExtension struct {
  rtego.DefaultExtension
}
```

### 注册 extension

在 extension 定义之后, 就需要将 extension 作为 addon 注册到 ASTRA
runtime 中. 例如, <span class="title-ref">default_extension.go</span>
中的注册代码如下:

``` GO
func init() {
  // Register addon
  rtego.RegisterAddonAsExtension(
    "default_extension_go",
    rtego.NewDefaultExtensionAddon(newDefaultExtension),
  )
}
```

- <span class="title-ref">RegisterAddonAsExtension</span> 是将一个 addon
  对象注册为 ASTRA extension addon 的方法. ASTRA 中的 addon 类型还包括
  extension_group 和 protocol. 在后续集成测试章节会涉及到.
  - 第一个参数是 addon 的名称, 是一个 addon 的唯一标识. 会被用于在 graph
    中通过声明式的方式来定义 extension. 如下:

    ``` json
    {
      "nodes": [
        {
          "type": "extension",
          "name": "extension_go",
          "addon": "default_extension_go",
          "extension_group": "default"
        }
      ]
    }
    ```

    这里的示例, 就是表示使用一个名称为
    <span class="title-ref">default_extension_go</span> 的 addon
    来创建一个 extension 实例, 名称为
    <span class="title-ref">extension_go</span>.

  - 第二个参数是一个 addon 对象. ASTRA 提供了一个简单的方式来创建 --
    <span class="title-ref">NewDefaultExtensionAddon</span>,
    传入的参数是业务 extension 的构造方法. 如:

    ``` GO
    func newDefaultExtension(name string) rtego.Extension {
      return &defaultExtension{}
    }
    ```

<div class="note">

<div class="title">

Note

</div>

- 需要特别注意的是, addon 的名称必须要唯一, 因为在 graph 中, 是将 addon
  的名称作为唯一索引来查找实现的. 这里, 将第一个参数改为
  <span class="title-ref">first_go_extension</span>.

</div>

### OnInit

开发者可以在 OnInit() 设置 extension 的配置, 如下:

``` GO
func (p *defaultExtension) OnInit(rte rtego.Rte, property rtego.MetadataInfo, manifest rtego.MetadataInfo) {
  property.Set(rtego.MetadataTypeJSONFileName, "customized_property.json")
  rte.OnInitDone()
}
```

- <span class="title-ref">property</span> 和
  <span class="title-ref">manifest</span> 都可以通过
  <span class="title-ref">Set()</span> 方法定制配置内容.
  示例中的第一个参数
  <span class="title-ref">rtego.MetadataTypeJSONFileName</span>
  表示自定义的 property 是以本地文件的方式存在的,
  第二个参数即是文件的路径, 是相对于 extension 的目录的. 所以上述示例中,
  在 app 加载 extension 时, 会加载
  <span class="title-ref">\<app\>/addon/extension/first_go_extension/customized_property.json</span>.
- ASTRA OnInit 中提供了加载默认配置的逻辑 -- 如果开发者没有调用
  <span class="title-ref">property.Set()</span>, 则会加载 extension
  目录下的 <span class="title-ref">property.json</span>; 同理,
  如果没有调用 <span class="title-ref">manifest.Set()</span>, 则会加载
  extension 目录下的 <span class="title-ref">manifest.json</span>. 同时,
  如示例, 如果开发者调用了
  <span class="title-ref">property.Set()</span>, 则不会默认加载
  <span class="title-ref">property.json</span> 了.
- OnInit 是异步方法, 开发者需要主动调用
  <span class="title-ref">rte.OnInitDone()</span> 来告知 ASTRA runtime
  预期的 init 完成了.

<div class="note">

<div class="title">

Note

</div>

- 请注意, <span class="title-ref">OnInitDone()</span> 也是异步方法,
  也就是说, 在 <span class="title-ref">OnInitDone()</span> 返回后,
  开发者依然不能使用 <span class="title-ref">rte.GetProperty()</span>
  来获取配置. 对于 extension 来说, 需要等待
  <span class="title-ref">OnStart()</span> 回调方法中才可以.

</div>

### OnStart

在 OnStart 被调用时, 表示 <span class="title-ref">OnInitDone()</span>
已经执行完成, extension 的 property 已经加载完成. 从这个时候开始,
extension 就可以获取配置了. 如下:

``` GO
func (p *defaultExtension) OnStart(rte rtego.Rte) {
  prop, err := rte.GetPropertyString("some_string")

  if err != nil {
    // handle error.
  } else {
    // do something.
  }

  rte.OnStartDone()
}
```

- <span class="title-ref">rte.GetPropertyString()</span>
  是获取一个类型为 string 的 property, property name 是
  <span class="title-ref">some_string</span>. 如果 property 不存在, 或者
  类型不匹配, 会返回一个 error. 如果在 extension 的配置如下:

  ``` json
  {
    "some_string": "hello world"
  }
  ```

  那么, <span class="title-ref">prop</span> 的值就是
  <span class="title-ref">hello world</span>.

- 与 <span class="title-ref">OnInit</span> 一致,
  <span class="title-ref">OnStart</span> 也是异步方法,
  开发者需要主动调用 <span class="title-ref">rte.OnStartDone()</span>
  来告知 ASTRA runtime 预期的 start 完成了.

API 文档参考 `rte api golang <rte_platform_api_golang>`.

### 错误处理

如上一节示例, <span class="title-ref">rte.GetPropertyString()</span>
会返回一个 error. 对于 ASTRA API, error 一般是通过
<span class="title-ref">rtego.RteError</span> 类型返回的. 所以,
可以通过如下的方式来处理 error:

``` GO
func (p *defaultExtension) OnStart(rte rtego.Rte) {
  prop, err := rte.GetPropertyString("some_string")

  if err != nil {
    // handle error.
    var rteErr *rtego.RteError
    if errors.As(err, &rteErr) {
      log.Printf("Failed to get property, cause: %s.\n", rteErr.ErrMsg())
    }
  } else {
    // do something.
  }

  rte.OnStartDone()
}
```

<span class="title-ref">rtego.RteError</span> 提供了
<span class="title-ref">ErrMsg()</span> 方法来获取错误信息; 提供了
<span class="title-ref">ErrNo()</span> 方法来获取错误码.

### 消息处理

ASTRA 提供了四种消息类型, 分别是 <span class="title-ref">Cmd</span>,
<span class="title-ref">Data</span>,
<span class="title-ref">ImageFrame</span>,
<span class="title-ref">PcmFrame</span>. 开发者可以通过实现
<span class="title-ref">OnCmd</span>,
<span class="title-ref">OnData</span>,
<span class="title-ref">OnImageFrame</span>,
<span class="title-ref">OnPcmFrame</span> 回调方法来处理这四种消息.

以 Cmd 为例说明如何接收和发送消息.

假设 <span class="title-ref">first_go_extension</span> 会收到一个
<span class="title-ref">name</span> 为
<span class="title-ref">hello</span> 的 Cmd, 并且其中包含了如下的
property:

| name            | type   |
|-----------------|--------|
| app_id          | string |
| client_type     | int8   |
| payload         | object |
| payload.err_no  | uint8  |
| payload.err_msg | string |

property 列表

<span class="title-ref">first_go_extension</span> 对
<span class="title-ref">hello</span> Cmd 的处理逻辑如下:

- 如果 <span class="title-ref">app_id</span> 或者
  <span class="title-ref">client_type</span> 参数不合法, 则返回错误:

  ``` json
  {
    "err_no": 1001,
    "err_msg": "Invalid argument."
  }
  ```

- 如果 <span class="title-ref">payload.err_no</span> 大于0, 则返回错误,
  错误内容即是 <span class="title-ref">payload</span> 中的内容.

- 如果 <span class="title-ref">payload.err_no</span> 等于0, 则将
  <span class="title-ref">hello</span> Cmd 向后投递, 期望由下游
  extension 处理, 并且在收到下游 extension 的处理结果后, 将结果返回.

#### 在 manifest.json 中描述 extension 的行为

按照上述的描述, <span class="title-ref">first_go_extension</span>
的行为如下:

- 会收到一个 名称为 <span class="title-ref">hello</span> 的 Cmd,
  同时包含 property.
- 可能会发出一个 名称为 <span class="title-ref">hello</span> 的 Cmd,
  同样也包含了 property.
- 会从下游 extension 收到一个响应, 响应中包含了 error 信息.
- 会向上游返回一个响应, 响应中包含 error 信息.

对于 ASTRA extension, 可以在 extension 的 manifest.json
中描述上述的行为, 包括:

- extension 会收到什么消息, 消息的名称, property 的结构定义是什么,
  即定义 schema.
- extension 会产生/发出什么消息, 消息的名称, property 的结构的定义.
- 同时, 对 Cmd 类型的消息, 需要有一个响应的定义 (在 ASTRA 中, 被称为
  Result).

有了这些定义后, ASTRA runtime 在向 extension 投递消息前, 以及 extension
通过 ASTRA runtime 发出消息前, runtime 都会根据 schema
的定义做合法性校验. 同时, 也是方便 extension 的使用者, 可以看到
extension 的协议定义.

schema 是定义在 manifest.json 中的 <span class="title-ref">api</span>
字段中. <span class="title-ref">cmd_in</span> 中定义 extension 要接收的
Cmd; <span class="title-ref">cmd_out</span> 中定义 extension 要发出的
Cmd.

<div class="note">

<div class="title">

Note

</div>

关于 schema 的使用, 参考:
`usage of rte schema <usage_of_rte_schema_cn>`.

</div>

按照上述的描述, <span class="title-ref">first_go_extension</span> 的
manifest.json 的内容如下:

``` json
{
  "type": "extension",
  "name": "first_go_extension",
  "version": "0.1.0",
  "language": "go",
  "dependencies": [
    {
      "type": "system",
      "name": "rte_runtime_go",
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

在 <span class="title-ref">OnCmd</span> 中, 首先要获取到请求的数据, 即
Cmd 中的 property. 我们预期定义一个 Request struct 用来表示请求的数据.
如下:

``` GO
type RequestPayload struct {
  ErrNo  uint8  `json:"err_no"`
  ErrMsg string `json:"err_msg"`
}

type Request struct {
  AppID      string         `json:"app_id"`
  ClientType int8           `json:"client_type"`
  Payload    RequestPayload `json:"payload"`
}
```

对于 Cmd/Data/PcmFrame/ImageFrame 这些 ASTRA message 对象, 都可以设置
property; ASTRA 提供了 property 的 getter/setter 相关的 API.
获取请求数据的逻辑, 就是通过 <span class="title-ref">GetProperty</span>
的 API 来解析 Cmd 中的 property. 如下:

``` GO
func parseRequestFromCmdProperty(cmd rtego.Cmd) (*Request, error) {
  request := &Request{}

  if appID, err := cmd.GetPropertyString("app_id"); err != nil {
    return nil, err
  } else {
    request.AppID = appID
  }

  if clientType, err := cmd.GetPropertyInt8("client_type"); err != nil {
    return nil, err
  } else {
    request.ClientType = clientType
  }

  if payloadBytes, err := cmd.GetPropertyToJSONBytes("payload"); err != nil {
    return nil, err
  } else {
    err := json.Unmarshal(payloadBytes, &request.Payload)

    rtego.ReleaseBytes(payloadBytes)

    if err != nil {
      return nil, err
    }
  }

  return request, nil
}
```

- <span class="title-ref">GetPropertyString()</span>,
  <span class="title-ref">GetPropertyInt8()</span> 是获取指定类型的
  property 的 特例化 API. 即使用
  <span class="title-ref">GetPropertyString()</span> 时, 预期该 property
  的类型是 string, 如果不是, 会返回 error.
- <span class="title-ref">GetPropertyToJSONBytes()</span> 是预期
  property 的值是一个 使用 json <span class="title-ref">序列化</span>
  后的数据. 提供该 API 的目的是 ASTRA runtime 不期望绑定 json 库的实现.
  开发者在获取到 property 的 slice 之后, 可以按需选择 json
  库进行反序列化.
- <span class="title-ref">rtego.ReleaseBytes()</span> 是因为 ASTRA GO
  binding 层提供了 memory pool, 这里只是归还
  <span class="title-ref">payloadBytes</span>.

#### 返回响应

在解析完请求数据后, 我们就可以来实现上述处理流程的第一步 --
如果参数异常, 返回错误响应. 所谓的 <span class="title-ref">响应</span>,
对于 ASTRA 来说, 是通过 <span class="title-ref">CmdResult</span>
来表示的. 所以, 返回响应, 在 ASTRA extension 中就是下面两个步骤:

- 创建一个 <span class="title-ref">CmdResult</span> 对象, 按需设置
  property.
- 将创建的 <span class="title-ref">CmdResult</span> 对象交给 ASTRA
  runtime, 由 runtime 来根据请求方的路径返回.

实现如下:

``` GO
const InvalidArgument uint8 = 1

func (r *Request) validate() error {
  if len(r.AppID) < 64 {
    return errors.New("invalid app_id")
  }

  if r.ClientType != 1 {
    return errors.New("invalid client_type")
  }

  return nil
}

func (p *defaultExtension) OnCmd(
  rte rtego.Rte,
  cmd rtego.Cmd,
) {
  request, err := parseRequestFromCmdProperty(cmd)
  if err == nil {
    err = request.validate()
  }

  if err != nil {
    result, fatal := rtego.NewCmdResult(rtego.Error)
    if fatal != nil {
      log.Fatalf("Failed to create result, %v\n", fatal)
      return
    }

    result.SetProperty("err_no", InvalidArgument)
    result.SetPropertyString("err_msg", err.Error())

    rte.ReturnResult(result, cmd)
  }
}
```

- <span class="title-ref">rtego.NewCmdResult()</span> 用来创建一个
  <span class="title-ref">CmdResult</span> 对象. 第一个参数是 错误码 --
  Ok 或者 Error. 这里的错误码是 ASTRA runtime 内置的, 主要是向 runtime
  说明有没有处理成功. 对于开发者, 也可以通过
  <span class="title-ref">GetStatusCode()</span> 获取该错误码. 当然,
  也可以像示例中的这样, 再定义一个更详细的业务上的错误码.
- <span class="title-ref">result.SetProperty()</span> 是向该
  <span class="title-ref">CmdResult</span> 对象中设置 property. property
  以 key-value 的方式存在.
  <span class="title-ref">SetPropertyString()</span> 是
  <span class="title-ref">SetProperty()</span> 的特例化 API, 提供该 API
  的主要目的是为了减少 GO string 传递时的性能开销.
- <span class="title-ref">rte.ReturnResult()</span> 就是将该
  <span class="title-ref">CmdResult</span> 返回给请求者.
  第一个参数是响应, 第二个参数是请求. ASTRA runtime 会根据请求的路径,
  将响应返回给请求者.

#### 传递请求给下游 extension

如果 extension 要发送消息给其他 extension, 可以调用
<span class="title-ref">SendCmd()</span> API. 如下:

``` GO
func (p *defaultExtension) OnCmd(
  rte rtego.Rte,
  cmd rtego.Cmd,
) {
  // ...

  if err != nil {
    // ...
  } else {
    // Dispatch the request to the upstream.
    rte.SendCmd(cmd, func(r rtego.Rte, result rtego.CmdResult) {
      r.ReturnResultDirectly(result)
    })
  }
}
```

- <span class="title-ref">SendCmd()</span> 中的第一个参数是请求的 cmd,
  第二个参数则是收到下游返回的 <span class="title-ref">CmdResult</span>
  的处理方法. 第二个参数也可以为 nil, 表示不需要特别处理下游返回的结果,
  如果当初传出去的 cmd 是来自于更上游的 extension, 则 runtime
  将会自动的返回到上一级的 extension.
- 在示例中的处理方法中, 使用到了
  <span class="title-ref">ReturnResultDirectly()</span> 方法.
  可以看到该方法与 <span class="title-ref">ReturnResult()</span>
  的差别是少传递了请求的 Cmd 对象. 主要是因为两个方面:
  - 对于 ASTRA 的消息对象 -- Cmd/Data/PcmFrame/ImageFrame, 存在
    ownership 的概念. 即在 extension 的消息回调方法中, 如
    <span class="title-ref">OnCmd()</span>, 是表示 ASTRA runtime 将该
    Cmd 的所有权转移给了 extension; 也就是说, 在 extension 获取到 Cmd
    后, ASTRA runtime 不会对 Cmd 产生读写行为. 同时, 在 extension 调用
    <span class="title-ref">SendCmd()</span> 或者
    <span class="title-ref">ReturnResult()</span> API后, 表示 extension
    将 Cmd 的所有权归还给了 ASTRA runtime, 由 runtime 做后续的处理,
    如消息的投递. 之后, extension 就不该对 Cmd 产生读写行为.
  - response handler (即 SendCmd 的第二个参数) 中的
    <span class="title-ref">result</span> 是由下游返回的, 这时 result
    已经和 Cmd 存在绑定关系, 即 runtime 是有 result 的返回路径信息的.
    所以无需再传递 Cmd 对象.

当然, 开发者在 response handler 中也可以对 result 进行处理.

目前为止, 一个简单的 Cmd 处理逻辑的示例就完成了. 对于 Data
等其他消息类型, 可参考 ASTRA API 文档.

## 本地部署到 app, 集成测试

arpm 提供了 <span class="title-ref">publish</span> 和
<span class="title-ref">local registry</span> 的能力,
所以可以利用这两个功能在不将 extension 上传至中心仓库的情况下,
在本地完成集成测试. 步骤如下:

- 设置 arpm local registry.
- 将 extension 上传至 local registry.
- 从中心仓库下载 <span class="title-ref">default_app_go</span>,
  作为集成测试环境. 并且下载需要的其他依赖.
- 从 local registry 中下载
  <span class="title-ref">first_go_extension</span>.
- 在 <span class="title-ref">default_app_go</span> 中配置 graph,
  指定消息的接收者为 <span class="title-ref">first_go_extension</span>,
  发送测试消息.

### 上传 extension 至 local registry

在上传之前, 需要将
<span class="title-ref">first_go_extension/go.mod</span> 中对 ASTRA GO
binding 的依赖路径还原, 因为需要安装到 app 下了. 如:

``` GO
replace agora.io/rte => ../../../interface
```

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

然后, 在 <span class="title-ref">first_go_extension</span>
目录下执行如下命令, 将 extension 上传至 local registry:

``` shell
$ arpm --config-file /tmp/code/config.json publish
```

执行完成后, 在
<span class="title-ref">/tmp/code/repository/extension/first_go_extension/0.1.0</span>
目录就是上传的 extension.

### 准备测试 app

1.  在一空白目录下, 安装 <span class="title-ref">default_app_go</span>
    作为测试 app.

> ``` shell
> $ arpm install app default_app_go
> ```
>
> 命令执行成功后, 在当前目录下会有一个
> <span class="title-ref">default_app_go</span> 的目录.
>
> <div class="note">
>
> <div class="title">
>
> Note
>
> </div>
>
> - 由于被测 extension 是用 GO 编写的, 目前 app 只能也是 GO 语言的.
>   <span class="title-ref">default_app_go</span> 是 ASTRA 提供的一个 GO
>   app 模板.
> - 在安装 app 时, 其中的依赖会自动安装.
>
> </div>

2.  在 app 目录下, 安装 extension_group.

> 切换到 app 目录下:
>
> ``` shell
> $ cd default_app_go
> ```
>
> 执行如下命令安装 \`default_extension_group\`:
>
> ``` shell
> $ arpm install extension_group default_extension_group
> ```
>
> 执行完成后, 会有一个
> <span class="title-ref">addon/extension_group/default_extension_group</span>
> 目录.
>
> <div class="note">
>
> <div class="title">
>
> Note
>
> </div>
>
> - extension_group 是 ASTRA
>   提供的可以通过声明式的方式来声明物理线程的能力; 同时, 也会声明
>   extension 实例运行在哪个 extension_group 中. 这里的
>   <span class="title-ref">default_extension_group</span> 是 ASTRA
>   提供的默认的 extension_group.
>
> </div>

3.  在 app 目录下, 安装我们要测试的
    <span class="title-ref">first_go_extension</span>.

> 执行如下命令:
>
> ``` shell
> $ arpm --config-file /tmp/code/config.json install extension first_go_extension
> ```
>
> 命令执行完成后, 在 <span class="title-ref">addon/extension</span>
> 目录下会有 <span class="title-ref">first_go_extension</span>.
>
> <div class="note">
>
> <div class="title">
>
> Note
>
> </div>
>
> - 需要注意的是, 因为 first_go_extension 是在 local registry 中, 需要跟
>   publish 时一样, 通过 <span class="title-ref">--config-file</span>
>   指定配置了 local registry 的配置文件路径.
>
> </div>

4.  增加一个 extension, 作为消息的生产者.

> <span class="title-ref">first_go_extension</span> 预期会收到一个
> <span class="title-ref">hello</span> cmd,
> 所以我们需要一个消息的生产者. 一种方式是可以增加一个 extension,
> 作为消息的生产者. 为了方便产生测试消息, 可以在生产者的 extension
> 中集成 http server.
>
> 首先, 可以基于 <span class="title-ref">default_extension_go</span>
> 创建一个 http server extension. 在 app 目录下执行如下命令:
>
> ``` shell
> $ arpm install extension default_extension_go --template-mode --template-data package_name=http_server
> ```
>
> 需要将
> <span class="title-ref">addon/extension/http_server/go.mod</span> 中的
> module 名称改成 <span class="title-ref">http_server</span>.
>
> http server 的主要功能: \* 在 extension 的 OnStart() 中启动一个 http
> server, 以 goroutine 的方式运行. \* 被接收到的请求转换成 ASTRA Cmd,
> 名称为 <span class="title-ref">hello</span>, 然后调用
> <span class="title-ref">SendCmd()</span> 将消息发出. \* 预期会收到一个
> CmdResult 响应, 将其中的内容写入到 http response.
>
> 代码实现如下:
>
> ``` GO
> type defaultExtension struct {
>   rtego.DefaultExtension
>   rte rtego.Rte
>
>   server *http.Server
> }
>
> type RequestPayload struct {
>   ErrNo  uint8  `json:"err_no"`
>   ErrMsg string `json:"err_msg"`
> }
>
> type Request struct {
>   AppID      string         `json:"app_id"`
>   ClientType int8           `json:"client_type"`
>   Payload    RequestPayload `json:"payload"`
> }
>
> func newDefaultExtension(name string) rtego.Extension {
>   return &defaultExtension{}
> }
>
> func (p *defaultExtension) defaultHandler(writer http.ResponseWriter, request *http.Request) {
>   switch request.URL.Path {
>   case "/health":
>     writer.WriteHeader(http.StatusOK)
>   default:
>     resultChan := make(chan rtego.CmdResult, 1)
>
>     var req Request
>     if err := json.NewDecoder(request.Body).Decode(&req); err != nil {
>       writer.WriteHeader(http.StatusBadRequest)
>       writer.Write([]byte("Invalid request body."))
>       return
>     }
>
>     cmd, _ := rtego.NewCmd("hello")
>     cmd.SetPropertyString("app_id", req.AppID)
>     cmd.SetProperty("client_type", req.ClientType)
>
>     payloadBytes, _ := json.Marshal(req.Payload)
>     cmd.SetPropertyFromJSONBytes("payload", payloadBytes)
>
>     p.rte.SendCmd(cmd, func(rte rtego.Rte, result rtego.CmdResult) {
>       resultChan <- result
>     })
>
>     result := <-resultChan
>
>     writer.WriteHeader(http.StatusOK)
>     errNo, _ := result.GetPropertyUint8("err_no")
>
>     if errNo > 0 {
>       errMsg, _ := result.GetPropertyString("err_msg")
>       writer.Write([]byte(errMsg))
>     } else {
>       writer.Write([]byte("OK"))
>     }
>   }
> }
>
> func (p *defaultExtension) OnStart(rte rtego.Rte) {
>   p.rte = rte
>
>   mux := http.NewServeMux()
>   mux.HandleFunc("/", p.defaultHandler)
>
>   p.server = &http.Server{
>     Addr:    ":8001",
>     Handler: mux,
>   }
>
>   go func() {
>     if err := p.server.ListenAndServe(); err != nil {
>       if err != http.ErrServerClosed {
>         panic(err)
>       }
>     }
>   }()
>
>   go func() {
>     // Check if the server is ready.
>     for {
>       resp, err := http.Get("http://127.0.0.1:8001/health")
>       if err != nil {
>         continue
>       }
>
>       defer resp.Body.Close()
>
>       if resp.StatusCode == 200 {
>         break
>       }
>
>       time.Sleep(50 * time.Millisecond)
>     }
>
>     fmt.Println("http server starts.")
>
>     p.rte.OnStartDone()
>   }()
> }
>
> func (p *defaultExtension) OnStop(rte rtego.Rte) {
>   fmt.Println("defaultExtension OnStop")
>
>   if p.server != nil {
>     p.server.Shutdown(context.Background())
>   }
>
>   rte.OnStopDone()
> }
>
> func init() {
>   fmt.Println("defaultExtension init")
>
>   // Register addon
>   rtego.RegisterAddonAsExtension(
>     "http_server",
>     rtego.NewDefaultExtensionAddon(newDefaultExtension),
>   )
> }
> ```

1.  配置 graph.

> 在 app 的 <span class="title-ref">manifest.json</span> 中配置
> <span class="title-ref">predefined_graph</span>, 指定
> <span class="title-ref">http_server</span> 产生的
> <span class="title-ref">hello</span> cmd, 发送给
> <span class="title-ref">first_go_extension</span>. 如:
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
>         "name": "first_go_extension",
>         "addon": "first_go_extension",
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
>                 "extension": "first_go_extension"
>               }
>             ]
>           }
>         ]
>       }
>     ]
>   }
> ]
> ```

6.  编译 app, 并启动.

> 在 app 目录下执行如下命令:
>
> ``` shell
> $ go run scripts/build/main.go
> ```
>
> 编译完成后, 默认会产生 <span class="title-ref">/bin/main</span>
> 可执行文件.
>
> 执行如下命令启动 app:
>
> ``` shell
> $ ./bin/main
> ```
>
> 在控制台输出 <span class="title-ref">http server starts</span>
> 日志信息时, 表示 http 监听端口已正常启动. 这时就可以发送请求测试了.
>
> 比如通过 curl 发送如下请求, 发送一条非法的 app_id 的消息.
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

ASTRA app 的编译是通过 ASTRA 定义的脚本执行的,
其中有关于编译所需的配置的设定. 也就是说, 不能采用直接执行
<span class="title-ref">go build</span> 来编译 ASTRA app. 这样,
就不能通过默认的方式调试 app, 而是要选择
<span class="title-ref">attach</span> 的方式.

比如, 在 vscode 中调试 app 的话, 在
<span class="title-ref">.vscode/launch.json</span> 中添加如下配置:

``` json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "app (golang) (go, attach)",
      "type": "go",
      "request": "attach",
      "mode": "local",
      "processId": 0,
      "stopOnEntry": true
    }
  ]
}
```

首先, 先按照上述方式编译启动 app.

接着, 在 vscode 的 <span class="title-ref">RUN AND DEBUG</span> 窗口选择
<span class="title-ref">app (golang) (go, attach)</span>, 然后点击
<span class="title-ref">Start Debugging</span> 即可.

然后, 在弹出的进程选择窗口查找启动的 app 进程, 就可以进行调试了.

<div class="note">

<div class="title">

Note

</div>

- 在 Linux 环境上, 如果出现 <span class="title-ref">the scope of ptrace
  system call application is limited</span> 的错误,
  可以通过如下方式解决:

  ``` shell
  $ sudo sysctl -w kernel.yama.ptrace_scope=0
  ```

</div>
