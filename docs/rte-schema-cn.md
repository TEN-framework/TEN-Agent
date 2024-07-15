# Usage - RTE Schema (简体中文)

## Overview

<span class="title-ref">RTE Schema</span> 提供用于描述
<span class="title-ref">RTE Value</span> 的数据结构.
<span class="title-ref">RTE Value</span> 是 RTE Runtime 中用于存储
property 等信息的结构化数据类型. <span class="title-ref">RTE
Schema</span> 可用在定义 Extension 的配置文件的数据结构; 同时,
也可以用于定义 Extension 的 接收 和 发出 的消息的数据结构.

最常见的应用场景, 比如有两个 Extension --- A 和 B; A 会向 B 发送 cmd.
这个场景下, 会有如下涉及到定义 RTE Schema 的地方:

- Extension A 的配置文件.
- Extension B 的配置文件.
- A 作为生产者发出的 cmd 中携带的消息的数据结构.
- B 作为消费者接收的 cmd 中携带的消息的数据结构.

## 配置文件

RTE Extension 默认会有两个配置文件:

- property.json: 主要是 Extension 自身的业务配置, 如:

  ``` json
  {
    "app_id": "123456",
    "channel": "test",
    "log": {
      "level": 1,
      "redirect_stdout": true,
      "file": "api.log"
    }
  }
  ```

- manifest.json: 主要是 Extension 的不可变信息, 包括 Extension 的元数据
  (type, name, version 等), schema 定义等. 如:

  ``` json
  {
    "type": "extension",
    "name": "A",
    "version": "1.0.0",
    "language": "cpp",
    "dependencies": [],
    "api": {}
  }
  ```

开发者可以在 <span class="title-ref">Extension::on_init()</span>
中自定义加载配置文件的逻辑. 默认情况下, RTE Extension 会自动加载目录下的
<span class="title-ref">property.json</span> 和
<span class="title-ref">manifest.json</span>. 在
<span class="title-ref">Extension::on_start()</span> 回调触发之后,
开发者就可以通过 <span class="title-ref">rte::get_property()</span> 获取
<span class="title-ref">property.json</span> 中的内容. 如:

``` cpp
void on_init(rte::rte_t &rte, rte::metadata_info_t &manifest,
             rte::metadata_info_t &property) override {
  // 可以通过如下方式加载自定义配置文件. 在这种情况下, 默认的 property.json 就不会被加载
  // 了.
  // property.set(RTE_METADATA_JSON_FILENAME, "a.json");

  rte.on_init_done(manifest, property);
}
```

在 <span class="title-ref">rte.on_init_done()</span> 触发后,
<span class="title-ref">property.json</span> 的内容就会被以
<span class="title-ref">RTE Value</span> 的形式存储在 RTE Runtime 中,
类型是 <span class="title-ref">Object</span>. 其中:

- <span class="title-ref">app_id</span> 是一个
  <span class="title-ref">String</span> 类型的
  <span class="title-ref">Value</span>, 开发者可以通过
  <span class="title-ref">rte.get_property_string("app_id")</span>
  的方式获取. 即需要指明类型是 <span class="title-ref">string</span>.
- <span class="title-ref">log</span> 是一个
  <span class="title-ref">Object</span> 类型的
  <span class="title-ref">Value</span>, 在 RTE Value 系统中,
  <span class="title-ref">Object</span> 是一个复合的结构化数据, 其中以
  key-value pair 的形式包含其他的 <span class="title-ref">RTE
  Value</span>. 例如 <span class="title-ref">level</span> 就是
  <span class="title-ref">log</span> 中的一个 field, 类型是
  <span class="title-ref">int64</span>.

<div class="note">

<div class="title">

Note

</div>

这里就涉及到 RTE Schema 的一个作用: 显示声明 Value 的精度.

</div>

对于 JSON 来说, integer 类型的 <span class="title-ref">1</span>, 在 x64
中默认是按照 <span class="title-ref">int64</span> 来解析的. RTE Runtime
在读取到 JSON 后, 在默认情况下, 也只能按照
<span class="title-ref">int64</span> 的方式来处理.
尽管开发者期望的类型是 <span class="title-ref">uint8</span>, 但是从 JSON
中无法识别到这种信息. 这时, 就需要通过 <span class="title-ref">RTE
Schema</span> 的方式来显示声明 <span class="title-ref">level</span>
的类型是 <span class="title-ref">uint8</span>. 在 RTE Runtime 解析
property.json 后, 会根据 RTE Schema 中给出的定义, 对
<span class="title-ref">level</span> 的值做判断, 如果符合
<span class="title-ref">uint8</span> 的存储要求, 在 RTE Value 中就会以
<span class="title-ref">uint8</span> 的方式存储.

