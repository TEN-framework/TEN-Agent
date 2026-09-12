# 08 Security

> Secret management, input validation, and repository hygiene.

## API Key Management

- **Single source**: All API keys live in `ai_agents/.env` (git-ignored)
- **Never hardcode** keys in `property.json` — use `${env:VAR_NAME}` substitution
- **Persistent storage**: Keep a copy of keys outside the repo (e.g., `~/api_keys.txt`)
  so branch switches don't lose them
- See `.env.example` for the complete variable catalog

## Environment Variable Substitution

In `property.json`, reference secrets via:

```json
{
  "api_key": "${env:DEEPGRAM_API_KEY}",
  "region": "${env:AZURE_REGION|eastus}"
}
```

| Syntax                    | Behavior                     |
| ------------------------- | ---------------------------- |
| `${env:VAR}`              | Required — error if missing  |
| `${env:VAR\|}`            | Optional — empty if missing  |
| `${env:VAR\|default}`     | Optional — default if missing|

## Sensitive Data in Logs

Extensions must encrypt sensitive fields before logging:

```python
def to_str(self, sensitive_handling: bool = True) -> str:
    config = copy.deepcopy(self)
    if config.params and "api_key" in config.params:
        config.params["api_key"] = utils.encrypt(config.params["api_key"])
    return f"{config}"
```

Never log raw API keys, tokens, or credentials.

## TLS Verification

- Use `ssl.create_default_context()` for outbound TLS and WebSocket clients.
- Never set `check_hostname` to `False` or `verify_mode` to `ssl.CERT_NONE`.
- Never use `ssl._create_unverified_context()` for production connections.
- Add trusted private certificate authorities to the default context when a
  deployment requires them; do not disable verification globally.

## Server-Side Protections

The Go server (`http_server.go`) implements:

- **Path traversal prevention**: Ignores client-requested `tenapp_dir`, always uses
  the launch-configured directory
- **Channel name sanitization**: Validated before use in file operations
- **Safe type conversion**: Property values are type-checked during merge
- **Recursive property merge**: Prevents injection via nested config overrides

## Pre-Commit Hooks

| Hook          | What It Checks                                              |
| ------------- | ----------------------------------------------------------- |
| `pre-commit`  | Scans staged files for API key patterns (`API_KEY.*=[A-Za-z0-9]{20,}`) |
| `pre-commit`  | Black formatting compliance (line-length 80)                |
| `commit-msg`  | Conventional commit format, blocks AI tool name references  |

## Git-Ignored Files

These are auto-generated — never modify or commit them:

| Pattern                | Source                    |
| ---------------------- | ------------------------- |
| `manifest-lock.json`   | `tman` dependency resolve |
| `compile_commands.json`| Build system              |
| `BUILD.gn`, `.gn`     | Build configuration       |
| `out/`, `build/`       | Build output              |
| `.ten/`                | TEN runtime files         |
| `bin/main`, `bin/worker`| Compiled binaries        |
| `.release/`            | Release packaging         |
| `node_modules/`        | JS dependencies           |
| `.env`                 | Environment secrets       |

## Files That Should Never Be Committed

- `.env` (API keys and secrets)
- `*.pem` (certificates)
- `*.pcm` (audio dumps)
- Credential files, tokens, session data

## Related Deep Dives

- [Deployment](L2/deployment.md) — Production security considerations
- [Server Architecture](L2/server_architecture.md) — Server-side validation details
