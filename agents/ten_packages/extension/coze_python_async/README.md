# coze_python_async

This is a python extension for coze service. The schema of coze service is attached in `schema.yml`.

An example of OpenAI wrapper is also attached in `examples/openai_wrapper.py`.

## Features

The extension will record history with count of `max_history`.

- `api_url` (must have): the url for the coze service.
- `token` (must have): use Bearer token to support default auth

The extension support flush that will close the existing http session.

## API

Refer to `api` definition in [manifest.json] and default values in [property.json](property.json).

- In:
 - `text_data` [data]: the asr result
 - `flush` [cmd]: the flush signal
- Out:
 - `flush` [cmd]: the flush signal

## Examples

You can run example using following command, and the wrapper service will listen 8000 by default.

```
> export API_TOKEN="xxx" && export OPENAI_API_KEY="xxx" && python3 openai_wrapper.py

INFO:     Started server process [162886]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```
