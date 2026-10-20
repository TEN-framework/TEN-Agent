# StepFun ASR Identity & Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce write-once segment identity, generation-safe mapping retirement, connect-attempt invalidation on stop, and unified normal-close — with contract tests proving ASR guide blockers from the 2026-10-20 design.

**Architecture:** Keep `_pending` deque; add bind/retire gate helpers on `TranscriptSegment`; filter `commit()` by session; defer `_retire_segment_mappings` until retirable; track connect attempt epoch + `_connect_task` in extension; route all `ConnectionClosedOK` through `_mark_normal_close()`.

**Tech Stack:** Python 3 asyncio, pytest, websockets mocks, TEN `AsyncASRBaseExtension` patterns in `stepfun_asr_python`.

**Spec:** `docs/superpowers/specs/2026-10-20-stepfun-asr-identity-lifecycle-design.md`

## Global Constraints

- Scope only `ai_agents/agents/ten_packages/extension/stepfun_asr_python/`
- No third-party state-machine library
- TDD: failing test before production change
- Conventional commits; no AI tool names in commits
- Do not commit unless the user asks (except when a plan step explicitly requires a commit and the user already authorized implementation work — prefer asking if unclear)

## File map

| File | Responsibility |
|------|----------------|
| `recognition.py` | Segment bind/retire helpers; `commit` session match; mapping retirement; `_mark_normal_close` |
| `extension.py` | Connect attempt epoch; `_connect_task` cancel on stop; gate late publish |
| `tests/test_extension.py` | Contract/regression tests (T1–T5) |
| `tests/test_recognition.py` | Unit-level recognition races if cleaner there |

---

### Task 1: Empty finalize must not claim another session's pending VAD

**Files:**
- Modify: `recognition.py` (`TranscriptSegment`, `commit`)
- Test: `tests/test_extension.py`

**Interfaces:**
- Produces: `TranscriptSegment.can_bind_finalize(session_id: str | None) -> bool`
- Produces: `commit(...)` only binds when `can_bind_finalize`; else empty path

- [ ] **Step 1: Write the failing test**

Add to `tests/test_extension.py`:

```python
@pytest.mark.asyncio
async def test_empty_finalize_does_not_claim_other_session_pending_vad():
    ext = _real_output_extension()
    recognition = StepFunASRRecognition(
        _config(server_vad=True), SimpleNamespace(), ext
    )
    recognition.websocket = FakeWebSocket()
    recognition._started = True
    recognition._generation = 1
    ext.recognition = recognition

    await recognition.send_audio(
        b"\x01\x02" * 160,
        metadata={"session_id": "session-a"},
        session_id="session-a",
    )
    await recognition._handle_message(
        {
            "type": "input_audio_buffer.speech_stopped",
            "item_id": "item-a",
            "audio_end_ms": 20,
        }
    )
    assert recognition._pending[0].session_id == "session-a"
    assert recognition._current.start == recognition._tail

    await ext._handle_finalize(
        "final-b",
        asyncio.get_running_loop().time(),
        {"session_id": "session-b"},
    )

    pending_a = recognition._pending[0]
    assert pending_a.finalize_id is None
    assert pending_a.session_id == "session-a"
    assert pending_a.metadata["session_id"] == "session-a"

    outputs = [
        json.loads(data.get_property_to_json(None)[0])
        for call in ext.ten_env.send_data.await_args_list
        for data in [call.args[0]]
        if data.get_name() in {"asr_result", "asr_finalize_end"}
    ]
    results = [item for item in outputs if "text" in item]
    finalize_ends = [item for item in outputs if "finalize_id" in item]
    assert results == [
        {
            "id": results[0]["id"],  # allow generated id if present
            "text": "",
            "final": True,
            "start_ms": 0,
            "duration_ms": 0,
            "language": "en",
            "words": [],
            "metadata": {
                "session_id": "session-b",
                "asr_info": {"finalize_id": "final-b"},
            },
        }
    ] or (
        results[0]["text"] == ""
        and results[0]["metadata"]["session_id"] == "session-b"
        and results[0]["metadata"]["asr_info"]["finalize_id"] == "final-b"
    )
    assert [item["finalize_id"] for item in finalize_ends] == ["final-b"]
```

