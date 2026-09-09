# mcp_client_python

Connects the agent to an [MCP](https://modelcontextprotocol.io/) server and
exposes every tool the server advertises as an LLM tool, so the LLM extension
can call them like any other tool.

## Features

- Registers all tools reported by the MCP server through `tool_register`
- Forwards `tool_call` to the server and returns the result to the LLM
- Two transports:
  - **stdio** — launches a local MCP server as a subprocess (`command`)
  - **SSE** — connects to a remote MCP server over HTTP (`url`)

## Configuration

| Property  | Type   | Description |
| --------- | ------ | ----------- |
| `command` | string | Command line of a local MCP server, launched and spoken to over stdio. Takes precedence over `url`. |
| `url`     | string | SSE endpoint of a remote MCP server. |

One of the two is required. If neither is set, the extension logs an error and
registers no tools.

### stdio (local server)

```json
{
  "command": "npx -y @modelcontextprotocol/server-filesystem /data"
}
```

The command line is split with `shlex.split`, so ordinary shell quoting works:

```json
{
  "command": "python -m my_server --root '/data/my files'"
}
```

The server runs as a child process of the extension and is shut down together
with it.

### SSE (remote server)

```json
{
  "url": "https://example.com/sse"
}
```

## API

Refer to the `api` definition in [manifest.json](manifest.json) and the
default values in [property.json](property.json).
