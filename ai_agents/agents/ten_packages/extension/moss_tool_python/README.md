# moss_tool_python

Gives a TEN agent a `search_knowledge_base` tool backed by [Moss](https://www.moss.dev).
Moss runs hybrid (semantic and keyword) search on an index you build and manage in Moss.
The extension downloads the index when it starts and searches it in memory, so a search
makes no network request.

## Two ways to use it

- **Tool call.** The LLM decides when to search. Add the node and connect its
  `tool_register` command to `main_control`, as with any tool extension.
- **Ambient retrieval.** `main_control` searches on every final user turn and adds the
  results to that turn before the LLM runs. The LLM answers in one call and never sees the
  tool. This needs the `context_tool` property of the `main_python` extension in
  [voice-assistant-with-moss](../../../examples/voice-assistant-with-moss).

## Configuration

| Property | Default | Description |
| --- | --- | --- |
| `project_id` | `${env:MOSS_PROJECT_ID}` | Moss project ID |
| `project_key` | `${env:MOSS_PROJECT_KEY}` | Moss project key |
| `index_name` | `${env:MOSS_INDEX_NAME}` | Index to search |
| `top_k` | `3` | Passages returned per search |

Create a project and an index in the [Moss portal](https://portal.usemoss.dev), from documents,
files or a website. The extension checks Moss for a new version of the index every 10 minutes.
If the index fails to load, the extension logs the error and does not register the tool,
so the agent keeps running without it.

## Maintenance

Moss maintains this extension and its example. For issues, open one here and mention
`moss_tool_python`, or write to contact@moss.dev.