<div class="note">

<div class="title">

Note

</div>

RTE Schema 的遵循的规则之一, 在做强制转换时, 不损失数据精度,
保证数据的完整性. 同时, 不支持跨类型的重解析, 如 int 转成 double 或者
string.

</div>

## RTE Schema

RTE Schema 中的 <span class="title-ref">type</span> 与
<span class="title-ref">RTE Value</span> 中的
<span class="title-ref">type</span> 完全一致, 包括:

- int8
- int16
- int32
- int64
- uint8
- uint16
- uint32
- uint64
- float32
- float64
- string
- bool
- buf
- ptr
- array
- object

对于 简单数据类型 (上述中 <span class="title-ref">array</span> 和
<span class="title-ref">object</span>) 除外, 声明方式如下:

``` json
{
  "type": "int8"
}
```

对于 <span class="title-ref">array</span> 类型, 声明方式如下:

``` json
{
  "type": "array",
  "items": {
    "type": "int8"
  }
}
```

对于 <span class="title-ref">object</span> 类型, 声明的方式如下:

``` json
{
  "type": "object",
  "properties": {
    "field_1": {
      "type": "int8"
    },
    "field_2": {
      "type": "bool"
    }
  }
}
```

以上述示例中的 <span class="title-ref">property.json</span> 为例,
其对应的 <span class="title-ref">RTE Schema</span> 如下:

``` json
{
  "type": "object",
  "properties": {
    "app_id": {
      "type": "string"
    },
    "channel": {
      "type": "string"
    },
    "log": {
      "type": "object",
      "properties": {
        "level": {
          "type": "uint8"
        },
        "redirect_stdout": {
          "type": "bool"
        },
        "file": {
          "type": "string"
        }
      }
    }
  }
}
```

<div class="note">

<div class="title">

Note

</div>

- 目前 <span class="title-ref">RTE Schema</span> 只支持
  <span class="title-ref">type keyword</span>, 满足最基本的需要.
  后续会根据需求, 逐步完善.

</div>

## manifest.json

Extension 的 <span class="title-ref">RTE Schema</span> 定义, 需要保存在
<span class="title-ref">manifest.json</span> 中. 与
<span class="title-ref">property.json</span> 一样, 在
<span class="title-ref">rte.on_init_done()</span> 执行完成后,
<span class="title-ref">manifest.json</span> 会被 RTE Runtime 解析,
这样在 RTE Runtime 加载 property.json 时, 就可以根据其中的 schema
定义来校验数据合法性.

<span class="title-ref">RTE Schema</span> 是放置在
<span class="title-ref">manifest.json</span> 中的
<span class="title-ref">api</span> section 下.
<span class="title-ref">api</span> 是一个 JSON object, 包含该 Extension
涉及的所有 schema 的定义, 包括上述提到的配置以及接下来会介绍的消息(RTE
cmd/data/image_frame/pcm_frame). <span class="title-ref">api</span>
section 的结构如下:

``` json
{
  "property": {},
  "cmd_in": [],
  "cmd_out": [],
  "data_in": [],
  "data_out": [],
  "image_frame_in": [],
  "image_frame_out": [],
  "pcm_frame_in": [],
  "pcm_frame_out": [],
  "interface_in": [],
  "interface_out": []
}
```

其中, <span class="title-ref">property.json</span> 的 schema 就放置在
<span class="title-ref">property</span> section 下. 如上述示例对应的
manifest.json 的内容应该如下:

``` json
{
  "type": "extension",
  "name": "A",
  "version": "1.0.0",
  "language": "cpp",
  "dependencies": [],
  "api": {
    "property": {
      "app_id": {
        "type": "string"
      },
      "channel": {
        "type": "string"
      },
      "log": {
        "type": "object",
        "properties": {
          "level": {
            "type": "uint8"
          },
          "redirect_stdout": {
            "type": "bool"
          },
          "file": {
            "type": "string"
          }
        }
      }
    }
  }
}
```

<div class="note">

<div class="title">

Note

</div>

- <span class="title-ref">api/property</span> 算是 RTE manifest 中的
  annotation key, 在系统中已经明确
  <span class="title-ref">property</span> 的类型就应该是
  <span class="title-ref">Object</span>, 所以不需要再声明
  <span class="title-ref">type</span>.

</div>

## 消息

