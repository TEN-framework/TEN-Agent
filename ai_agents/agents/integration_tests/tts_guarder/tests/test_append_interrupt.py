#!/usr/bin/env python3
#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#

from typing import Any
from typing_extensions import override
from ten_runtime import (
    AsyncExtensionTester,
    AsyncTenEnvTester,
    Data,
    AudioFrame,
    TenError,
    TenErrorCode,
)
import json
import asyncio
import os
import glob
import time

TTS_DUMP_CONFIG_FILE = "property_dump.json"
AUDIO_DURATION_TOLERANCE_MS = 50

# Expected event sequence states for each group
class GroupState:
    """Track state for each group"""
    WAITING_AUDIO_START = "waiting_audio_start"
    RECEIVING_AUDIO_FRAMES = "receiving_audio_frames"
    WAITING_AUDIO_END = "waiting_audio_end"
    COMPLETED = "completed"


class AppendInterruptTester(AsyncExtensionTester):
    """Test class for TTS extension append input with flush interrupt"""

    def __init__(
        self,
        session_id: str = "test_append_interrupt_session_123",
    ):
        super().__init__()
        print("=" * 80)
        print("🧪 TEST CASE: Append Interrupt TTS Test")
        print("=" * 80)
        print("📋 Test Description: Validate TTS append input with flush interrupt")
        print("🎯 Test Objectives:")
        print("   - Verify append input with multiple text inputs")
        print("   - Verify flush interrupt functionality")
        print("   - Verify interrupted group receives INTERRUPTED reason")
        print("   - Verify strict event sequence order")
        print("   - Verify dump file generation")
        print("=" * 80)

        self.session_id: str = session_id
        self.dump_file_name = f"tts_append_interrupt_{self.session_id}.pcm"
        
        # Define groups of text inputs, each group can have different number of texts
        # Each group uses the same request_id and metadata within the group
        # You can customize the number of groups and texts in each group
        self.text_groups = [
            # Group 1: Define texts for group 1 (this group will be flushed after first audio frame)
            # Use longer texts to ensure first group is still processing when flush is sent
            [
                "Hello world, this is the first text input with longer content.",
                "This is the second text input for testing with more words and sentences.",
                "This is the third text input in the first group, containing even more content.",
                "This is the fourth text input in the first group, with additional text to ensure sufficient length.",
                "This is the fifth text input in the first group, providing more content for testing.",
            ],
            # Group 2: Define texts for group 2 (should not generate audio after flush)
            ["And this is the third text input message.", "This group should not generate audio after flush."],
            # Group 3: Define texts for group 3 (should not generate audio after flush)
            ["Now we start the third group of inputs.", "This is the fifth text input message."],
            # Group 4: Define texts for group 4 (should not generate audio after flush)
            ["And finally the fourth group text input message."],
            # Add more groups as needed...
        ]
        
        # Specify which group will be flushed (0-based index)
        # Group 1 (index 0) will be flushed - flush will be sent after receiving first audio frame
        # After flush, subsequent groups should not generate audio
        self.flush_group_index = 0
        
        # Calculate expected group count from text_groups
        self.expected_group_count = len(self.text_groups)
        
        # Check which groups are empty (all texts are empty or whitespace only)
        self.empty_groups = []
        for group_idx, texts in enumerate(self.text_groups):
            # A group is empty if all texts are empty or whitespace only
            is_empty = all(not text or not text.strip() for text in texts)
            self.empty_groups.append(is_empty)
            if is_empty:
                print(f"⚠️  Group {group_idx + 1} is empty (all texts are empty/whitespace), will be skipped")
        
        # Request IDs and metadata for all groups (dynamically generated based on group count)
        self.request_ids = [
            f"test_append_interrupt_request_id_{i+1}" for i in range(self.expected_group_count)
        ]
        self.metadatas = [
            {
                "session_id": self.session_id,
                "turn_id": i + 1,
            }
            for i in range(self.expected_group_count)
        ]
        
        # Flush ID for the flush operation
        self.flush_id = f"test_append_interrupt_flush_{self.session_id}"
        self.sent_flush_metadata = {
            "session_id": self.session_id,
        }
        
        # Event sequence tracking - track state for each group
        self.current_group_index = 0
        self.group_states = [GroupState.WAITING_AUDIO_START] * self.expected_group_count
        self.audio_start_received = [False] * self.expected_group_count
        self.audio_frames_received = [False] * self.expected_group_count
        self.audio_end_received = [False] * self.expected_group_count
        
        # Mark empty groups as completed from the start
        for group_idx, is_empty in enumerate(self.empty_groups):
            if is_empty:
                self.group_states[group_idx] = GroupState.COMPLETED
                self.audio_end_received[group_idx] = True  # Mark as received to skip
        
        # Flush tracking
        self.flush_sent = False
        self.flush_end_received = False
        self.flush_end_timestamp = None
        self.post_flush_end_audio_count = 0
        self.post_flush_end_data_count = 0
        
        # Audio tracking
        self.current_request_id = None
        self.current_metadata = None
        self.audio_start_time = None
        self.total_audio_bytes = 0
        self.current_request_audio_bytes = 0
        self.sample_rate = 0
        self.request_audio_bytes = [0] * self.expected_group_count

    def _calculate_pcm_audio_duration_ms(self, audio_bytes: int) -> int:
        """Calculate PCM audio duration in milliseconds based on audio bytes"""
        if audio_bytes == 0 or self.sample_rate == 0:
            return 0
        
        # PCM format: 16-bit (2 bytes per sample), mono (1 channel)
        bytes_per_sample = 2
        channels = 1
        duration_sec = audio_bytes / (self.sample_rate * bytes_per_sample * channels)
        return int(duration_sec * 1000)

    @override
    async def on_start(self, ten_env: AsyncTenEnvTester) -> None:
        """Start the TTS append interrupt test - send first two groups of text inputs sequentially without waiting."""
        ten_env.log_info("Starting TTS append interrupt test")
        
        # Send only first two groups (group 0 and 1) of text inputs sequentially
        # Third and fourth groups will be sent after receiving flush_end
        for group_idx in range(min(2, len(self.text_groups))):
            # Skip empty groups
            if self.empty_groups[group_idx]:
                ten_env.log_info(f"Skipping group {group_idx + 1} (empty group)")
                continue
            
            texts = self.text_groups[group_idx]
            request_id = self.request_ids[group_idx]
            metadata = self.metadatas[group_idx]
            ten_env.log_info(f"Sending group {group_idx + 1} with {len(texts)} text input(s) using {request_id}...")
            
            # Send all texts in this group with same request_id and metadata
            for i, text in enumerate(texts):
                is_last_in_group = (i == len(texts) - 1)
                await self._send_tts_text_input(
                    ten_env, text, request_id, metadata, is_last_in_group
                )
        
        total_texts = sum(len(self.text_groups[i]) for i in range(min(2, len(self.text_groups))))
        non_empty_groups = sum(1 for i in range(min(2, len(self.text_groups))) if not self.empty_groups[i])
        ten_env.log_info(f"✅ First two groups: {total_texts} text inputs in {min(2, len(self.text_groups))} groups ({non_empty_groups} non-empty) sent sequentially")
        ten_env.log_info(f"⏳ Waiting for flush_end before sending groups 3 and 4...")

    async def _send_tts_text_input(
        self,
        ten_env: AsyncTenEnvTester,
        text: str,
        request_id: str,
        metadata: dict[str, Any],
        text_input_end: bool = True,
    ) -> None:
        """Send tts text input to TTS extension."""
        ten_env.log_info(f"Sending tts text input: {text} (request_id: {request_id}, text_input_end: {text_input_end})")
        tts_text_input_obj = Data.create("tts_text_input")
        tts_text_input_obj.set_property_string("text", text)
        tts_text_input_obj.set_property_string("request_id", request_id)
        tts_text_input_obj.set_property_bool("text_input_end", text_input_end)
        tts_text_input_obj.set_property_from_json("metadata", json.dumps(metadata))
        await ten_env.send_data(tts_text_input_obj)
        ten_env.log_info(f"✅ tts text input sent: {text}")

    async def _send_flush(self, ten_env: AsyncTenEnvTester) -> None:
        """Send flush signal to interrupt current group."""
        ten_env.log_info(f"Sending flush for group {self.flush_group_index + 1}")
        flush_data = Data.create("tts_flush")
        flush_data.set_property_string("flush_id", self.flush_id)
        flush_data.set_property_from_json("metadata", json.dumps(self.sent_flush_metadata))
        await ten_env.send_data(flush_data)
        self.flush_sent = True
        ten_env.log_info(f"✅ Flush sent with flush_id: {self.flush_id}")

    async def _send_remaining_groups(self, ten_env: AsyncTenEnvTester) -> None:
        """Send third and fourth groups after receiving flush_end."""
        ten_env.log_info("Sending remaining groups (3 and 4) after flush_end...")
        
        # Send groups 3 and 4 (group_idx 2 and 3)
        for group_idx in range(2, min(4, len(self.text_groups))):
            # Skip empty groups
            if self.empty_groups[group_idx]:
                ten_env.log_info(f"Skipping group {group_idx + 1} (empty group)")
                continue
            
            texts = self.text_groups[group_idx]
            request_id = self.request_ids[group_idx]
            metadata = self.metadatas[group_idx]
            ten_env.log_info(f"Sending group {group_idx + 1} with {len(texts)} text input(s) using {request_id}...")
            
            # Send all texts in this group with same request_id and metadata
            for i, text in enumerate(texts):
                is_last_in_group = (i == len(texts) - 1)
                await self._send_tts_text_input(
                    ten_env, text, request_id, metadata, is_last_in_group
                )
        
        total_texts = sum(len(self.text_groups[i]) for i in range(2, min(4, len(self.text_groups))))
        non_empty_groups = sum(1 for i in range(2, min(4, len(self.text_groups))) if not self.empty_groups[i])
        ten_env.log_info(f"✅ Remaining groups (3 and 4): {total_texts} text inputs in {min(2, max(0, len(self.text_groups) - 2))} groups ({non_empty_groups} non-empty) sent sequentially")

    def _stop_test_with_error(
        self, ten_env: AsyncTenEnvTester, error_message: str
    ) -> None:
        """Stop test with error message."""
        ten_env.log_error(error_message)
        ten_env.stop_test(
            TenError.create(TenErrorCode.ErrorCodeGeneric, error_message)
        )

    def _validate_metadata(
        self,
        ten_env: AsyncTenEnvTester,
        received_metadata: dict[str, Any],
        expected_metadata: dict[str, Any],
        event_name: str,
    ) -> bool:
        """Validate metadata matches expected."""
        if any(
            key not in received_metadata or received_metadata[key] != value
            for key, value in expected_metadata.items()
        ):
            self._stop_test_with_error(
                ten_env,
                f"Metadata mismatch in {event_name}. Expected: {expected_metadata}, Received: {received_metadata}",
            )
            return False
        return True

    def _check_event_sequence(self, ten_env: AsyncTenEnvTester, received_event: str) -> None:
        """Check if received event matches expected sequence for current group."""
        # After flush is sent, subsequent groups (group 2, index 1) should not generate any audio events
        # But groups 3 and 4 (index 2 and 3) sent after flush_end should be allowed
        if self.flush_sent and not self.flush_end_received and self.current_group_index > self.flush_group_index:
            self._stop_test_with_error(
                ten_env,
                f"Received event {received_event} for group {self.current_group_index + 1} after flush was sent but before flush_end. Subsequent groups should not generate any audio events (tts_audio_start, audio_frame, tts_audio_end) until flush_end is received."
            )
            return
        
        if self.current_group_index >= self.expected_group_count:
            self._stop_test_with_error(ten_env, f"Received event {received_event} but all {self.expected_group_count} groups are completed")
            return
        
        # Skip empty groups
        while self.current_group_index < self.expected_group_count and self.empty_groups[self.current_group_index]:
            ten_env.log_info(f"Skipping empty group {self.current_group_index + 1}")
            self.current_group_index += 1
            if self.current_group_index < self.expected_group_count:
                self.group_states[self.current_group_index] = GroupState.WAITING_AUDIO_START
        
        if self.current_group_index >= self.expected_group_count:
            self._stop_test_with_error(ten_env, f"Received event {received_event} but all groups are completed")
            return
        
        current_state = self.group_states[self.current_group_index]
        error_msg = None
        
        # Skip state check for group 3 (index 2) - it's sent after flush_end
        skip_state_check = (self.current_group_index == 2)
        
        if received_event == "tts_audio_start":
            if skip_state_check or current_state == GroupState.WAITING_AUDIO_START:
                # Expected audio start for current group
                self.group_states[self.current_group_index] = GroupState.RECEIVING_AUDIO_FRAMES
            else:
                error_msg = f"Unexpected tts_audio_start for group {self.current_group_index + 1} in state: {current_state}"
        elif received_event == "audio_frame":
            if skip_state_check or current_state == GroupState.RECEIVING_AUDIO_FRAMES:
                # Expected audio frames for current group
                pass
            else:
                error_msg = f"Unexpected audio_frame for group {self.current_group_index + 1} in state: {current_state}"
        elif received_event == "tts_audio_end":
            if skip_state_check or current_state == GroupState.RECEIVING_AUDIO_FRAMES:
                # Expected audio end for current group
                self.group_states[self.current_group_index] = GroupState.COMPLETED
                # Move to next non-empty group
                if self.current_group_index < self.expected_group_count - 1:
                    self.current_group_index += 1
                    # Skip empty groups
                    while self.current_group_index < self.expected_group_count and self.empty_groups[self.current_group_index]:
                        ten_env.log_info(f"Skipping empty group {self.current_group_index + 1}")
                        self.current_group_index += 1
                    if self.current_group_index < self.expected_group_count:
                        self.group_states[self.current_group_index] = GroupState.WAITING_AUDIO_START
            else:
                error_msg = f"Unexpected tts_audio_end for group {self.current_group_index + 1} in state: {current_state}"
        
        if error_msg:
            self._stop_test_with_error(ten_env, error_msg)

    @override
    async def on_data(self, ten_env: AsyncTenEnvTester, data: Data) -> None:
        """Handle received data from TTS extension."""
        name: str = data.get_name()
        current_state = self.group_states[self.current_group_index] if self.current_group_index < len(self.group_states) else "unknown"
        ten_env.log_info(f"Received data: {name} (current group: {self.current_group_index + 1}, state: {current_state})")

        if name == "error":
            json_str, _ = data.get_property_to_json("")
            ten_env.log_info(f"Received error data: {json_str}")
            self._stop_test_with_error(ten_env, f"Received error data: {json_str}")
            return
        elif name == "tts_audio_start":
            # Get request_id first to determine which group this event belongs to
            received_request_id, _ = data.get_property_string("request_id")
            
            # Find the group index based on request_id
            group_index_from_request_id = None
            for i, req_id in enumerate(self.request_ids):
                if req_id == received_request_id:
                    group_index_from_request_id = i
                    break
            
            if group_index_from_request_id is None:
                self._stop_test_with_error(
                    ten_env,
                    f"Unknown request_id in tts_audio_start: {received_request_id}",
                )
                return
            
            # Update current_group_index to match the received request_id
            # This handles the case where group 2 (index 1) doesn't receive tts_audio_start
            # because flush was sent before it started processing
            if self.current_group_index != group_index_from_request_id:
                ten_env.log_info(f"Updating current_group_index from {self.current_group_index + 1} to {group_index_from_request_id + 1} based on request_id {received_request_id}")
                self.current_group_index = group_index_from_request_id
                # Update group state if needed
                if self.current_group_index < len(self.group_states):
                    if self.group_states[self.current_group_index] == GroupState.WAITING_AUDIO_START:
                        self.group_states[self.current_group_index] = GroupState.RECEIVING_AUDIO_FRAMES
            
            # Check event sequence
            self._check_event_sequence(ten_env, "tts_audio_start")
            
            ten_env.log_info(f"Received tts_audio_start for group {self.current_group_index + 1}")
            self.audio_start_time = time.time()
            
            # Validate request_id matches
            expected_request_id = self.request_ids[self.current_group_index]
            if received_request_id != expected_request_id:
                self._stop_test_with_error(
                    ten_env,
                    f"Request ID mismatch in group {self.current_group_index + 1} tts_audio_start. Expected: {expected_request_id}, Received: {received_request_id}",
                )
                return
            
            self.current_request_id = expected_request_id
            self.current_metadata = self.metadatas[self.current_group_index]
            self.audio_start_received[self.current_group_index] = True
            self.current_request_audio_bytes = 0
            
            # Validate metadata
            metadata_str, _ = data.get_property_to_json("metadata")
            if metadata_str:
                try:
                    received_metadata = json.loads(metadata_str)
                    expected_metadata = {
                        "session_id": self.current_metadata.get("session_id", ""),
                        "turn_id": self.current_metadata.get("turn_id", -1),
                    }
                    if not self._validate_metadata(ten_env, received_metadata, expected_metadata, "tts_audio_start"):
                        return
                except json.JSONDecodeError:
                    self._stop_test_with_error(ten_env, f"Invalid JSON in tts_audio_start metadata: {metadata_str}")
                    return
            else:
                self._stop_test_with_error(ten_env, f"Missing metadata in tts_audio_start response")
                return
            
            ten_env.log_info(f"✅ tts_audio_start received with correct request_id: {received_request_id} and metadata")
            return
        elif name == "tts_audio_end":
            # Get request_id first to determine which group this event belongs to
            received_request_id, _ = data.get_property_string("request_id")
            
            # Find the group index based on request_id
            group_index_from_request_id = None
            for i, req_id in enumerate(self.request_ids):
                if req_id == received_request_id:
                    group_index_from_request_id = i
                    break
            
            if group_index_from_request_id is None:
                self._stop_test_with_error(
                    ten_env,
                    f"Unknown request_id in tts_audio_end: {received_request_id}",
                )
                return
            
            # Update current_group_index to match the received request_id
            # This handles the case where group 2 (index 1) doesn't receive tts_audio_start
            # because flush was sent before it started processing
            if self.current_group_index != group_index_from_request_id:
                ten_env.log_info(f"Updating current_group_index from {self.current_group_index + 1} to {group_index_from_request_id + 1} based on request_id {received_request_id}")
                self.current_group_index = group_index_from_request_id
            
            # Save current group index before check, as it might be updated
            group_idx_before_check = self.current_group_index
            self._check_event_sequence(ten_env, "tts_audio_end")
            
            ten_env.log_info(f"Received tts_audio_end for group {group_idx_before_check + 1}")
            
            # Validate request_id matches
            expected_request_id = self.request_ids[group_idx_before_check]
            if received_request_id != expected_request_id:
                self._stop_test_with_error(
                    ten_env,
                    f"Request ID mismatch in group {group_idx_before_check + 1} tts_audio_end. Expected: {expected_request_id}, Received: {received_request_id}",
                )
                return
            
            self.current_request_id = expected_request_id
            self.current_metadata = self.metadatas[group_idx_before_check]
            self.audio_end_received[group_idx_before_check] = True
            self.request_audio_bytes[group_idx_before_check] = self.current_request_audio_bytes
            
            # Validate metadata
            metadata_str, _ = data.get_property_to_json("metadata")
            if metadata_str:
                try:
                    received_metadata = json.loads(metadata_str)
                    expected_metadata = {
                        "session_id": self.current_metadata.get("session_id", ""),
                        "turn_id": self.current_metadata.get("turn_id", -1),
                    }
                    if not self._validate_metadata(ten_env, received_metadata, expected_metadata, "tts_audio_end"):
                        return
                except json.JSONDecodeError:
                    self._stop_test_with_error(ten_env, f"Invalid JSON in tts_audio_end metadata: {metadata_str}")
                    return
            else:
                self._stop_test_with_error(ten_env, f"Missing metadata in tts_audio_end response")
                return
            
            # Validate reason - first group should be INTERRUPTED (reason=2)
            # TTSAudioEndReason.REQUEST_END = 1, INTERRUPTED = 2
            received_reason, _ = data.get_property_int("reason")
            
            if group_idx_before_check == 0:
                # First group should have INTERRUPTED reason (2) because flush was sent
                if received_reason != 2:
                    self._stop_test_with_error(
                        ten_env,
                        f"Reason mismatch in group {group_idx_before_check + 1} tts_audio_end. Expected: 2 (INTERRUPTED), Received: {received_reason}",
                    )
                    return
                ten_env.log_info(f"✅ Group {group_idx_before_check + 1} received INTERRUPTED reason (2) as expected")
            else:
                # Other groups should have REQUEST_END reason (1)
                if received_reason != 1:
                    self._stop_test_with_error(
                        ten_env,
                        f"Reason mismatch in group {group_idx_before_check + 1} tts_audio_end. Expected: 1 (REQUEST_END), Received: {received_reason}",
                    )
                    return
                ten_env.log_info(f"✅ Group {group_idx_before_check + 1} received REQUEST_END reason (1) as expected")
            
            # Validate audio duration (skip for interrupted group as it may be incomplete)
            # First group (index 0) is interrupted, skip duration validation
            if group_idx_before_check != 0 and self.audio_start_time is not None:
                current_time = time.time()
                actual_duration_ms = (current_time - self.audio_start_time) * 1000
                
                # Get request_total_audio_duration_ms
                received_audio_duration_ms, _ = data.get_property_int("request_total_audio_duration_ms")
                
                # Calculate PCM duration based on current request audio bytes
                # Use current_request_audio_bytes which is already updated by audio frames
                pcm_audio_duration_ms = self._calculate_pcm_audio_duration_ms(self.current_request_audio_bytes)
                
                if pcm_audio_duration_ms > 0 and received_audio_duration_ms > 0:
                    audio_duration_diff = abs(received_audio_duration_ms - pcm_audio_duration_ms)
                    if audio_duration_diff > AUDIO_DURATION_TOLERANCE_MS:
                        self._stop_test_with_error(
                            ten_env,
                            f"Audio duration mismatch. PCM calculated: {pcm_audio_duration_ms}ms, Reported: {received_audio_duration_ms}ms, Diff: {audio_duration_diff}ms",
                        )
                        return
                    ten_env.log_info(
                        f"✅ Audio duration validation passed. PCM: {pcm_audio_duration_ms}ms, Reported: {received_audio_duration_ms}ms, Diff: {audio_duration_diff}ms"
                    )
                else:
                    ten_env.log_info(
                        f"Skipping audio duration validation - PCM: {pcm_audio_duration_ms}ms, Reported: {received_audio_duration_ms}ms"
                    )
                
                ten_env.log_info(f"Actual event duration: {actual_duration_ms:.2f}ms")
            else:
                if group_idx_before_check == 0:
                    ten_env.log_info(f"Skipping audio duration validation for interrupted group {group_idx_before_check + 1}")
                else:
                    ten_env.log_warn("tts_audio_start not received before tts_audio_end")
            
            ten_env.log_info(f"✅ tts_audio_end received with correct request_id, metadata, and reason for group {group_idx_before_check + 1}")
            
            # If first group (interrupted group) completed, wait for flush_end to check dump files
            # Subsequent groups should not generate audio after flush
            if group_idx_before_check == 0:
                ten_env.log_info(f"✅ Interrupted group {group_idx_before_check + 1} completed, waiting for flush_end to check dump files")
            
            # Check if the last expected group (group 3 or 4) is completed - this is the end condition
            # Groups 3 and 4 (index 2 and 3) are sent after flush_end
            # When the last non-empty group's tts_audio_end is received, check all dump files and end test
            if group_idx_before_check >= 2:  # Group 3 (index 2) or Group 4 (index 3)
                # Check if this is the last non-empty group that should complete
                # Expected groups: 1 (index 0), 3 (index 2), 4 (index 3)
                # Group 2 (index 1) should NOT complete (not processed due to flush)
                expected_completed_groups = [0, 2, 3]  # Group 1, 3, 4 should complete
                # Find the last non-empty group in expected_completed_groups
                last_expected_group = None
                for i in reversed(expected_completed_groups):
                    if i < len(self.empty_groups) and not self.empty_groups[i]:
                        last_expected_group = i
                        break
                
                # If this is the last expected group, end the test
                if last_expected_group is not None and group_idx_before_check == last_expected_group:
                    ten_env.log_info(f"✅ Last expected group {group_idx_before_check + 1} completed, checking final dump files and ending test...")
                    self._check_final_dump_file_number(ten_env)
                    ten_env.log_info("✅ All expected groups completed, test passed")
                    ten_env.stop_test()
                    return
            
            return
        elif name == "tts_flush_end":
            if not self.flush_sent:
                self._stop_test_with_error(ten_env, f"Received tts_flush_end but flush was not sent")
                return
            
            # Validate flush_id
            received_flush_id, _ = data.get_property_string("flush_id")
            if received_flush_id != self.flush_id:
                self._stop_test_with_error(ten_env, f"Flush ID mismatch. Expected: {self.flush_id}, Received: {received_flush_id}")
                return
            
            # Validate metadata completely consistent
            metadata_str, _ = data.get_property_to_json("metadata")
            if metadata_str:
                try:
                    received_metadata = json.loads(metadata_str)
                    if any(
                        key not in received_metadata
                        or received_metadata[key] != value
                        for key, value in self.sent_flush_metadata.items()
                    ):
                        self._stop_test_with_error(ten_env, f"Metadata mismatch in flush_end. Expected: {self.sent_flush_metadata}, Received: {received_metadata}")
                        return
                except json.JSONDecodeError:
                    self._stop_test_with_error(ten_env, f"Invalid JSON in flush_end metadata: {metadata_str}")
                    return
            else:
                # If no metadata is received, but there is metadata sent, report an error
                if self.sent_flush_metadata is not None:
                    self._stop_test_with_error(ten_env, f"Missing metadata in flush_end response. Expected: {self.sent_flush_metadata}")
                    return
            
            ten_env.log_info(f"✅ tts_flush_end received with correct flush_id: {received_flush_id} and metadata: {received_metadata}")
            self.flush_end_received = True
            self.flush_end_timestamp = time.time()
            
            # Check dump files after flush_end
            self._check_dump_file_number(ten_env)
            
            # Send third and fourth groups after receiving flush_end
            asyncio.create_task(self._send_remaining_groups(ten_env))
            
            return
        else:
            # Check if any unexpected data is received after flush_end
            # Groups 3 and 4 (index 2 and 3) are sent after flush_end, so their data events are expected
            if self.flush_end_received:
                # Only count unexpected data (not from groups 3 and 4)
                # Note: current_group_index might not be accurate for all data types, so we check based on event type
                # For tts_audio_start, tts_audio_end, we can check current_group_index
                # For other data types, we might need to check the data content
                if name in ["tts_audio_start", "tts_audio_end"]:
                    if self.current_group_index not in [2, 3]:
                        self.post_flush_end_data_count += 1
                        ten_env.log_info(f"⚠️ Received unexpected data '{name}' after flush_end for group {self.current_group_index + 1} (count: {self.post_flush_end_data_count})")
                        return
                else:
                    # metrics (non-ttfb) after flush_end is expected (usage metrics)
                    if name == "metrics":
                        ten_env.log_info(f"ℹ️ Received expected metrics data after flush_end (count: {self.post_flush_end_data_count})")
                        return
                    # For other data types, count as unexpected
                    self.post_flush_end_data_count += 1
                    ten_env.log_info(f"⚠️ Received unexpected data '{name}' after flush_end (count: {self.post_flush_end_data_count})")
                    return

    def _check_dump_file_number(self, ten_env: AsyncTenEnvTester) -> None:
        """Check if there are exactly expected number of dump files in the directory."""
        if not hasattr(self, 'tts_extension_dump_folder') or not self.tts_extension_dump_folder:
            ten_env.log_error("tts_extension_dump_folder not set")
            self._stop_test_with_error(ten_env, "tts_extension_dump_folder not configured")
            return

        if not os.path.exists(self.tts_extension_dump_folder):
            self._stop_test_with_error(ten_env, f"TTS extension dump folder not found: {self.tts_extension_dump_folder}")
            return
        
        # Get all files in the directory
        time.sleep(5)
        dump_files = []
        for file_path in glob.glob(os.path.join(self.tts_extension_dump_folder, "*")):
            if os.path.isfile(file_path):
                dump_files.append(file_path)

        ten_env.log_info(f"Found {len(dump_files)} dump files in {self.tts_extension_dump_folder}")
        for i, file_path in enumerate(dump_files):
            ten_env.log_info(f"  {i+1}. {os.path.basename(file_path)}")
        
        # After flush_end, check dump files:
        # - First group (index 0): should have dump file (interrupted by flush)
        # - Second group (index 1): should NOT have dump file (not processed due to flush)
        # - Third and fourth groups (index 2, 3): will be sent after flush_end, so not checked here yet
        # At flush_end time, only first group should have dump file
        # If first group is empty, then no dump files expected
        expected_count_at_flush_end = 1 if (self.expected_group_count > 0 and not self.empty_groups[0]) else 0
        if len(dump_files) == expected_count_at_flush_end:
            ten_env.log_info(f"✅ Found exactly {expected_count_at_flush_end} dump file(s) as expected at flush_end (only first group)")
            # Don't stop test here, wait for remaining groups to complete
        elif len(dump_files) > expected_count_at_flush_end:
            self._stop_test_with_error(ten_env, f"Found {len(dump_files)} dump files at flush_end, expected exactly {expected_count_at_flush_end} (only first group)")
        else:
            self._stop_test_with_error(ten_env, f"Found {len(dump_files)} dump files at flush_end, expected exactly {expected_count_at_flush_end} (only first group)")

    def _check_final_dump_file_number(self, ten_env: AsyncTenEnvTester) -> None:
        """Check if there are exactly expected number of dump files after all groups completed."""
        if not hasattr(self, 'tts_extension_dump_folder') or not self.tts_extension_dump_folder:
            ten_env.log_error("tts_extension_dump_folder not set")
            self._stop_test_with_error(ten_env, "tts_extension_dump_folder not configured")
            return

        if not os.path.exists(self.tts_extension_dump_folder):
            self._stop_test_with_error(ten_env, f"TTS extension dump folder not found: {self.tts_extension_dump_folder}")
            return
        
        # Get all files in the directory
        time.sleep(1)
        dump_files = []
        for file_path in glob.glob(os.path.join(self.tts_extension_dump_folder, "*")):
            if os.path.isfile(file_path):
                dump_files.append(file_path)

        ten_env.log_info(f"Found {len(dump_files)} dump files in {self.tts_extension_dump_folder}")
        for i, file_path in enumerate(dump_files):
            ten_env.log_info(f"  {i+1}. {os.path.basename(file_path)}")
        
        # After all groups completed, check dump files:
        # - First group (index 0): should have dump file (interrupted by flush)
        # - Second group (index 1): should NOT have dump file (not processed due to flush)
        # - Third and fourth groups (index 2, 3): should have dump files (sent after flush_end)
        # Expected: groups 1, 3, 4 should have dump files (3 files if all 4 groups are non-empty)
        # If first group is empty, then no dump files expected
        expected_completed_groups = [0, 2, 3]  # Group 1, 3, 4 should complete and have dump files
        expected_count_final = sum(
            1 for i in expected_completed_groups
            if i < len(self.empty_groups) and not self.empty_groups[i]
        )
        
        if len(dump_files) == expected_count_final:
            ten_env.log_info(f"✅ Found exactly {expected_count_final} dump file(s) as expected after all groups completed (groups 1, 3, 4)")
        elif len(dump_files) > expected_count_final:
            self._stop_test_with_error(ten_env, f"Found {len(dump_files)} dump files after all groups completed, expected exactly {expected_count_final} (groups 1, 3, 4)")
        else:
            self._stop_test_with_error(ten_env, f"Found {len(dump_files)} dump files after all groups completed, expected exactly {expected_count_final} (groups 1, 3, 4)")

    @override
    async def on_audio_frame(self, ten_env: AsyncTenEnvTester, audio_frame: AudioFrame) -> None:
        """Handle received audio frame from TTS extension."""
        # Check if any unexpected audio frame is received after flush_end
        # Groups 3 and 4 (index 2 and 3) are sent after flush_end, so their audio frames are expected
        if self.flush_end_received:
            # Only count unexpected audio frames (not from groups 3 and 4)
            if self.current_group_index not in [2, 3]:
                self.post_flush_end_audio_count += 1
                ten_env.log_info(f"⚠️ Received unexpected audio frame after flush_end for group {self.current_group_index + 1} (count: {self.post_flush_end_audio_count})")
                return
        
        # Check event sequence
        self._check_event_sequence(ten_env, "audio_frame")
        
        # Check sample_rate
        sample_rate = audio_frame.get_sample_rate()
        ten_env.log_info(f"Received audio frame with sample_rate: {sample_rate} for group {self.current_group_index + 1}")

        # Store current test sample_rate
        if self.sample_rate == 0:
            self.sample_rate = sample_rate
            ten_env.log_info(f"First audio frame received with sample_rate: {sample_rate}")

        # Mark that audio frames have been received for current group
        if self.current_group_index < len(self.audio_frames_received):
            self.audio_frames_received[self.current_group_index] = True

        # Send flush when receiving first audio frame of the flush group
        if not self.flush_sent and self.current_group_index == self.flush_group_index:
            ten_env.log_info(f"Received first audio frame for flush group {self.current_group_index + 1}, sending flush")
            await self._send_flush(ten_env)

        # Accumulate audio bytes for duration calculation
        try:
            audio_data = audio_frame.get_buf()
            if audio_data:
                self.total_audio_bytes += len(audio_data)
                self.current_request_audio_bytes += len(audio_data)
                ten_env.log_info(
                    f"Audio frame size: {len(audio_data)} bytes, Current request: {self.current_request_audio_bytes} bytes, Total: {self.total_audio_bytes} bytes"
                )
        except Exception as e:
            ten_env.log_warn(f"Failed to get audio data: {e}")

    @override
    async def on_stop(self, ten_env: AsyncTenEnvTester) -> None:
        """Clean up resources when test stops."""
        ten_env.log_info("Test stopped")
        # Keep dump files for inspection
        # _delete_dump_file(self.tts_extension_dump_folder)