Prefer the looser assertions on result shape (text/metadata/finalize_id) if exact payload keys differ — match existing `_real_output_extension` finalize tests.

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ai_agents/agents/ten_packages/extension/stepfun_asr_python && \
  python -m pytest tests/test_extension.py::test_empty_finalize_does_not_claim_other_session_pending_vad -v
```

Expected: FAIL — `pending_a.finalize_id` is `"final-b"` (or session overwritten).

- [ ] **Step 3: Minimal implementation**

On `TranscriptSegment`:

```python
def can_bind_finalize(self, session_id: str | None) -> bool:
    if self.published or self.finalize_id is not None:
        return False
    if self.session_id is None or session_id is None:
        return True
    return self.session_id == session_id
```

In `commit()`, change pending selection to:

```python
pending_segment = next(
    (
        segment
        for segment in reversed(self._pending)
        if segment.can_bind_finalize(session_id)
    ),
    None,
)
```

When binding, only set metadata/session if not already frozen (write-once): if `pending_segment.metadata is None` and metadata provided, set; if `pending_segment.session_id is None` and session_id provided, set; never overwrite non-None identity fields.

- [ ] **Step 4: Run test to verify it passes**

Same pytest command — Expected: PASS. Also run:

```bash
python -m pytest tests/test_extension.py::test_finalize_binds_new_current_audio_not_older_vad_segment \
  tests/test_extension.py::test_finalize_waits_for_pending_vad_result \
  tests/test_extension.py::test_empty_finalize_clears_its_ttlw_context -v
```

Expected: all PASS.

- [ ] **Step 5: Commit** (when user authorizes commits for this work)

```bash
git add recognition.py tests/test_extension.py
git commit -m "fix(asr): bind empty finalize only to matching session"
```

---

### Task 2: Preserve in-flight replay mappings for published spans

**Files:**
- Modify: `recognition.py` (`_retire_segment_mappings` call site, helpers)
- Test: `tests/test_extension.py` or `tests/test_recognition.py`

**Interfaces:**
- Produces: `TranscriptSegment.can_retire_mappings(current_generation: int) -> bool`
- Rule: do not retire mappings for a published segment that still has an `_items` entry whose item is not in `_completed_item_set` for the **current** generation's replay — simpler rule from spec: only call `_retire_segment_mappings` when no `_items` value is that segment **or** all such items are already in `_completed_item_set`.

Recommended rule (precise):

```python
def _segment_mappings_retirable(self, segment: TranscriptSegment) -> bool:
    for item, mapped in self._items.items():
        if mapped is segment and item not in self._completed_item_set:
            return False
    return True
```

In the published-prefix loop:

```python
while self._pending and self._pending[0].published:
    completed = self._pending[0]
    if not self._segment_mappings_retirable(completed):
        break
    self._pending.popleft()
    self._retire_segment_mappings(completed)
    self._base = completed.end
    self._release_confirmed_audio()
```

Note: if we break with published head still in deque, `_base` must not skip it forever — either advance `_base` without retiring maps, or keep head until retirable. Prefer: **popleft only when retirable**; until then leave published head in place (audio retention stays until maps clear). Alternate: popleft + advance `_base` but skip `_retire_segment_mappings` — choose **defer popleft** only if audio memory pressure is OK; otherwise **popleft + advance `_base` without retiring maps**.

**Chosen:** popleft + advance `_base` + release audio, but **skip** `_retire_segment_mappings` when not retirable (maps stay for replay).

```python
while self._pending and self._pending[0].published:
    completed = self._pending.popleft()
    if self._segment_mappings_retirable(completed):
        self._retire_segment_mappings(completed)
    self._base = completed.end
    self._release_confirmed_audio()
