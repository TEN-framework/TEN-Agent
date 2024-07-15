## Overview

<span class="title-ref">RTE Schema</span> provides a way to describe the data structure of <span class="title-ref">RTE Value</span>. <span class="title-ref">RTE Value</span> is a structured data type used in RTE Runtime to store information such as properties. <span class="title-ref">RTE Schema</span> can be used to define the data structure of configuration files for Extensions, as well as the data structure of messages sent and received by Extensions.

The most common use case is when there are two Extensions - A and B, and A sends a command to B. In this scenario, RTE Schema is involved in the following places:

- Configuration file of Extension A.
- Configuration file of Extension B.
- Data structure of the message carried by the command sent by A as a producer.
- Data structure of the message carried by the command received by B as a consumer.

## Configuration Files

RTE Extensions typically have two configuration files:

- property.json: This file contains the business-specific configuration of the Extension, such as:

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

- manifest.json: This file contains the immutable information of the Extension, including metadata (type, name, version, etc.) and schema definitions. For example:

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

Developers can customize the logic for loading configuration files in the <span class="title-ref">Extension::on_init()</span> function. By default, RTE Extension automatically loads the <span class="title-ref">property.json</span> and <span class="title-ref">manifest.json</span> files in the directory. After the <span class="title-ref">Extension::on_start()</span> callback is triggered, developers can use <span class="title-ref">rte::get_property()</span> to retrieve the contents of <span class="title-ref">property.json</span>. For example:

``` cpp

```cpp
void on_init(rte::rte_t &rte, rte::metadata_info_t &manifest,
       rte::metadata_info_t &property) override {
  // You can load custom configuration files using the following method. In this case, the default property.json will not be loaded.
  // property.set(RTE_METADATA_JSON_FILENAME, "a.json");

  rte.on_init_done(manifest, property);
}
```

After the `rte.on_init_done()` is triggered, the content of property.json will be stored in RTE Runtime as an RTE Value, with the type of Object. Here are some details:

- `app_id` is a Value of type String, and developers can retrieve it using `rte.get_property_string("app_id")`, specifying the type as string.
- `log` is a Value of type Object. In the RTE Value system, Object is a composite structured data that contains other RTE Values in key-value pairs. For example, `level` is a field in `log` and its type is int64.

<div class="note">

<div class="title">

Note

</div>

This involves one of the purposes of RTE Schema: to explicitly declare the precision of Values.

</div>

For JSON, an integer value like `1` is by default parsed as `int64` in x64. When RTE Runtime reads JSON, it can only handle it as `int64` by default. Even if the developer expects the type to be `uint8`, this information cannot be inferred from JSON alone. This is where RTE Schema comes in, to explicitly declare the type of `level` as `uint8`. After parsing property.json with RTE Runtime, the value of `level` will be evaluated based on the definition in the RTE Schema. If it meets the storage requirements of `uint8`, it will be stored as `uint8` in the RTE Value.

<div class="note">

<div class="title">

Note

</div>

One of the rules followed by RTE Schema is to ensure data integrity and no loss of precision during type conversion. It does not support cross-type re-parsing, such as converting int to double or string.

</div>

## RTE Schema

The <span class="title-ref">type</span> in RTE Schema is exactly the same as the <span class="title-ref">type</span> in RTE Value, including:

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

Except for the simple data types (<span class="title-ref">array</span> and <span class="title-ref">object</span>), the declaration is as follows:

``` json
{
  "type": "int8"
}
```

For the <span class="title-ref">array</span> type, the declaration is as follows:

``` json
{
  "type": "array",
  "items": {
    "type": "int8"
  }
}
```

For the <span class="title-ref">object</span> type, the declaration is as follows:

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

Using the example of <span class="title-ref">property.json</span> mentioned above, its corresponding RTE Schema is as follows:

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

- Currently, RTE Schema only supports the <span class="title-ref">type keyword</span> to meet the basic needs. It will be gradually improved based on future requirements.

</div>

## manifest.json

The definition of the RTE Schema for the Extension needs to be saved in the manifest.json file. Similar to property.json, after the rte.on_init_done() is executed, manifest.json will be parsed by the RTE Runtime. This allows the RTE Runtime to validate the data integrity based on the schema definitions when loading property.json.

The RTE Schema is placed under the api section in manifest.json. The api section is a JSON object that contains the definitions of all the schemas involved in the Extension, including the configurations mentioned above and the messages (RTE cmd/data/image_frame/pcm_frame) that will be introduced next. The structure of the api section is as follows:

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

The schema for property.json is placed under the property section. The content of the manifest.json corresponding to the example mentioned above should be as follows:

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

## Messages

Extensions can exchange messages, including cmd/data/image_frame/pcm_frame. If it is used as a producer (e.g., calling rte.send_cmd()), the corresponding schema is defined in the xxx_in section of manifest.json, such as cmd_in. Similarly, if it is used as a consumer (e.g., receiving messages in the on_cmd() callback), the corresponding schema is defined in the xxx_out section of manifest.json, such as cmd_out.

The schema definition for messages is indexed by name.

- cmd must specify the name. For example:

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

- For data/image_frame/pcm_frame, the name is optional. This means that the name in the schema definition is optional; schemas without a specified name will be considered as the default schema. In other words, for any message, if a name exists, the schema will be indexed by that name; if not found, the default schema will be used. For example:

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


Similarly, when using JSON as the property of a message, if a schema exists, the types and precision will be converted according to the definitions in the schema.

For the example mentioned above, Extension A's cmd_out (i.e., A calling rte.send_cmd()) corresponds to Extension B's cmd_in (i.e., B receiving the message in the on_cmd() callback).

<div class="note">

<div class="title">

Note

</div>

- Currently, if the cmd sent by A does not comply with the schema definition, B will not receive the cmd, and the RTE Runtime will return an error to A.

</div>

Compared to data/image_frame/pcm_frame, cmd has an ack (represented as status cmd in RTE). This means that when defining the cmd schema, you can also define the schema for the corresponding status cmd. For example:

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

- "status" is the annotation key used to define the status schema.
- "rte/detail" is the annotation key used to define the type of detail in the status. It is used in APIs like rte.return_string(), cmd.get_detail(), etc.
- "status/property" is the annotation key that works the same as the property in cmd.
- The "status" in cmd_in refers to the response received from the downstream Extension as a producer. Similarly, the "status" in cmd_out refers to the response sent back to the upstream as a consumer.

</div>

## Example

Taking the rte_stt_asr_filter extension as an example, let's see how to define the schema.

First, the property.json file under the rte_stt_asr_filter extension is not used. Its configuration is specified in the Graph as follows:

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

The corresponding schema should be:

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

Next, it will receive the following five cmds:

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

Let's take start and onUserAudioTrackSubscribed cmds as examples.

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

  For the start cmd, it includes two properties:

  - `languages`: an array type with elements of string type.
  - `licenseFilePath`: a string type.

  So, the corresponding schema should be:

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

  For the onUserAudioTrackSubscribed cmd, it includes two properties:

  - `userId`: a string type.
  - `audioTrack`: a ptr type pointing to agora::rtc::IRemoteAudioTrack.

  So, the corresponding schema should be:

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