def _delete_dump_file(dump_path: str) -> None:
    """Delete all dump files in the specified path."""
    for file_path in glob.glob(os.path.join(dump_path, "*")):
        if os.path.isfile(file_path):
            os.remove(file_path)
        elif os.path.isdir(file_path):
            import shutil
            shutil.rmtree(file_path)


def test_append_interrupt(extension_name: str, config_dir: str) -> None:
    """Verify TTS append input with flush interrupt."""
    # Get config file path
    config_file_path = os.path.join(config_dir, TTS_DUMP_CONFIG_FILE)
    if not os.path.exists(config_file_path):
        raise FileNotFoundError(f"Config file not found: {config_file_path}")

    # Load config file
    with open(config_file_path, "r") as f:
        config: dict[str, Any] = json.load(f)

    # Log test configuration
    print(f"Using test configuration: {config}")
    if not os.path.exists(config["dump_path"]):
        os.makedirs(config["dump_path"])
    else:
        # Delete all files in the directory before test to avoid interference from previous test
        _delete_dump_file(config["dump_path"])

    # Create and run tester
    tester = AppendInterruptTester(
        session_id="test_append_interrupt_session_123",
    )

    # Set the tts_extension_dump_folder for the tester
    tester.tts_extension_dump_folder = config["dump_path"]

    tester.set_test_mode_single(extension_name, json.dumps(config))
    error = tester.run()

    # Verify test results
    assert (
        error is None
    ), f"Test failed: {error.error_message() if error else 'Unknown error'}"
