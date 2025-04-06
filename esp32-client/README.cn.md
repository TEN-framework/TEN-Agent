# 声网 ESP32 大模型智能对话

*简体中文| [English](README.md)*

## 例程简介

本例程演示了如何通过乐鑫 ESP32-S3 Korvo V3 开发板，模拟一个典型的大模型智能对话场景，可以演示进入大模型进行实时智能对话。

### 文件结构
```
├── CMakeLists.txt
├── components                                  Agora iot sdk component
│   ├── agora_iot_sdk
│   │   ├── CMakeLists.txt
│   │   ├── include                             Agora iot sdk header files
│   │   │   ├── agora_rtc_api.h
│   │   └── libs                                Agora iot sdk libraries                      
│   │       ├── libagora-cjson.a
│   │       ├── libahpl.a
│   │       ├── librtsa.a
|   ├── esp32-camera                           esp32-camera component submodule
├── main                                        LLM Demo code
│   ├── ai_agent.h
│   ├── app_config.h
│   ├── common.h
│   ├── audio_proc.h
│   ├── rtc_proc.h
│   ├── CMakeLists.txt
│   ├── Kconfig.projbuild
|   ├── ai_agent.c
|   ├── audio_proc.c
|   ├── rtc_proc.c
│   └── llm_main.c
├── partitions.csv                              partition table
├── README.en.md
├── README.md
├── sdkconfig.defaults
└── sdkconfig.defaults.esp32s3
```

## 环境配置

### 硬件要求

本例程目前仅支持`ESP32-S3-Korvo-2 V3`开发板。

## 编译和下载

### esp32-camera

编译运行本示例需要 esp32-camera 组件。该组件已作为子模块添加到 `components/esp32-camera` 目录中。请运行以下命令克隆子模块：

```bash
git submodule update --init --recursive
```

### Agora IOT SDK

