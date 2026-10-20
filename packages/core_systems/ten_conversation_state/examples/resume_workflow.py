#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
"""Two-process recovery demonstration with an application-owned SQLite store."""

import argparse
import asyncio
import sqlite3
from pathlib import Path

from ten_conversation_state import (
    Checkpoint,
    CheckpointManager,
    ResumeDecision,
)


class SQLiteStore:
    """Example backend; use an application-controlled path, not a client path."""

    def __init__(self, path: Path):
        self.path = path
        with sqlite3.connect(path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS checkpoints ("
                "conversation TEXT, checkpoint TEXT, payload TEXT, "
                "PRIMARY KEY (conversation, checkpoint))"
            )

    async def save(self, checkpoint):
        payload = checkpoint.to_json()

        def write():
            with sqlite3.connect(self.path) as connection:
                connection.execute(
                    "INSERT INTO checkpoints VALUES (?, ?, ?)",
                    (
                        checkpoint.conversation_id,
                        checkpoint.checkpoint_id,
                        payload,
                    ),
                )

        await asyncio.to_thread(write)

    async def load(self, conversation_id, checkpoint_id):
        def read():
            with sqlite3.connect(self.path) as connection:
                return connection.execute(
                    "SELECT payload FROM checkpoints "
                    "WHERE conversation = ? AND checkpoint = ?",
                    (conversation_id, checkpoint_id),
                ).fetchone()

        row = await asyncio.to_thread(read)
        return Checkpoint.from_json(row[0]) if row else None

    async def delete(self, conversation_id, checkpoint_id):
        def remove():
            with sqlite3.connect(self.path) as connection:
                connection.execute(
                    "DELETE FROM checkpoints "
                    "WHERE conversation = ? AND checkpoint = ?",
                    (conversation_id, checkpoint_id),
                )

        await asyncio.to_thread(remove)


class Workflow:
    """The same hooks can live on an application-owned TEN extension."""

    state_version = "1"

    def __init__(self):
        self.state = {
            "topic": "travel",
            "step": "ask_destination",
            "completed_operations": [],
        }

    async def snapshot_state(self):
        # Explicit allowlist: never include provider clients or authentication.
        return {
            key: self.state[key]
            for key in ("topic", "step", "completed_operations")
        }

    async def validate_state(self, state):
        if (
            not isinstance(state, dict)
            or set(state) != {"topic", "step", "completed_operations"}
            or state["topic"] != "travel"
            or state["step"] != "confirm_itinerary"
            or state["completed_operations"] != ["lookup:demo-trip"]
        ):
            raise ValueError("Unsupported workflow state")

    async def restore_state(self, state):
        self.state = state


async def demo_policy(_checkpoint):
    # This local demo contains only non-sensitive sample data.
    # A real app must verify the current caller's access to the conversation
    # and revalidate identity/privileges independently of checkpoint contents.
    return ResumeDecision.RESTORE


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("checkpoint", "resume"))
    parser.add_argument("database", type=Path)
    parser.add_argument("--checkpoint-id")
    args = parser.parse_args()
    if args.action == "resume" and not args.checkpoint_id:
        parser.error("resume requires --checkpoint-id")
    workflow = Workflow()
    store = await asyncio.to_thread(SQLiteStore, args.database)
    manager = CheckpointManager(store, {"workflow": workflow})
    if args.action == "checkpoint":
        # Simulate information gathering and a completed tool operation.
        workflow.state["step"] = "confirm_itinerary"
        workflow.state["completed_operations"].append("lookup:demo-trip")
        checkpoint = await manager.checkpoint("demo", ttl_seconds=3600)
        print(checkpoint.checkpoint_id)
        # Exit this process, losing every in-memory object and connection.
    else:
        decision = await manager.restore(
            "demo", args.checkpoint_id, policy=demo_policy
        )
        if decision is not ResumeDecision.RESTORE:
            raise RuntimeError(f"Cannot resume: {decision.value}")
        print(f"Continue at: {workflow.state['step']}")
        print("Completed lookup retained; no tool operation replayed.")


if __name__ == "__main__":
    asyncio.run(main())
