# Conversation checkpoint and resume

An opt-in Python proof of concept for
[issue #2340](https://github.com/TEN-framework/ten-framework/issues/2340).
Applications explicitly capture JSON state and restore it into a new session.
The package has no runtime or vendor dependencies and does not change existing
extension lifecycle behavior. Its API is experimental pending maintainer review.

## Install and run

From the repository root, using Python 3.10 or newer:

```sh
python -m pip install ./packages/core_systems/ten_conversation_state
python -m unittest discover -s packages/core_systems/ten_conversation_state/tests -v
```

Alternatively, set `PYTHONPATH=packages/core_systems/ten_conversation_state`
to run the tests and example directly from source.

The example uses an application-owned SQLite backend. Run these as **separate
processes**, copying the checkpoint ID printed by the first command:

```sh
python packages/core_systems/ten_conversation_state/examples/resume_workflow.py checkpoint /tmp/conversation.db
python packages/core_systems/ten_conversation_state/examples/resume_workflow.py resume /tmp/conversation.db --checkpoint-id <printed-id>
```

On Windows, use a writable path such as `conversation.db`. The first process
simulates gathering information and completing a tool lookup, saves a checkpoint,
then exits. The second process creates a fresh workflow and resumes at
`confirm_itinerary`, retaining the completed lookup reference without replaying it.
This demonstrates logical state recovery after a process interruption; it does not
open or reconnect a WebRTC, WebSocket, or SIP transport.

## Participants and TEN integration

Register an explicit mapping of stable component names to objects implementing:

- `state_version: str`: application-defined schema version.
- `async snapshot_state()`: return allowlisted JSON state.
- `async validate_state(state)`: validate without mutating live state.
- `async restore_state(state)`: apply state without replaying tool side effects.

An application-owned `AsyncExtension` can implement these hooks and construct a
`CheckpointManager(store, {"workflow": self})` during `on_init`. Call
`manager.checkpoint(conversation_id, ttl_seconds=3600)` at an explicit workflow
boundary. In a fresh extension, await
`manager.restore(conversation_id, checkpoint_id, policy=resume_policy)` after
configuration and before accepting new input or sending a greeting. Handle the
returned decision before processing audio or user requests. Existing third-party
extensions do not participate automatically; use adapters for their state APIs.

The application owns orchestration. Pause input and wait for in-flight tool calls
to complete before snapshotting or restoring. A manager serializes its own calls
on one event loop, but cannot pause extensions or provide a distributed snapshot.
Do not pass raw extension instances across runtime threads: an adapter must route
snapshot/validate/restore commands onto the owning extension's loop using TEN
messages. This initial package does not define graph-wide commands or automatic
disconnect/reconnect hooks.

## Resume policy

Every restore requires an async policy receiving a detached checkpoint copy:

```python
async def resume_policy(checkpoint):
    if not await application.authorized_for(checkpoint.conversation_id):
        return ResumeDecision.REVALIDATE
    return ResumeDecision.RESTORE
```

Import `ResumeDecision` from `ten_conversation_state`. `application` above is the
application's own authorization service, bound to the current caller.

`RESTORE` permits validation and application of state. `REVALIDATE` and `EXPIRED`
leave all participants untouched. After revalidation succeeds, the application
can explicitly retry restore with a policy that checks the fresh authorization.
Policies may reject an entire checkpoint; selective field migrations or redaction
must happen explicitly in application-owned state before checkpointing.

Expiration is enforced before policy execution and checked again after policy and
validation complete. An expired checkpoint cannot be approved by a policy.
Conversation ID and checkpoint ID must match the request. IDs are lookup keys,
not authorization credentials. Authenticate and authorize the current caller
independently; never restore authentication or privileges from saved state.

## Format, storage, and failure behavior

The version 1 envelope contains `conversation_id`, a UUID `checkpoint_id`, UTC Unix
`created_at` and optional `expires_at`, `schema_version`, and `components`. Each
component has a `version` and `state`. Only JSON objects with string keys, arrays,
strings, booleans, null, integers, and finite floats are accepted. Tuples, bytes,
cycles, sockets, provider clients, and arbitrary objects are rejected. JSON
validation cannot detect secrets: participants must explicitly exclude them.

Implement `CheckpointStore.save`, `load`, and `delete` to use a database, Redis,
object storage, or application persistence. Store a complete validated envelope
atomically; `Checkpoint.to_json()` and `Checkpoint.from_json()` provide the wire
format. `load` returns `None` for a missing key. Backend errors propagate to the
caller. The memory store isolates objects but does not survive a process restart.
Storage access control, encryption, retention, size limits, expired-checkpoint
cleanup, and concurrent-writer ownership belong to the application/backend.

Unknown envelope versions, component versions, or participant sets are rejected
before restore. Migrations are application-owned. All participants validate
before any restore hook runs. A failing restore hook raises `RestoreError` with
the failed `component` and the names already `restored`; there is no rollback of
arbitrary extension state. Discard that new session and construct fresh
participants before retrying. Cancellation propagates and may also leave a partial
restore; discard the session in that case. Do not expose a session until restore
has completed successfully.

Checkpointing does not guarantee exactly-once tool execution. Preserve operation
IDs and use application-level idempotency for external side effects. Automatic
scheduling, cross-agent migration, distributed failover, provider conversation
recreation, and automatic transport reconnection are outside this initial scope.