编译运行本示例需要 Agora IoT SDK。Agora IoT SDK 可以在 [这里](https://rte-store.s3.amazonaws.com/agora_iot_sdk.tar) 下载。
将 `agora_iot_sdk.tar` 放到 `esp32-client/components` 目录下，并运行如下命令：

```bash
cd esp32-client/components
tar -xvf agora_iot_sdk.tar
```

### Linux 操作系统

#### 默认 IDF 分支

本例程支持 IDF tag v[5.2.3] 及以后的，例程默认使用 IDF tag v[5.2.3] (commit id: c9763f62dd00c887a1a8fafe388db868a7e44069)。

选择 IDF 分支的方法，如下所示：

```bash
cd $IDF_PATH
git checkout v5.2.3
git pull
git submodule update --init --recursive
```

本例程支持 ADF v2.7 tag (commit id: 9cf556de500019bb79f3bb84c821fda37668c052)

#### 打上 IDF 补丁

本例程还需给 IDF 合入1个 patch， 合入命令如下：

```bash
export ADF_PATH=~/esp/esp-adf
cd $IDF_PATH
git apply $ADF_PATH/idf_patches/idf_v5.2_freertos.patch
```

#### 编译固件

将本例程(esp32-client)目录拷贝至 ~/esp 目录下。请运行如下命令：

```bash
$ . $HOME/esp/esp-idf/export.sh
$ cd ~/esp/esp32-client
$ idf.py set-target esp32s3
$ idf.py menuconfig	--> Agora Demo for ESP32 --> (配置 WIFI SSID 和 Password)
$ idf.py build
```
配置freertos的前向兼容能力
在menuconfig中Component config --> FreeRTOS --> Kernel设置configENABLE_BACKWARD_COMPATIBILITY

### Windows 操作系统

#### 默认 IDF 分支

下载IDF，选择v5.2.3 offline版本下载，例程默认使用 IDF tag v[5.2.3]
https://docs.espressif.com/projects/esp-idf/zh_CN/v5.2.3/esp32/get-started/windows-setup.html

下载ADF，ADF目录Espressif/frameworks，为支持ADF v2.7 tag (commit id: 9cf556de500019bb79f3bb84c821fda37668c052)
https://docs.espressif.com/projects/esp-adf/zh_CN/latest/get-started/index.html#step-2-get-esp-adf


#### 打上 IDF 补丁

方法一.系统设置中将ADF_PATH添加到环境变量
E:\esp32s3\Espressif\frameworks\esp-adf
方法二.命令行中将ADF_PATH添加到环境变量

```bash
$ setx ADF_PATH Espressif/frameworks/esp-adf
```

注意：ADF_PATH环境变量设置后，重启ESP-IDF 5.2 PowerShell生效

本例程还需给 IDF 合入1个 patch， 合入命令如下：

```bash
cd $IDF_PATH
git apply $ADF_PATH/idf_patches/idf_v5.2_freertos.patch
```

#### 编译固件

将本例程(esp32-client)目录拷贝至 Espressif/frameworks 目录下。请运行如下命令：
```bash
$ cd ../esp32-client
$ idf.py set-target esp32s3
$ idf.py menuconfig	--> Agora Demo for ESP32 --> (配置 WIFI SSID 和 Password)
$ idf.py build
```
配置freertos的前向兼容能力
在menuconfig中Component config --> FreeRTOS --> Kernel设置configENABLE_BACKWARD_COMPATIBILITY


### 下载固件

请运行如下命令：

```bash
$ idf.py -p /dev/ttyUSB0 flash monitor
```
注意：Linux系统中可能会遇到 /dev/ttyUSB0 权限问题，请执行 sudo usermod -aG dialout $USER

下载成功后，本例程会自动运行，待设备端加入RTC频道完成后，可以看到串口打印："Agora: Press [SET] key to Join the Ai Agent ..."。


## 如何使用例程

### 五分钟快速体验

注意：

1. 请确认开发板上已至少接入一个扬声器。

### 配置你自己的 AI Agent

1. 请在 `app_config.h` 文件中配置你自己的 AI Agent。
2. 修改 `TENAI_AGENT_URL` 为你自己的 TEN-Agent 服务器 URL (一般为你通过 `task run` 启动的8080服务)。
3. 修改 `AI_AGENT_CHANNEL_NAME` 为你自己的 AI Agent Channel 名称。
4. 如果你之前就在TEN-Agent配置过 `openai_v2v` 或 `gemini_v2v` (取决于你在`app_config.h`中配置的宏定义(`CONFIG_GRAPH_OPENAI` 或 `CONFIG_GRAPH_GEMINI`)) 的graph， 你可以直接请求使用。`openai_v2v` 目前不支持图像输入，`gemini_v2v` 支持图像输入。
5. 如果你没有配置过 `openai_v2v` graph 或者想使用其他 graph，你需要在 `ai_agent.c` 的 `_build_start_json` 函数中修改启动的相关参数。
6. 重新编译后烧录到芯片上。

#### Demo：大模型AiAgent实时语音对话

1. 按键 `SET` 表示启动大模型
2. 按键 `MUTE` 表示停止大模型
3. 按键 `VOL+` 表示增大音量，一次增大10，最大到100
4. 按键 `VOL-` 表示减小音量，一次减小10，最小到0
5. 设备开机后，设备自动连接到服务器生成APPID对应的Channel频道内。按下 `SET` 键，开始启动大模型，开始进行实时语音对话；按下 `MUTE` 键，停止大模型。


## 关于声网

声网音视频物联网平台方案，依托声网自建的底层实时传输网络 Agora SD-RTN™ (Software Defined Real-time Network)，为所有支持网络功能的 Linux/RTOS 设备提供音视频码流在互联网实时传输的能力。该方案充分利用了声网全球全网节点和智能动态路由算法，与此同时支持了前向纠错、智能重传、带宽预测、码流平滑等多种组合抗弱网的策略，可以在设备所处的各种不确定网络环境下，仍然交付高连通、高实时和高稳定的最佳音视频网络体验。此外，该方案具有极小的包体积和内存占用，适合运行在任何资源受限的 IoT 设备上，包括乐鑫 ESP32 全系列产品。

## 技术支持

请按照下面的链接获取技术支持：

- 如果发现了示例代码的 bug 和有其他疑问，可以直接联系社区负责人

我们会尽快回复。

