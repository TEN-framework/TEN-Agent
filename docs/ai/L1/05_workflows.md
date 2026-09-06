# 05 Workflows

> Step-by-step guides for common development tasks.

## Create a New TTS / ASR / LLM Extension

**Fastest path**: Copy a similar extension and adapt it.

| Type        | Copy From                  | Base Class                  |
| ----------- | -------------------------- | --------------------------- |
| TTS (HTTP)  | `rime_http_tts`            | `AsyncTTS2HttpExtension`    |
| TTS (WS)    | `deepgram_tts`             | `AsyncTTS2BaseExtension`    |
| ASR         | `deepgram_asr_python`      | `AsyncASRBaseExtension`     |
| LLM         | `openai_llm2_python`       | `AsyncLLMBaseExtension`     |

```bash
cp -r agents/ten_packages/extension/<existing_tts> \
  agents/ten_packages/extension/my_vendor_tts
```

Then:
1. Rename addon decorator, class names, `manifest.json` `name` field
2. Keep vendor config in `params`; extract secrets for auth and forward the rest to the vendor request layer
3. Implement the abstract methods for your vendor API
4. Create `tests/configs/` with required config files (see below)
5. Run guarder tests: `task tts-guarder-test EXTENSION=my_vendor_tts`
6. Run formatter: `task format`

**Typical required test config files** for TTS: `property_basic_audio_setting1.json`,
`property_basic_audio_setting2.json`, `property_dump.json`, `property_miss_required.json`,
`property_invalid.json`

Some extensions also keep `property.json` as a default valid config, but the exact
set depends on the extension template and guarder harness in use.

Optional / vendor-dependent TTS configs:
- `property_subtitle_alignment.json` if the vendor emits word/segment timestamps

**Required test config files** for ASR: `property_en.json`, `property_zh.json`,
`property_invalid.json`, `property_dump.json`

For full walkthrough with code and guarder expectations, see
[Extension Development](L2/extension_development.md) and [Testing](L2/testing.md).

### New ASR/TTS Extension Checklist

Use one recent strong example as the main template, not just any extension of
the same type.

| Type | Strong Template | Why |
| ---- | --------------- | --- |
| TTS (WS) | `deepgram_tts` | Better lifecycle and standalone test coverage |
| ASR | `openai_asr_python` | Stronger result-shape testing than thinner templates |

Minimum end-to-end steps:
1. Verify the vendor wire contract first: endpoint, event names, payload encoding, finalize primitive.
2. Copy a recent extension with the same transport shape.
3. Implement config loading, secret redaction, and `config:` logging.
4. Implement error classification and `vendor_info`.
5. Add standalone tests before running guarders.
6. Run guarders sequentially, not in parallel, inside the same container.
7. Add README and example graph wiring only after the extension tests are green.

## Add Extension to a Graph

1. **Add node** to `predefined_graphs[].graph.nodes[]` in the example's `tenapp/property.json`:
   ```json
   {"type": "extension", "name": "my_tts", "addon": "my_tts_python",
    "extension_group": "tts",
    "property": {"params": {"api_key": "${env:MY_API_KEY}"}}}
   ```

2. **Add connections** — wire data flow between extensions:
   ```json
   {"extension": "my_tts",
    "data": [{"name": "tts_text_input", "source": [{"extension": "main"}]}],
    "audio_frame": [{"name": "pcm_frame", "dest": [{"extension": "agora_rtc"}]}]}
   ```

3. **Add dependency** to example `tenapp/manifest.json` (local extensions use path):
   ```json
   {"path": "../../../ten_packages/extension/my_tts_python"}
   ```

4. **Install** with `task install` (not bare `tman install` — the latter can wipe `bin/worker`).

