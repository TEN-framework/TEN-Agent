# vision_tool_python

This is tool for vision ability, currently there are two patterns:
- use triditional model
- use multimodal llm model

The pattern can be switched by `use_llm` pattern to use different cmd protocol.

Tool description is as follow:

*Query to the latest frame from camera. The camera is always on, always use latest frame to answer user's question. Call this whenever you need to understand the input camera image like you have vision capability, for example when user asks 'What can you see?', 'Can you see me?', 'take a look.'*

It is built using TEN Tool Call Protocol (Beta).

## Features

The tool can accept video frame from rtc extension.

The tool will only register itself to llm extension as soon as the video frame is received.

The tool will cache video frame every `frequency_ms` ms.

## API

Refer to `api` definition in [manifest.json] and default values in [property.json](property.json).

- out: `tool_register`
- in: `tool_call`
- out(`use_llm=false`): `analyze_image`
- out(`use_llm=true`): `chat_completion`

## Misc

- Multi-frame support
- Movement detection
- Prompt Engineering