Extension 之间可以传递消息, 包括 cmd / data / image_frame / pcm_frame.
如果是作为生产者 (例如调用
<span class="title-ref">rte.send_cmd()</span>), 对应的 schema 是定义在
<span class="title-ref">manifest.json</span> 中的
<span class="title-ref">xxx_in</span> section 中, 如
<span class="title-ref">cmd_in</span>. 同理, 作为消费者 (例如通过
<span class="title-ref">on_cmd()</span> 回调接收), 对应的 schema
是定义在 <span class="title-ref">manifest.json</span> 中的
<span class="title-ref">xxx_out</span> section 中, 如
<span class="title-ref">cmd_out</span>.

消息的 schema 定义, 是以 <span class="title-ref">name</span> 为索引的.

- <span class="title-ref">cmd</span> 是必须指定
  <span class="title-ref">name</span> 的. 如:

  ``` json
  {
    "api": {
      "cmd_in": [
        {
          "name": "start",
          "property": {
            "app_id": {
              "type": "string"
            }
          }
        }
      ]
    }
  }
  ```

  <div class="note">

  <div class="title">

  Note

  </div>

  - 其中, <span class="title-ref">name</span> 和
    <span class="title-ref">property</span> 也是作为 annotation key.
    <span class="title-ref">property</span> 下的内容, 即是该 cmd 下的
    property 的 schema, 会作用于
    <span class="title-ref">cmd.set_property()</span> 和
    <span class="title-ref">cmd.get_property()</span> 等 API.

  </div>

- <span class="title-ref">data</span> /
  <span class="title-ref">image_frame</span> /
  <span class="title-ref">pcm_frame</span> 的
  <span class="title-ref">name</span> 是可选的. 也就是说 schema 定义中的
  <span class="title-ref">name</span> 是可选的; 不指定
  <span class="title-ref">name</span> 的 schema 会被视为默认的 schema.
  也就是说, 对于任一个消息, 如果存在
  <span class="title-ref">name</span>, 则按
  <span class="title-ref">name</span> 索引 schema; 如果找不到,
  则取默认的 schema. 如:

  ``` json
  {
    "api": {
      "data_in": [
        {
          "property": {
            "width": {
              "type": "uint32"
            }
          }
        },
        {
          "name": "speech",
          "property": {
            "width": {
              "type": "uint16"
            }
          }
        }
      ]
    }
  }
  ```

同样, 在将 JSON 作为 msg 的 property 时, 如果存在 schema, 也会根据
schema 中的定义, 对类型和精度进行转换.

对于上述的示例, Extension A 的 <span class="title-ref">cmd_out</span>
(即 A 会调用 rte.send_cmd()), 对应了 Extension B 的
<span class="title-ref">cmd_in</span> (即 B 会在
<span class="title-ref">on_cmd()</span> 回调中收到消息).

<div class="note">

<div class="title">

Note

</div>

- 目前, 如果 A 发出的 cmd 不符合 schema 的定义, 则 B 不会收到 cmd, RTE
  Runtime 会向 A 返回一个 error.

</div>

相对于 <span class="title-ref">data / image_frame / pcm_frame</span>
来说, <span class="title-ref">cmd</span> 是有 ack 的 (在 RTE 中, 是以
<span class="title-ref">status cmd</span> 表示). 也就是, 在定义
<span class="title-ref">cmd schema</span> 时, 也可以定义其对应的
<span class="title-ref">status cmd</span> 的 schema. 如:

``` json
{
  "api": {
    "cmd_in": [
      {
        "name": "start",
        "property": {
          "app_id": {
            "type": "string"
          }
        },
        "result": {
          "property": {
            "detail": {
              "type": "string"
            },
            "code": {
              "type": "uint8"
            }
          }
        }
      }
    ]
  }
}
```

<div class="note">

<div class="title">

Note

</div>

- <span class="title-ref">status</span> 为 annotation key, 是定义
  <span class="title-ref">status</span> schema 的入口.
- <span class="title-ref">rte/detail</span> 是 annotation key, 是定义
  <span class="title-ref">status</span> 中 detail 的类型. 作用于
  <span class="title-ref">rte.return_string()</span>,
  <span class="title-ref">cmd.get_detail()</span> 等API.
- <span class="title-ref">status/property</span> 是 annotation key,
  作用与 cmd 中的 property 一致.
- <span class="title-ref">cmd_in</span> 中的
  <span class="title-ref">status</span> 是指作为 生产者 收到的下游
  Extension 的响应. 同样, <span class="title-ref">cmd_out</span> 中的
  <span class="title-ref">status</span> 是指作为 消费者
  向上游回复的响应.

</div>

## 示例

以 <span class="title-ref">rte_stt_asr_filter</span> extension 作为示例,
看下如何定义 schema.

首先, <span class="title-ref">rte_stt_asr_filter</span> extension 下的
<span class="title-ref">property.json</span> 文件并没有用到, 其配置是在
Graph 中指定的, 如下:

