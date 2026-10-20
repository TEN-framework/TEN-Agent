# StepFun ASR identity & lifecycle design

Date: 2026-10-20  
Status: approved for planning (sections §1–§3 reviewed in session)  
Scope: `ai_agents/agents/ten_packages/extension/stepfun_asr_python/`  
Approach: **C — explicit identity + lifecycle state machine** (not surgical patches alone)

## Problem

Review of `6e28b29` against the ASR guide found five merge-blocking defects that share one root cause: **lifecycle identity (session / connection generation / connect attempt) is not bound to result state (pending / published / replay)**, so later work can silently rewrite earlier ownership.

| # | Severity | Symptom |
|---|----------|---------|
| 1 | P1 | Empty finalize on silent session B claims session A's pending VAD span |
| 2 | P2 | Retiring published pending mappings drops in-flight replay identities |
| 3 | P2 | Inner `ConnectionClosedOK` omits `_normal_close`; recovery close looks fatal |
| 4 | P1 | `trigger_connect` in-flight `websockets.connect()` survives `stop` and publishes late |
| 5 | P2 | Missing connection/metrics/reconnect contract tests and guarder evidence |

Guide blockers cited by review: §§5.3, 6.2–6.3, 7.1–7.2, 8.1, 9, 9.2–9.3, 11.1–11.2, 12.3, 13.1–13.2.

## Goals

- Make segment and connection identity **immutable after bind**; refuse silent reassignment.
- Encode lifecycle as **one-way phases** with gate methods, not scattered booleans.
- Invalidate and cancel **every** connection attempt on stop.
- Treat normal WebSocket close as a **single code path**.
- Prove invariants with capturing contract tests + standalone/guarder evidence on PR.

## Non-goals

- No third-party state-machine framework.
- No rewrite of `_pending` deque / journal storage model.
- No changes to StepFun ASR guarder framework itself (only satisfy its contracts).
- No fragile full-network E2E beyond existing guarder.

## Architecture

```
extension.py                     recognition.py
─────────────────                ────────────────────────────
connect attempt epoch            TranscriptSegment identity
_connect_task registry           phase: Open→Sealed→Bound→Published→Retirable
stop ⇒ bump epoch + cancel       commit() binds only matching session
status publish gated by epoch    item maps retire only when retirable
                                 _mark_normal_close() everywhere
```

Recognition owns transport/journal/segment rules. Extension owns stop epoch, connect task tracking, and whether connection-status events may publish.

---

## §1 Segment identity & lifecycle

### Invariants

1. **Write-once identity**  
   After a successful bind, `session_id`, `finalize_id`, `finalize_time`, and `metadata` are frozen. Later finalize or result routing must not overwrite them.

2. **Claim requires a key**  
   `commit(finalize_id, session_id, …)` may bind only a pending segment that satisfies all of:
   - `not published`
   - `finalize_id is None`
   - `session_id is None or session_id == requested session_id`
   - boundary semantics consistent (VAD-sealed `end`, or explicit commit span)

   Otherwise: **do not mutate any pending segment**; emit an independent empty result for that finalize (existing `empty.completed` path).

3. **One-way phases**  
   `Open → Sealed → Bound(optional finalize) → Published → Retirable`  
   Illegal transitions are rejected or no-op (duplicate published finals are discarded), never silent rewrites.

4. **Retire queue vs retire mappings**  
   Prefix of `_pending` that is `published` may still `popleft` to advance `_base` and release audio.  
   `_items` / `_item_starts` retire only when the segment is **retirable for the current connection generation** (no in-flight replay item still needs it).  
   A published span that received a new item mapping after reconnect keeps mappings; a replayed final hits “already published → remember completed + return”, and must **not** fall back to empty `_current` / `missing_commit_boundary`.

### Implementation sketch

- Add explicit `phase` (or equivalent `can_bind_finalize` / `can_retire_mappings` helpers) on `TranscriptSegment`.
- Replace the unbound reverse scan in `commit()` (`recognition.py` ~620–635) with session/boundary-filtered selection; mismatch → empty finalize ack.
- Change the published-prefix loop (`~463–466`) so mapping retirement is gated; completed-item set still short-circuits duplicate finals.
- Keep `_pending` deque; concentrate checks in small facade methods used by `commit`, `_handle_message`, and `_segment_for`.

### Acceptance (§1)

- Silent session B finalize with no new B audio: B gets empty + its own `finalize_id`/`session_id`; A's metadata/finalize untouched; emitted JSON capturable.
- A pending + B published → reconnect replays both: B's second final is non-fatal; A can still complete.

---

