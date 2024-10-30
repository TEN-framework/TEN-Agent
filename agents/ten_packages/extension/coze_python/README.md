# coze_python

This is the coze extension that will call coze bot to have conversation.

Each agent will create a new conversation and chat using stream mode.

## Features

Currently the coze should support not only coze.cn and coze.com.

Use https://github.com/coze-dev/coze-py to connect to coze server.

## API

Refer to `api` definition in [manifest.json] and default values in [property.json](property.json).

### Input

- Receive input query only for `is_final=true`
- Will produce stream result
