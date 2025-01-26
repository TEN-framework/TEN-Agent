# Agora ESP32 Large Model Intelligent Dialogue

*Simplified Chinese | [English](README.en.md)*

## Overview

This is an RTC Client SDK & Demo running on Espressif ESP32-S3 Korvo V3 development board. This example demonstrates how to make TEN-Agent work with it.

### File Structure
```
├── CMakeLists.txt
├── components                                  Agora IoT SDK component
│   ├── agora_iot_sdk
│   │   ├── CMakeLists.txt
│   │   ├── include                             Agora IoT SDK header files
│   │   │   ├── agora_rtc_api.h
│   │   └── libs                                Agora IoT SDK libraries                      
│   │       ├── libagora-cjson.a
│   │       ├── libahpl.a
│   │       ├── librtsa.a
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
├── partitions.csv                              Partition table
├── README.en.md
├── README.md
├── sdkconfig.defaults
└── sdkconfig.defaults.esp32s3
```

## Environment Setup

### Hardware Requirements

This example currently supports the `ESP32-S3-Korvo-2 V3` development board only.

## Compilation and Download

### Agora IOT SDK

To compile and run this example, you need the Agora IoT SDK.
The SDK can be downloaded at [here](https://rte-store.s3.amazonaws.com/agora_iot_sdk.tar)
Put `agora_iot_sdk.tar` to `esp32-client/components` directory and run the following command:

```bash
cd esp32-client/components
tar -xvf agora_iot_sdk.tar
```

### Linux Operating System

#### Default IDF Branch

This example supports IDF tag v[5.2.3] and later versions, with the default set to IDF tag v[5.2.3] (commit id: c9763f62dd00c887a1a8fafe388db868a7e44069).

To select the correct IDF branch, run the following commands:
```bash
cd $IDF_PATH
git checkout v5.2.3
git pull
git submodule update --init --recursive
```

This example supports ADF v2.7 tag (commit id: 9cf556de500019bb79f3bb84c821fda37668c052).

#### Applying the IDF Patch

A patch must be applied to IDF. Use the following command:
```bash
export ADF_PATH=~/esp/esp-adf
cd $IDF_PATH
git apply $ADF_PATH/idf_patches/idf_v5.2_freertos.patch
```

#### Compiling the Firmware

Copy the example project directory (esp32-client) to the `~/esp` directory and run the following commands:
```bash
$ . $HOME/esp/esp-idf/export.sh
$ cd ~/esp/esp32-client
$ idf.py set-target esp32s3
$ idf.py menuconfig	--> Agora Demo for ESP32 --> (Configure WIFI SSID and Password)
$ idf.py build
```

To configure FreeRTOS backward compatibility:
In `menuconfig`, navigate to `Component config` --> `FreeRTOS` --> `Kernel` and enable `configENABLE_BACKWARD_COMPATIBILITY`.

### Windows Operating System

#### Default IDF Branch

Download IDF, selecting version v5.2.3 (offline version) from the following link:  
[ESP-IDF Windows Setup](https://docs.espressif.com/projects/esp-idf/zh_CN/v5.2.3/esp32/get-started/windows-setup.html)

Download ADF to the `Espressif/frameworks` directory to support ADF v2.7 tag (commit id: 9cf556de500019bb79f3bb84c821fda37668c052):  
[ESP-ADF Setup](https://docs.espressif.com/projects/esp-adf/zh_CN/latest/get-started/index.html#step-2-get-esp-adf)

#### Applying the IDF Patch

Method 1: Add `ADF_PATH` to the environment variables in system settings:
```
E:\esp32s3\Espressif\frameworks\esp-adf
```

Method 2: Add `ADF_PATH` via the command line:
```bash
$ setx ADF_PATH Espressif/frameworks/esp-adf
```

**Note:** After setting the `ADF_PATH` environment variable, restart ESP-IDF 5.2 PowerShell for changes to take effect.

Apply the required patch to IDF using:
```bash
cd $IDF_PATH
git apply $ADF_PATH/idf_patches/idf_v5.2_freertos.patch
```

#### Compiling the Firmware

Copy the example project directory (esp32-client) to the `Espressif/frameworks` directory and run the following commands:
```bash
$ cd ../esp32-client
$ idf.py set-target esp32s3
$ idf.py menuconfig	--> Agora Demo for ESP32 --> (Configure WIFI SSID and Password)
$ idf.py build
```

Configure FreeRTOS backward compatibility:  
In `menuconfig`, navigate to `Component config` --> `FreeRTOS` --> `Kernel` and enable `configENABLE_BACKWARD_COMPATIBILITY`.

### Flashing the Firmware

Run the following command:
```bash
$ idf.py -p /dev/ttyUSB0 flash monitor
```
**Note:** On Linux, you might encounter permission issues with `/dev/ttyUSB0`. Run the following command to fix it:
```bash
sudo usermod -aG dialout $USER
```

Once flashing is complete, the example will run automatically. After the device joins the RTC channel, the serial output will display:  
**"Agora: Press [SET] key to Join the Ai Agent ..."**

## How to Use the Example

### Quick Start in 5 Minutes

**Note:**  
Ensure at least one speaker is connected to the development board.

#### Demo: Real-time Voice Dialogue with Large Model AiAgent

1. Press the `SET` button to start the large model.
2. Press the `MUTE` button to stop the large model.
3. Press the `VOL+` button to increase volume (increments of 10, up to a maximum of 100).
4. Press the `VOL-` button to decrease volume (decrements of 10, down to a minimum of 0).
5. After the device boots up, it will automatically connect to the RTC channel associated with the generated APPID. Press the `SET` button to initiate real-time voice dialogue; press the `MUTE` button to stop it.

### Registering Your Own Doorbell Account

Let's walk you through creating your own user and device accounts.

#### Creating a New Device Account

1. Open the `app_config.h` file in the project.
2. Modify `AI_AGENT_NAME` to a unique name for the large model AiAgent task.
3. Modify `AI_AGENT_CHANNEL_NAME` to a unique channel name.
4. Recompile and flash the firmware. You can now use the new `AI_AGENT_NAME` and `AI_AGENT_CHANNEL_NAME` for real-time voice dialogue.

## About Agora

Agora’s audio and video IoT platform leverages its proprietary real-time transmission network, **Agora SD-RTN™ (Software Defined Real-time Network)**, to provide real-time audio and video streaming capabilities for Linux/RTOS devices with networking capabilities. The solution ensures high connectivity, real-time performance, and stability even under uncertain network conditions using advanced techniques such as forward error correction, intelligent retransmission, bandwidth prediction, and stream smoothing. Additionally, it offers a minimal memory footprint, making it ideal for resource-constrained IoT devices, including the entire Espressif ESP32 series.

## Technical Support

For technical support, follow the links below:

- Report bugs and inquiries directly to the community representatives.

We will respond as soon as possible.
