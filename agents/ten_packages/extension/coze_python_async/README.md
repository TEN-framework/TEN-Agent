# coze_python_async

This is a python extension for coze that support both coze.cn and coze.com.

## Features

Currently the extension only support conversation with certain bot.

- `bot_id` (must have)
- `token` (must have)
- `base_url` (optional): can be coze.com or coze.cn

The extension support flush that will close the existing http session.

### TODO List

Currently file upload is not support and there is no memory support in current extension.

## API

Refer to `api` definition in [manifest.json] and default values in [property.json](property.json).

- In:
 - `text_data` [data]: the asr result
 - `flush` [cmd]: the flush signal
- Out:
 - `flush` [cmd]: the flush signal