```

And when a new item is mapped to an already-published segment during replay, `_segment_for` / completed path already returns early if `segment.published` — ensure item stays in `_items` until that replay item completes.

- [ ] **Step 1: Write failing test**

Scenario: A unpublished pending, B published; simulate reconnect by clearing items, bumping generation, queueing new commit acks for both, then:

1. New acks arrive for A and B (map new item ids)
2. A's replayed final arrives → published-prefix loop would retire both if B's map was cleared
3. B's replayed final must not error

Sketch:

```python
@pytest.mark.asyncio
async def test_replay_final_for_published_span_survives_earlier_pending_final():
    callback = CapturingCallback()
    recognition = StepFunASRRecognition(
        _config(server_vad=True), SimpleNamespace(), callback
    )
    recognition.websocket = FakeWebSocket()
    recognition._started = True
    recognition._generation = 1

    # Seal A via VAD, leave unpublished
    await recognition.send_audio(b"\x01\x02" * 160, metadata={"session_id": "a"}, session_id="a")
    await recognition._handle_message(
        {"type": "input_audio_buffer.speech_stopped", "item_id": "item-a0", "audio_end_ms": 20}
    )
    seg_a = recognition._pending[0]

    # Seal and publish B
    await recognition.send_audio(b"\x03\x04" * 160, metadata={"session_id": "b"}, session_id="b")
    await recognition._handle_message(
        {"type": "input_audio_buffer.speech_stopped", "item_id": "item-b0", "audio_end_ms": 40}
    )
    seg_b = recognition._pending[1]
    await recognition._handle_message(
        {
            "type": "response.audio_transcription.completed",
            "item_id": "item-b0",
            "transcript": "b",
            "words": [{"word": "b", "start": 0.2, "end": 0.3}],
        }
    )
    assert seg_b.published is True

    # Reconnect bookkeeping
    recognition._generation = 2
    recognition._items.clear()
    recognition._item_starts.clear()
    recognition._completed_item_set.clear()
    recognition._completed_items.clear()
    recognition._awaiting_ack.clear()
    seg_a.generation = 2
    seg_b.generation = 2
    recognition._items["item-a1"] = seg_a
    recognition._items["item-b1"] = seg_b

    await recognition._handle_message(
        {
            "type": "response.audio_transcription.completed",
            "item_id": "item-a1",
            "transcript": "a",
            "words": [{"word": "a", "start": 0.0, "end": 0.1}],
        }
    )
    # B's new mapping must still resolve
    assert recognition._items.get("item-b1") is seg_b

    await recognition._handle_message(
        {
            "type": "response.audio_transcription.completed",
            "item_id": "item-b1",
            "transcript": "b",
            "words": [{"word": "b", "start": 0.2, "end": 0.3}],
        }
    )
    assert callback.errors == []
    assert any(code == "missing_commit_boundary" for _, _, code in callback.errors) is False
