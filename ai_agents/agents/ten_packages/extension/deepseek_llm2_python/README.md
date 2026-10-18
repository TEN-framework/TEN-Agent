# DeepSeek LLM2 extension

`deepseek_llm2_python` provides the LLM2 command interface for the optional
`voice_assistant_jev_router` graph. It uses the OpenAI-compatible DeepSeek API
at `https://api.deepseek.com` with the `deepseek-flash` model.

The controller passes `extra_body.thinking.type` as `enabled` or `disabled`
for each request. When DeepSeek streams `reasoning_content`, this extension
emits TEN reasoning events separately from answer events. It never logs the
API key, request body, generated answer, or reasoning text.

The shared `openai_llm2_python` extension is not imported by this package.
