#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
"""Explicit, application-controlled snapshots; no runtime objects or transport."""

import asyncio
import json
import math
import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Awaitable, Callable, Mapping, Protocol
from uuid import uuid4


def _json_copy(value: Any) -> Any:
    """Reject lossy JSON coercions, non-finite numbers and runtime objects."""

    def validate(item: Any) -> None:
        if item is None or type(item) in (str, bool, int):
            return
        if type(item) is float and math.isfinite(item):
            return
        if type(item) is list:
            for child in item:
                validate(child)
            return
        if type(item) is dict and all(type(k) is str for k in item):
            for child in item.values():
                validate(child)
            return
        raise ValueError("State must contain only finite JSON values")

    try:
        validate(value)
        return json.loads(json.dumps(value, allow_nan=False))
    except RecursionError as exc:
        raise ValueError("State must not contain cycles") from exc


def _identifier(value: Any) -> None:
    if type(value) is not str or not value.strip():
        raise ValueError("Identifiers must be non-empty strings")


def _timestamp(value: Any) -> None:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Timestamps must be finite numbers")


@dataclass(frozen=True)
class Checkpoint:
    """Version 1 envelope; timestamps are Unix seconds in UTC."""

    conversation_id: str
    checkpoint_id: str
    created_at: float
    expires_at: float | None
    components: dict[str, dict[str, Any]]
    schema_version: int = 1

    def to_json(self) -> str:
        self.validate()
        return json.dumps(asdict(self), allow_nan=False)

    @classmethod
    def from_json(cls, payload: str) -> "Checkpoint":
        value = json.loads(payload)
        fields = {
            "conversation_id",
            "checkpoint_id",
            "created_at",
            "expires_at",
            "components",
            "schema_version",
        }
        if type(value) is not dict or set(value) != fields:
            raise ValueError("Invalid checkpoint envelope")
        checkpoint = cls(**value)
        checkpoint.validate()
        return checkpoint

    def validate(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("Unsupported checkpoint schema version")
        _identifier(self.conversation_id)
        _identifier(self.checkpoint_id)
        _timestamp(self.created_at)
        if self.expires_at is not None:
            _timestamp(self.expires_at)
            if self.expires_at <= self.created_at:
                raise ValueError("Expiration must follow creation")
        if type(self.components) is not dict:
            raise ValueError("Components must be an object")
        for name, component in self.components.items():
            _identifier(name)
            if type(component) is not dict or set(component) != {
                "version",
                "state",
            }:
                raise ValueError("Invalid component envelope")
            _identifier(component["version"])
            _json_copy(component["state"])


class StateParticipant(Protocol):
    """An explicitly registered application component or extension adapter."""

    state_version: str

    async def snapshot_state(self) -> Any:
        """Return only allowlisted JSON state at an application safe point."""
        ...

    async def validate_state(self, state: Any) -> None:
        """Check state without mutation; raise if it cannot be restored."""
        ...

    async def restore_state(self, state: Any) -> None:
        """Apply validated state without replaying external side effects."""
        ...


class CheckpointStore(Protocol):
    """Backends must atomically save each complete envelope, or raise."""

    async def save(self, checkpoint: Checkpoint) -> None: ...

    async def load(
        self, conversation_id: str, checkpoint_id: str
    ) -> Checkpoint | None: ...

    async def delete(
        self, conversation_id: str, checkpoint_id: str
    ) -> None: ...


class InMemoryCheckpointStore:
    """Development store. State does not survive process termination."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], str] = {}

    async def save(self, checkpoint: Checkpoint) -> None:
        self._entries[
            (checkpoint.conversation_id, checkpoint.checkpoint_id)
        ] = checkpoint.to_json()

    async def load(
        self, conversation_id: str, checkpoint_id: str
    ) -> Checkpoint | None:
        payload = self._entries.get((conversation_id, checkpoint_id))
        return Checkpoint.from_json(payload) if payload is not None else None

    async def delete(self, conversation_id: str, checkpoint_id: str) -> None:
        self._entries.pop((conversation_id, checkpoint_id), None)


class ResumeDecision(Enum):
    RESTORE = "restore"
    REVALIDATE = "revalidate"
    EXPIRED = "expired"


ResumePolicy = Callable[[Checkpoint], Awaitable[ResumeDecision]]


class RestoreError(RuntimeError):
    """A hook failed; discard the new session because it may be partial."""

    def __init__(self, component: str, restored: tuple[str, ...]) -> None:
        super().__init__(f"Restore failed for component {component!r}")
        self.component = component
        self.restored = restored


class CheckpointManager:
    """Coordinate a fixed set of participants on one asyncio event loop."""

    def __init__(
        self,
        store: CheckpointStore,
        participants: Mapping[str, StateParticipant],
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._store = store
        self._participants = dict(participants)
        for name, participant in self._participants.items():
            _identifier(name)
            _identifier(participant.state_version)
        self._clock = clock
        self._lock = asyncio.Lock()

    async def checkpoint(
        self, conversation_id: str, *, ttl_seconds: float | None = None
    ) -> Checkpoint:
        _identifier(conversation_id)
        if ttl_seconds is not None:
            _timestamp(ttl_seconds)
            if ttl_seconds <= 0:
                raise ValueError("TTL must be positive")
        async with self._lock:
            created_at = self._clock()
            components = {}
            for name, participant in self._participants.items():
                components[name] = {
                    "version": participant.state_version,
                    "state": _json_copy(await participant.snapshot_state()),
                }
            checkpoint = Checkpoint(
                conversation_id=conversation_id,
                checkpoint_id=str(uuid4()),
                created_at=created_at,
                expires_at=(
                    created_at + ttl_seconds
                    if ttl_seconds is not None
                    else None
                ),
                components=components,
            )
            # Detach the returned checkpoint from backend-owned objects.
            await self._store.save(Checkpoint.from_json(checkpoint.to_json()))
            return checkpoint

    async def restore(
        self,
        conversation_id: str,
        checkpoint_id: str,
        *,
        policy: ResumePolicy,
    ) -> ResumeDecision:
        _identifier(conversation_id)
        _identifier(checkpoint_id)
        async with self._lock:
            checkpoint = await self._store.load(conversation_id, checkpoint_id)
            if checkpoint is None:
                raise LookupError("Checkpoint not found")
            checkpoint = Checkpoint.from_json(checkpoint.to_json())
            if (checkpoint.conversation_id, checkpoint.checkpoint_id) != (
                conversation_id,
                checkpoint_id,
            ):
                raise ValueError("Checkpoint identity mismatch")
            if self._expired(checkpoint):
                return ResumeDecision.EXPIRED
            if set(checkpoint.components) != set(self._participants):
                raise ValueError("Checkpoint participant set mismatch")
            for name, participant in self._participants.items():
                if checkpoint.components[name]["version"] != (
                    participant.state_version
                ):
                    raise ValueError(f"State version mismatch for {name!r}")
            # Policies receive an isolated copy and cannot rewrite stored state.
            decision = await policy(Checkpoint.from_json(checkpoint.to_json()))
            if not isinstance(decision, ResumeDecision):
                raise ValueError("Policy must return a ResumeDecision")
            if self._expired(checkpoint):
                return ResumeDecision.EXPIRED
            if decision is not ResumeDecision.RESTORE:
                return decision
            # Validate every participant before applying any state.
            for name, participant in self._participants.items():
                await participant.validate_state(
                    _json_copy(checkpoint.components[name]["state"])
                )
            if self._expired(checkpoint):
                return ResumeDecision.EXPIRED
            restored = []
            for name, participant in self._participants.items():
                try:
                    await participant.restore_state(
                        _json_copy(checkpoint.components[name]["state"])
                    )
                except Exception as exc:
                    raise RestoreError(name, tuple(restored)) from exc
                restored.append(name)
            return ResumeDecision.RESTORE

    def _expired(self, checkpoint: Checkpoint) -> bool:
        now = self._clock()
        _timestamp(now)
        return (
            checkpoint.expires_at is not None and now >= checkpoint.expires_at
        )