## §2 Connection attempt epoch & normal close

### Invariants

1. **Every connect attempt has a token**  
   Before `_connect_once` / `recognition.start()`, assign `attempt_id = ++_connect_attempt` (or a dedicated stop epoch). Semantics: “is installing this socket still allowed?”

2. **Stop invalidates all in-flight attempts**  
   On `stop_connection` / `on_stop`:
   - `stopped = True` (existing)
   - bump `_connect_attempt` / stop epoch
   - cancel + await `_recovery_task`, `_input_task`, and **`_connect_task` (or any task registered as the active connect)**
   - then `recognition.shutdown()`

3. **Late success must self-abort**  
   After `websockets.connect()` returns, and before starting the receiver or publishing connected/ready, check `stopped` or `attempt_id != current epoch`. If invalid: close the socket, do not start receiver, do not emit status.

4. **One normal-close entrypoint**  
   All `ConnectionClosedOK` paths (inner `_pump` in `start()`, `_receive_loop`, `_pump_or_reconnect`, handshake) call `_mark_normal_close()` so `_normal_close` is set. Inner handlers must not return without it.

### Implementation sketch

- Extension keeps `_connecting` for re-entrancy; add epoch check so stop-after-connect cannot publish.
- Register the task that runs connect (including base `trigger_connect` / `on_data` path) so stop can cancel it—not only `_recovery_task`.
- Recognition: unify `_mark_normal_close()`; after await connect, if `_closing` or attempt invalid, discard socket.
- Preferred minimal hook: extension passes validity callback, or stop always `shutdown()` which sets `_closing` before late install.

### Acceptance (§2)

- `trigger_connect` blocked in `connect()` then `on_stop`: no late connected/ready; attempt cancelled; no leftover receiver.
- Successful `session.updated` then `ConnectionClosedOK` during journal replay `send()`: `normal_close` true; no ASR error / no “connection ended before ready”.

---

## §3 Contract tests & evidence

### Principles

- Tests assert **§1/§2 invariants**, not private knobs (avoid directly mutating `_generation` when a real replacement socket path exists).
- Connection/metrics cases use a **capturing / real-output** fixture (`_real_output_extension()` or equivalent), not the default fixture that mocks status and connect-delay.
- Races use controllable fake sockets / pending `connect()` futures—no live network in unit tests.

### Required cases

| ID | Case | Assertions |
|----|------|------------|
| T1 | Empty B finalize while A pending (no new B audio) | B empty + own ids; A untouched; emitted JSON |
| T2 | Out-of-order original finals, ordered replay on replacement socket | B second final non-fatal; A completes; in-flight maps retained |
| T3 | `session.updated` then replay `ConnectionClosedOK` | `normal_close`; no ASR error |
| T4 | Gated `trigger_connect` vs `on_stop` | No late status; connect cancelled |
| T5a | Successful connection-status sequence | Ordered status; credential masking |
| T5b | connect-delay / TTFW / TTLW | Real JSON + session metadata |
| T5c | Two complete same-session cycles | Timeline continuity; no finalize/session bleed |
| T5d | Retained-span replay via connection replacement | Real `start()` / socket path |

Tighten existing finalize/handshake tests if they currently allow cross-session bind.

### Merge evidence

PR must link:

1. Standalone: `stepfun_asr_python` unit tests green (command + log/CI link).
2. StepFun ASR guarder: passing run on current head (task artifact or CI link).

---

## Mapping review FAIL → design

| Checklist area | Fixed by |
|----------------|----------|
| Lifecycle / Connection state (#4) | §2 attempt epoch + cancel |
| Buffering / Finalize / Result shape / Metrics reassignment (#1) | §1 bind rules + empty path |
| Reconnect fatal / normal close error (#2, #3) | §1 mapping retirement + §2 `_mark_normal_close` |
| Tests / metrics coverage (#5) | §3 |

## Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Phase enum drifts from `published` flag | Prefer helpers derived from one field, or keep `published` as Published+ projection |
| Cancel connect races with reconnect loop | Single owner: stop bumps epoch; reconnect checks epoch before `_connect_once` |
| Over-filtering commit leaves VAD span orphaned | Bind allows `session_id is None` on sealed VAD when finalize carries the session; document in tests T1 |

## Implementation order (for later plan)

1. §1 segment bind + mapping retirement (unblocks #1/#2).
2. §2 normal close + connect epoch/stop (unblocks #3/#4).
3. §3 tests + guarder evidence (unblocks #5).

## Open points resolved in session

- Approach: **C** (identity + lifecycle), not A/B.
- Sections §1–§3 approved before this document was written.
