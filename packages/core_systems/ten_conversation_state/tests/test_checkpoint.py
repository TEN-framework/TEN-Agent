#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
import json
import unittest
from dataclasses import replace

from ten_conversation_state import (
    Checkpoint,
    CheckpointManager,
    InMemoryCheckpointStore,
    RestoreError,
    ResumeDecision,
)


async def allow(_checkpoint):
    return ResumeDecision.RESTORE


class Participant:
    state_version = "1"

    def __init__(self, state=None):
        self.state = state if state is not None else {"step": 0}
        self.restores = 0
        self.invalid = False
        self.fail = False

    async def snapshot_state(self):
        return self.state

    async def validate_state(self, state):
        if self.invalid or not isinstance(state, dict):
            raise ValueError("Invalid workflow")
        # Even accidental mutation during validation must not change restore.
        state["validation_only"] = True

    async def restore_state(self, state):
        if self.fail:
            raise RuntimeError("Apply failed")
        self.state = state
        self.restores += 1


class CheckpointTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.now = 100.0

        class RecordingStore(InMemoryCheckpointStore):
            def __init__(self):
                super().__init__()
                self.saved = []

            async def save(self, checkpoint):
                await super().save(checkpoint)
                self.saved.append(checkpoint.checkpoint_id)

        self.store = RecordingStore()
        self.workflow = Participant({"step": 2, "results": ["verified"]})
        self.manager = self.manager_for({"workflow": self.workflow})

    def manager_for(self, participants):
        return CheckpointManager(
            self.store, participants, clock=lambda: self.now
        )

    async def resume(self, manager, checkpoint, policy=allow):
        return await manager.restore(
            "conversation", checkpoint.checkpoint_id, policy=policy
        )

    async def test_new_session_restores_completed_work(self):
        checkpoint = await self.manager.checkpoint("conversation")
        new_workflow = Participant()
        manager = self.manager_for({"workflow": new_workflow})
        self.assertEqual(
            await self.resume(manager, checkpoint), ResumeDecision.RESTORE
        )
        self.assertEqual(new_workflow.state, self.workflow.state)
        self.assertEqual(new_workflow.restores, 1)

    async def test_snapshot_and_store_are_isolated(self):
        checkpoint = await self.manager.checkpoint("conversation")
        self.workflow.state["results"].append("later")
        checkpoint.components["workflow"]["state"]["step"] = 99
        loaded = await self.store.load("conversation", checkpoint.checkpoint_id)
        self.assertEqual(loaded.components["workflow"]["state"]["step"], 2)
        self.assertEqual(
            loaded.components["workflow"]["state"]["results"], ["verified"]
        )
        loaded.components.clear()
        self.assertTrue(
            (
                await self.store.load("conversation", checkpoint.checkpoint_id)
            ).components
        )

    async def test_json_roundtrip(self):
        checkpoint = await self.manager.checkpoint(
            "conversation", ttl_seconds=5
        )
        self.assertEqual(Checkpoint.from_json(checkpoint.to_json()), checkpoint)

    async def test_invalid_json_values_never_saved(self):
        cyclic = []
        cyclic.append(cyclic)
        for invalid in (
            object(),
            b"audio",
            (1, 2),
            {1: "key"},
            float("nan"),
            float("inf"),
            cyclic,
        ):
            with self.subTest(kind=type(invalid)):
                self.workflow.state = {"value": invalid}
                with self.assertRaises(ValueError):
                    await self.manager.checkpoint("conversation")
        self.assertEqual(self.store.saved, [])

    async def test_snapshot_failure_never_saves_partial_checkpoint(self):
        class Broken(Participant):
            async def snapshot_state(self):
                raise RuntimeError("Snapshot failed")

        manager = self.manager_for({"first": self.workflow, "second": Broken()})
        with self.assertRaises(RuntimeError):
            await manager.checkpoint("conversation")
        self.assertEqual(self.store.saved, [])

    async def test_policy_blocks_all_mutation(self):
        checkpoint = await self.manager.checkpoint("conversation")
        for decision in (ResumeDecision.REVALIDATE, ResumeDecision.EXPIRED):

            async def policy(_checkpoint, decision=decision):
                return decision

            self.assertEqual(
                await self.resume(self.manager, checkpoint, policy), decision
            )
        self.assertEqual(self.workflow.restores, 0)

    async def test_policy_cannot_rewrite_state(self):
        checkpoint = await self.manager.checkpoint("conversation")

        async def policy(value):
            value.components["workflow"]["state"]["step"] = 999
            return ResumeDecision.RESTORE

        await self.resume(self.manager, checkpoint, policy)
        self.assertEqual(self.workflow.state["step"], 2)

    async def test_invalid_or_failed_policy_blocks_restore(self):
        checkpoint = await self.manager.checkpoint("conversation")

        async def invalid(_checkpoint):
            return "restore"

        async def failed(_checkpoint):
            raise RuntimeError("Authorization unavailable")

        for policy, error in ((invalid, ValueError), (failed, RuntimeError)):
            with self.assertRaises(error):
                await self.resume(self.manager, checkpoint, policy)
        self.assertEqual(self.workflow.restores, 0)

    async def test_expiration_boundary_skips_policy(self):
        checkpoint = await self.manager.checkpoint(
            "conversation", ttl_seconds=5
        )
        self.now = 105

        async def policy(_checkpoint):
            self.fail("Expired checkpoint must not reach policy")

        self.assertEqual(
            await self.resume(self.manager, checkpoint, policy),
            ResumeDecision.EXPIRED,
        )
        self.assertEqual(self.workflow.restores, 0)

    async def test_expiration_during_policy_or_validation(self):
        checkpoint = await self.manager.checkpoint(
            "conversation", ttl_seconds=5
        )

        async def slow_policy(_checkpoint):
            self.now = 105
            return ResumeDecision.RESTORE

        self.assertEqual(
            await self.resume(self.manager, checkpoint, slow_policy),
            ResumeDecision.EXPIRED,
        )
        self.now = 100

        async def slow_validation(_state):
            self.now = 105

        self.workflow.validate_state = slow_validation
        self.assertEqual(
            await self.resume(self.manager, checkpoint), ResumeDecision.EXPIRED
        )
        self.assertEqual(self.workflow.restores, 0)

    async def test_missing_or_wrong_conversation(self):
        checkpoint = await self.manager.checkpoint("conversation")
        with self.assertRaises(LookupError):
            await self.manager.restore(
                "other", checkpoint.checkpoint_id, policy=allow
            )
        await self.store.delete("conversation", checkpoint.checkpoint_id)
        await self.store.delete("conversation", checkpoint.checkpoint_id)
        with self.assertRaises(LookupError):
            await self.resume(self.manager, checkpoint)

    async def test_backend_identity_mismatch_is_rejected(self):
        checkpoint = await self.manager.checkpoint("conversation")

        async def wrong_identity(_conversation_id, _checkpoint_id):
            return replace(checkpoint, conversation_id="other")

        self.store.load = wrong_identity
        with self.assertRaisesRegex(ValueError, "identity"):
            await self.resume(self.manager, checkpoint)
        self.assertEqual(self.workflow.restores, 0)

    async def test_participant_and_version_mismatch(self):
        checkpoint = await self.manager.checkpoint("conversation")
        for participants in ({}, {"other": self.workflow}):
            with self.assertRaisesRegex(ValueError, "participant"):
                await self.resume(self.manager_for(participants), checkpoint)
        self.workflow.state_version = "2"
        with self.assertRaisesRegex(ValueError, "version"):
            await self.resume(self.manager, checkpoint)
        self.assertEqual(self.workflow.restores, 0)

    async def test_all_validation_precedes_restore(self):
        second = Participant()
        manager = self.manager_for({"first": self.workflow, "second": second})
        checkpoint = await manager.checkpoint("conversation")
        second.invalid = True
        with self.assertRaises(ValueError):
            await self.resume(manager, checkpoint)
        self.assertEqual(self.workflow.restores, 0)

    async def test_partial_restore_reports_failure(self):
        second = Participant()
        manager = self.manager_for({"first": self.workflow, "second": second})
        checkpoint = await manager.checkpoint("conversation")
        second.fail = True
        with self.assertRaises(RestoreError) as caught:
            await self.resume(manager, checkpoint)
        self.assertEqual(caught.exception.component, "second")
        self.assertEqual(caught.exception.restored, ("first",))

    async def test_bad_metadata_is_rejected(self):
        checkpoint = await self.manager.checkpoint("conversation")
        for field, value in (
            ("schema_version", 2),
            ("schema_version", True),
            ("created_at", float("inf")),
            ("expires_at", 99),
            ("conversation_id", ""),
            ("components", []),
        ):
            payload = json.loads(checkpoint.to_json())
            payload[field] = value
            with self.subTest(field=field, value=value):
                with self.assertRaises(ValueError):
                    Checkpoint.from_json(json.dumps(payload))
        with self.assertRaises(ValueError):
            Checkpoint.from_json('{"schema_version": 1}')

    async def test_invalid_ttl_and_identifiers(self):
        for ttl in (-1, 0, True, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                await self.manager.checkpoint("conversation", ttl_seconds=ttl)
        with self.assertRaises(ValueError):
            await self.manager.checkpoint("")
        with self.assertRaises(ValueError):
            self.manager_for({"": self.workflow})

    async def test_cancellation_propagates_and_releases_lock(self):
        checkpoint = await self.manager.checkpoint("conversation")
        entered = asyncio.Event()

        async def wait_policy(_checkpoint):
            entered.set()
            await asyncio.Event().wait()

        task = asyncio.create_task(
            self.resume(self.manager, checkpoint, wait_policy)
        )
        await entered.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(self.workflow.restores, 0)
        await asyncio.wait_for(self.resume(self.manager, checkpoint), timeout=1)

    async def test_storage_errors_propagate(self):
        class UnavailableStore:
            async def save(self, checkpoint):
                raise OSError("Storage unavailable")

            async def load(self, conversation_id, checkpoint_id):
                raise OSError("Storage unavailable")

        manager = CheckpointManager(
            UnavailableStore(), {"workflow": self.workflow}
        )
        with self.assertRaises(OSError):
            await manager.checkpoint("conversation")
        with self.assertRaises(OSError):
            await manager.restore("conversation", "id", policy=allow)
        self.assertEqual(self.workflow.restores, 0)

    async def test_same_manager_serializes_operations(self):
        checkpoint = await self.manager.checkpoint("conversation")
        entered = asyncio.Event()
        release = asyncio.Event()

        async def policy(_checkpoint):
            entered.set()
            await release.wait()
            return ResumeDecision.RESTORE

        restoring = asyncio.create_task(
            self.resume(self.manager, checkpoint, policy)
        )
        await entered.wait()
        snapshotting = asyncio.create_task(
            self.manager.checkpoint("conversation")
        )
        await asyncio.sleep(0)
        self.assertFalse(snapshotting.done())
        release.set()
        await asyncio.wait_for(asyncio.gather(restoring, snapshotting), 1)


if __name__ == "__main__":
    unittest.main()
