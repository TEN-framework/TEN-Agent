#
# This file is part of TEN Framework.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the root directory of this source tree.
#
"""Independent checks for the PCM sample clock observed by the Guarder."""

from dataclasses import dataclass

from .timing_hooks.base import RequestTimingReference


@dataclass(frozen=True)
class AudioFrameTiming:
    timestamp_ms: int
    samples: int
    sample_rate: int
    channels: int = 1

    @property
    def duration_ms(self) -> int:
        return (
            self.samples * 1000 // self.sample_rate
            if self.sample_rate > 0
            else 0
        )


def validate_audio_clock(frames: list[AudioFrameTiming]) -> tuple[bool, str]:
    if not frames:
        return False, "No audio frames received"
    first = frames[0]
    if first.sample_rate <= 0 or first.channels <= 0:
        return False, "Invalid audio format"
    samples_before = 0
    for index, current in enumerate(frames):
        if (
            current.sample_rate != first.sample_rate
            or current.channels != first.channels
        ):
            return False, "Audio format changed within the request"
        if current.samples <= 0:
            return False, "Audio frame contains no samples"
        expected = (
            first.timestamp_ms + samples_before * 1000 // first.sample_rate
        )
        if abs(current.timestamp_ms - expected) > 1:
            return (
                False,
                f"Audio cumulative sample clock mismatch at frame {index}: expected {expected}, got {current.timestamp_ms}",
            )
        samples_before += current.samples
    return True, "Audio timestamps follow cumulative PCM samples (within 1ms)"


def timed_results(results: list[dict]) -> list[dict]:
    return [result for result in results if result.get("words")]


def validate_subtitle_bounds(
    results: list[dict], frames: list[AudioFrameTiming]
) -> tuple[bool, str]:
    captions = timed_results(results)
    if not captions or not frames:
        return False, "Missing subtitle words or audio frames"
    first = frames[0]
    if first.sample_rate <= 0:
        return False, "Invalid audio sample rate"
    audio_end = (
        first.timestamp_ms
        + sum(frame.samples for frame in frames) * 1000 / first.sample_rate
    )
    previous_start = None
    for result in captions:
        start = result.get("start_ms", -1)
        duration = result.get("duration_ms", 0)
        if (
            duration < 0
            or start < first.timestamp_ms - 1
            or start > audio_end + 1
            or start + duration > audio_end + 1
        ):
            return False, "Subtitle range lies outside the PCM timeline"
        if previous_start is not None and start <= previous_start:
            return False, "Subtitle starts are not strictly ascending"
        previous_start = start
        previous_word = None
        for word in result["words"]:
            word_start = word.get("start_ms", -1)
            word_duration = word.get("duration_ms", -1)
            word_end = word_start + word_duration
            if (
                word_duration < 0
                or word_start < first.timestamp_ms - 1
                or word_end > audio_end + 1
            ):
                return False, "Subtitle word lies outside the PCM timeline"
            if word_start < start - 1 or (
                duration > 0 and word_end > start + duration + 1
            ):
                return False, "Subtitle word lies outside its result range"
            if previous_word is not None and word_start < previous_word:
                return False, "Subtitle words are not ascending"
            previous_word = word_start
    return True, "Subtitle words stay within PCM and their result ranges"


def validate_provider_reference(
    request_id: str,
    results: list[dict],
    frames: list[AudioFrameTiming],
    reference: RequestTimingReference,
) -> tuple[bool, str]:
    vendor = reference.vendor
    if reference.error:
        return False, reference.error
    if any(result.get("request_id") != request_id for result in results):
        return False, "Subtitle belongs to another request"
    if reference.sample_rate <= 0 or reference.channels <= 0:
        return False, f"{vendor} audio format was not observed"
    if not frames or any(
        frame.sample_rate != reference.sample_rate
        or frame.channels != reference.channels
        for frame in frames
    ):
        return False, f"TEN audio format differs from {vendor}"
    observed_bytes = sum(frame.samples * frame.channels * 2 for frame in frames)
    if observed_bytes != reference.pcm_bytes:
        return False, "TEN PCM sample count differs from provider audio"
    captions = timed_results(results)
    if not reference.captions or len(captions) != len(reference.captions):
        return False, "TEN subtitle count differs from provider subtitles"
    origin = frames[0].timestamp_ms
    for result, expected_words in zip(captions, reference.captions):
        if len(result["words"]) != len(expected_words):
            return False, "TEN word count differs from provider words"
        for actual, raw in zip(result["words"], expected_words):
            expected_start = origin + int(raw.start_ms)
            expected_end = origin + int(raw.end_ms)
            actual_end = actual["start_ms"] + actual["duration_ms"]
            if (
                actual["word"] != raw.word
                or abs(actual["start_ms"] - expected_start) > 1
                or abs(actual_end - expected_end) > 1
            ):
                return (
                    False,
                    f"TEN word timing differs from {vendor}: expected [{expected_start}, {expected_end}], got [{actual['start_ms']}, {actual_end}]",
                )
    first_offset = float(reference.captions[0][0].start_ms)
    observed_offset = captions[0]["words"][0]["start_ms"] - origin
    return (
        True,
        f"{vendor} raw timing verified: {len(captions)} subtitles, first word offset {first_offset:.3f}ms -> {observed_offset}ms",
    )