```

- [ ] **Step 2: Run — expect FAIL** (B mapping gone / missing_commit_boundary)

- [ ] **Step 3: Implement mapping retirement gate as above**

- [ ] **Step 4: Run — expect PASS**; re-run Task 1 tests

- [ ] **Step 5: Commit** when authorized: `fix(asr): retain item maps for in-flight replay`

---

### Task 3: Unify normal close + cancel connect attempts on stop

**Files:**
- Modify: `recognition.py` (inner `ConnectionClosedOK`, `_mark_normal_close`, `_pump_or_reconnect`)
- Modify: `extension.py` (`_connect_attempt`, `_connect_task`, `stop_connection`, `_connect_once` / `start_connection`)
- Test: `tests/test_extension.py`

**Interfaces:**
- `StepFunASRRecognition._mark_normal_close() -> None`
- `StepFunASRExtension._connect_attempt: int`
- `StepFunASRExtension._connect_task: asyncio.Task | None`
- `stop_connection` cancels `_connect_task` like `_recovery_task`

- [ ] **Step 1a: Failing test — normal close during replay sets flag**

Extend handshake tests: after `session.updated`, pump/send raises `ConnectionClosedOK`; assert `recognition.normal_close is True` and extension does not emit ASR error for that path (mirror `test_handshake_normal_close_does_not_emit_error`).

- [ ] **Step 1b: Failing test — stop cancels in-flight connect**

```python
@pytest.mark.asyncio
async def test_stop_cancels_in_flight_trigger_connect(monkeypatch):
    ext = _extension()
    ext.stopped = False
    gate = asyncio.Event()
    installed = {"ws": False}

    async def slow_connect(*_a, **_k):
        await gate.wait()
        installed["ws"] = True
        return ExhaustingWebSocket()

    # Wire recognition + patch websockets.connect; schedule start_connection as task
    # then await stop_connection before gate.set(); gate.set(); await task
    # assert installed["ws"] is False OR websocket discarded / on_connected not called
```

Fill in using existing `start_connection` + monkeypatch `websockets.connect` patterns from `test_handshake_*`.

- [ ] **Step 2: Run both — expect FAIL**

- [ ] **Step 3: Implement**

```python
def _mark_normal_close(self) -> None:
    self._normal_close = True
```

Replace every `self._normal_close = True` and the bare inner `except ConnectionClosedOK: ... return` in `start()` to call `_mark_normal_close()` first.

Extension:

```python
self._connect_attempt = 0
self._connect_task = None
```

In `start_connection` / `_connect_once`: capture `attempt = self._connect_attempt`; after `recognition.start()`, if `self.stopped or attempt != self._connect_attempt`: shutdown socket / skip ready.

Track current task: when launching connect from recovery or when `start_connection` is entered from a task that isn't recovery, set `self._connect_task = asyncio.current_task()` in try/finally clear.

`stop_connection`: bump `_connect_attempt`; cancel `_connect_task` with `_recovery_task` / `_input_task`.

Also after `websockets.connect` inside `recognition.start`, if `_closing`: close and return without publishing.

- [ ] **Step 4: Tests PASS**

- [ ] **Step 5: Commit** when authorized: `fix(asr): invalidate connect attempts on stop`

---

### Task 4: Contract coverage (status, metrics, replacement replay)

**Files:**
- Modify: `tests/test_extension.py` (use `_real_output_extension`)
- Possibly small hooks in `extension.py` only if tests cannot observe otherwise

- [ ] **Step 1: Add tests T5a–T5d** per design §3 (connection status sequence + masking; connect-delay/TTFW/TTLW JSON; two same-session cycles; retained-span replay via real `recognition.start()` replacement socket with monkeypatched `websockets.connect`, not bare `_generation = 2`)

- [ ] **Step 2: Run full package tests**

```bash
cd ai_agents/agents/ten_packages/extension/stepfun_asr_python && python -m pytest tests/ -v
```

Expected: all PASS.

- [ ] **Step 3: Document guarder evidence in PR** (run StepFun ASR guarder if env available; link logs). If guarder cannot run in this environment, note blocker and list exact command from `tasks/StepFun_ASR_share_20261016/`.

- [ ] **Step 4: Commit** when authorized: `test(asr): cover StepFun connection and replay contracts`

---

## Spec coverage check

| Spec requirement | Task |
|------------------|------|
| §1 session-matched commit / empty B | Task 1 |
| §1 mapping retirement / replay | Task 2 |
| §2 `_mark_normal_close` | Task 3 |
| §2 connect epoch / stop cancel | Task 3 |
| §3 T1–T5 + evidence | Tasks 1–4 |

## Placeholder scan

No TBD steps; test sketches may need payload-key adjustment to match `send_asr_result` actual JSON — align with existing tests in the same file.