``` json
{
  "type": "extension",
  "name": "rte_stt_asr_filter",
  "addon": "rte_stt_asr_filter",
  "extension_group": "rtc_group",
  "property": {
    "app_id": "1a4dcbc3",
    "api_key": "b6e21445580c80a2a62a9c0394bc5e83",
    "api_secret": "ZTliNzFhODU2MDMzYzQzYzUxODNmY2Ix",
    "plugin_path": "addon/extension/rte_stt_asr_filter/lib/liblinux_audio_hy_extension.so",
    "data_encoding": "raw"
  }
}
```

对应的 schema 应该是:

``` json
{
  "api": {
    "property": {
      "app_id": {
        "type": "string"
      },
      "api_key": {
        "type": "string"
      },
      "api_secret": {
        "type": "string"
      },
      "plugin_path": {
        "type": "string"
      },
      "data_encoding": {
        "type": "string"
      }
    }
  }
}
```

接着, 会接收如下五个 cmd:

``` cpp
if (command == COMMAND_START) {
  handleStart(rte, std::move(cmd));
} else if (command == COMMAND_STOP) {
  handleStop(rte, std::move(cmd));
} else if (command == COMMAND_ON_USER_AUDIO_TRACK_SUBSCRIBED) {
  handleUserAudioTrackSubscribed(rte, std::move(cmd));
} else if (command == COMMAND_ON_USER_AUDIO_TRACK_STATE_CHANGED) {
  handleUserAudioTrackStateChanged(rte, std::move(cmd));
} else if (command == COMMAND_QUERY) {
  handleQuery(rte, std::move(cmd));
} else {
  RTE_LOGE("FATAL: unknown command: %s", command.c_str());
  rte.return_string(RTE_STATUS_CODE_ERROR, "not implemented", std::move(cmd));
}
```

下面以 <span class="title-ref">start</span> 和
<span class="title-ref">onUserAudioTrackSubscribed</span> cmd 为例.

- start

  ``` cpp
  class Config
  {
    // ...

    private:
      std::vector<std::string> languages_;
      std::string licenseFilePath_;
  };

  void from_json(const nlohmann::json& j, Config& p)
  {
    try {
      j.at("languages").get_to(p.languages_);
    } catch (std::exception& e) {
      RTE_LOGW("Failed to parse 'languages' property: %s", e.what());
    }

    try {
      j.at("licenseFilePath").get_to(p.licenseFilePath_);
    } catch (std::exception& e) {
      RTE_LOGW("Failed to parse 'licenseFilePath' property: %s", e.what());
    }
  }
  ```

  对于 start cmd, 其中包括两个 property:

  - \`languages\`: 是一个 <span class="title-ref">array</span> 类型,
    其中的元素是 <span class="title-ref">string</span> 类型.
  - \`licenseFilePath\`: 是一个 <span class="title-ref">string</span>
    类型.

  所以, 对应的 schema 应该是:

  ``` json
  {
    "api": {
      "cmd_in": [
        {
          "name": "start",
          "property": {
            "languages": {
              "type": "array",
              "items": {
                "type": "string"
              }
            },
            "licenseFilePath": {
              "type": "string"
            }
          },
          "result": {
            "property": {
              "detail": {
                "type": "string"
              }
            }
          }
        }
      ]
    }
  }
  ```

- onUserAudioTrackSubscribed

  ``` cpp
  void rte_stt_asr_filter_extension_t::handleUserAudioTrackSubscribed(
      rte::rte_t &rte, std::unique_ptr<rte::cmd_t> cmd) {
    auto user_id = cmd->get_property_string("userId");
    auto *track =
        cmd->get_property<agora::rtc::IRemoteAudioTrack *>("audioTrack");

    // ...

    rte.return_string(RTE_STATUS_CODE_OK, "done", std::move(cmd));
  }
  ```

  对于 onUserAudioTrackSubscribed cmd, 其中包括两个 property:

  - \`userId\`: 是一个 <span class="title-ref">string</span> 类型.
  - \`audioTrack\`: 是一个 <span class="title-ref">ptr</span> 类型, 指向
    <span class="title-ref">agora::rtc::IRemoteAudioTrack</span> 类型.

  所以, 对应的 schema 应该是:

  ``` json
  {
    "api": {
      "cmd_in": [
        {
          "name": "onUserAudioTrackSubscribed",
          "property": {
            "userId": {
              "type": "string"
            },
            "audioTrack": {
              "type": "ptr"
            }
          },
          "result": {
            "property": {
              "detail": {
                "type": "string"
              }
            }
          }
        }
      ]
    }
  }
  ```