5. **Nuclear restart** — required when graphs are added/removed. See
   [Setup → Restart Procedures](01_setup.md#restart-procedures) for the exact
   command sequence.

See [Graph Configuration](L2/graph_configuration.md) for connection types and
routing patterns. When adding a TTS vendor, copy a confirmed working voice graph and
preserve its routing model. Some shipped graphs rely on explicit message connections,
while others keep part of the orchestration inside `main_control`.

**For complex multi-graph setups** (A/B testing vendors, avatar variants), use
`rebuild_property.py` instead of hand-editing. See
[Generating property.json](L2/graph_configuration.md#generating-propertyjson-with-rebuild_propertypy).

## Customize the Main Extension

The "main" extension orchestrates agent behavior (greetings, tool routing, interruption).
Three implementation variants exist:

| Variant              | File                  | Use Case                        |
| -------------------- | --------------------- | ------------------------------- |
| Python Cascade       | `main_cascade_python` | ASR → LLM → TTS pipeline       |
| Python Realtime V2V  | `main_realtime_python`| OpenAI Realtime API (voice-to-voice) |
| Node.js Cascade      | `main_nodejs`         | TypeScript implementation       |

Modify `on_data()` to change event routing, `on_cmd()` for tool handling.

## Run Tests

```bash
# Standalone (single extension, with install)
sudo docker exec ten_agent_dev bash -c \
  "cd /app && task test-extension EXTENSION=agents/ten_packages/extension/<ext>"

# Integration guarder (ASR or TTS — run sequentially, not in parallel)
sudo docker exec ten_agent_dev bash -c \
  "cd /app && task tts-guarder-test EXTENSION=<ext> CONFIG_DIR=tests/configs"
```

Other variants (`task test`, `task test-extension-no-install`, `task asr-guarder-test`) and
debugging guidance live in [Testing](L2/testing.md).

## Restart After Changes

| What Changed                    | Action                                               |
| ------------------------------- | ---------------------------------------------------- |
| `property.json` (graphs added)  | Nuclear restart (kill all, remove lock, task run)    |
| `property.json` (config only)   | No restart needed (loaded per session)               |
| `.env`                          | `docker compose down && docker compose up -d` + deps |
| Python code                     | Restart server only                                  |
| Go code                         | `task install` then restart server                   |
| Container restart               | Reinstall Python deps, then `task run`               |

## Build and Install

Always prefer `task install` over bare `tman install`:

```bash
sudo docker exec ten_agent_dev bash -c \
  "cd /app/agents/examples/<example> && task install"
```

Python-deps-only and `tman install` variants are in
[Setup → Install and Run](01_setup.md#install-and-run).

## Update Extension Code in Running Container

See [Operations and Restarts](L2/operations_restarts.md) for `docker cp` syntax,
symlink verification, and restart steps.

## Pre-Commit / Pre-Push Checks

Run **all** of these before pushing — each maps to a CI job that blocks merge,
and there are no local hooks for most of them, so CI is the first thing that
catches a miss. For an extension change under
`agents/ten_packages/extension/<ext>/`:

```bash
# 1. Format + static checks (CI: task check, task lint)
sudo docker exec ten_agent_dev bash -c \
  "cd /app && task format && task check && task lint"
# task lint / task lint-extension in-container ALWAYS exits non-zero with
# E0401 import-errors — the runtime imports only resolve in CI. Judge by
# comparing against a known CI-green extension (e.g. xai_asr_python shows
# the same E0401s); only warnings beyond that baseline are real findings.

# 2. Standalone tests for the extension
sudo docker exec ten_agent_dev bash -c \
  "cd /app && task test-extension EXTENSION=agents/ten_packages/extension/<ext>"

# 3. Guarder tests against the real vendor API (TTS shown; ASR uses asr-guarder-test)
sudo docker exec ten_agent_dev bash -c \
  "cd /app && task tts-guarder-test EXTENSION=<ext> CONFIG_DIR=tests/configs"
```

Then verify **commit messages** — a separate CI job
(`Lint Commit Messages / commitlint`) runs `@commitlint/config-conventional`
on every commit in the PR, with **no local hook**. The usual trip-up is
`body-max-line-length` (≤100 chars per body line) — hard-wrap the body and use
`git commit -F msg.txt`. Full rules and a self-check script:
[Conventions → Commit Messages](04_conventions.md#commit-messages).

Checklist (all must be green before `git push`):

| Gate | Command / rule | CI job |
| ---- | -------------- | ------ |
| Black format | `task check` (`--line-length 80`) | format check |
| Pylint | `task lint` (any warning is fatal) | lint |
| Standalone tests | `task test-extension EXTENSION=...` | per-extension tests |
| Guarder tests | `task tts-guarder-test` / `task asr-guarder-test` | guarder |
| Commit messages | conventional + body lines ≤100 | commitlint |

> Note: a stale `.ten/` left in an extension dir (e.g. from a prior
> `tman install --standalone`) makes `task check` report spurious reformatting
> and breaks the next standalone install with a symlink error. Remove it
> (`rm -rf <ext>/.ten`) before re-running.

## Related Deep Dives

- [Extension Development](L2/extension_development.md) — Full extension creation with code examples
- [Graph Configuration](L2/graph_configuration.md) — Connection wiring and routing patterns
- [Testing](L2/testing.md) — Test infrastructure, guarder tests, debugging
- [Operations and Restarts](L2/operations_restarts.md) — Full restart procedures, recovery
