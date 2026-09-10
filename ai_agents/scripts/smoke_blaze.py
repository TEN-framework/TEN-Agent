#!/usr/bin/env python3
"""
Smoke-test Blaze STT and TTS extensions against a live Blaze API.

Loads credentials from (first match wins):
  1) process environment
  2) ai_agents/.env
  3) repo-root .env

Usage (from repo root or ai_agents/):

  python ai_agents/scripts/smoke_blaze.py
  python ai_agents/scripts/smoke_blaze.py --audio /path/to/sample.wav
  python ai_agents/scripts/smoke_blaze.py --text "Xin chào" --skip-stt

Exit code 0 if selected checks pass.
"""

from __future__ import annotations

import argparse
import io
import math
import os
import struct
import sys
import time
import wave
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
AI_AGENTS = REPO_ROOT / "ai_agents"
EXT_ROOT = AI_AGENTS / "agents" / "ten_packages" / "extension"


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load_env() -> None:
    _load_dotenv(AI_AGENTS / ".env")
    _load_dotenv(REPO_ROOT / ".env")
    # Map unified key if vendor-specific missing
    key = os.environ.get("BLAZE_API_KEY", "")
    if key:
        os.environ.setdefault("BLAZE_STT_API_KEY", key)
        os.environ.setdefault("BLAZE_TTS_API_KEY", key)
    os.environ.setdefault("BLAZE_STT_API_URL", "https://api.blaze.vn")
    os.environ.setdefault("BLAZE_TTS_API_URL", "https://api.blaze.vn")


def make_tone_wav(seconds: float = 0.5, sr: int = 16000, freq: float = 440.0) -> bytes:
    n = int(sr * seconds)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        frames = bytearray()
        for i in range(n):
            val = int(8000 * math.sin(2 * math.pi * freq * i / sr))
            frames += struct.pack("<h", val)
        w.writeframes(frames)
    return buf.getvalue()


def redacted(key: str) -> str:
    if not key:
        return "<empty>"
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}...{key[-4:]} (len={len(key)})"


def smoke_tts(api_url: str, api_key: str, text: str, speaker_id: str, out_path: Path) -> bool:
    sys.path.insert(0, str(EXT_ROOT / "blaze_tts_python"))
    from blaze_tts import BlazeTTSExtension  # type: ignore  # pylint: disable=import-error

    print(f"[TTS] api_url={api_url}")
    print(f"[TTS] api_key={redacted(api_key)}")
    tts = BlazeTTSExtension(
        config={
            "api_url": api_url,
            "api_key": api_key,
            "language": "vi",
            "speaker_id": speaker_id,
        }
    )

    speakers = tts.get_speakers()
    lst = speakers.get("list_speakers") or []
    print(f"[TTS] speakers: {len(lst)}")
    if not speaker_id and lst:
        speaker_id = lst[0]["id"]
        print(f"[TTS] using first speaker: {speaker_id}")

    result = tts.synthesize(
        text=text,
        speaker_id=speaker_id,
        language="vi",
        audio_format="wav",
        media_type="audio/ogg; codecs=opus",
    )
    job_id = result.get("id") or result.get("job_id")
    print(f"[TTS] job_id={job_id} raw={result}")
    if not job_id:
        print("[TTS] FAIL: no job id")
        return False

    # Poll download (Blaze often returns 425 while processing)
    audio = None
    for attempt in range(1, 61):
        try:
            audio = tts.download_audio(job_id)
            print(f"[TTS] download attempt {attempt}: OK {len(audio)} bytes")
            break
        except Exception as exc:  # pylint: disable=broad-exception-caught
            status = getattr(getattr(exc, "response", None), "status_code", None)
            print(f"[TTS] download attempt {attempt}: {status or type(exc).__name__}")
            if status not in (None, 425):
                print(f"[TTS] FAIL: {exc}")
                return False
            time.sleep(2)

    if not audio:
        print("[TTS] FAIL: download timeout")
        return False

    out_path.write_bytes(audio)
    print(f"[TTS] saved {out_path} ({out_path.stat().st_size} bytes)")

    # Basic WAV sanity
    try:
        with wave.open(io.BytesIO(audio), "rb") as w:
            print(
                f"[TTS] wav channels={w.getnchannels()} "
                f"width={w.getsampwidth()} rate={w.getframerate()} "
                f"frames={w.getnframes()}"
            )
    except wave.Error as exc:
        print(f"[TTS] WARN: not a WAV file ({exc}); still counted as pass if bytes>0")

    print("[TTS] PASS")
    return True


def smoke_stt(api_url: str, api_key: str, audio_bytes: bytes) -> bool:
    sys.path.insert(0, str(EXT_ROOT / "blaze_stt_python"))
    from blaze_stt import BlazeSTTExtension  # type: ignore  # pylint: disable=import-error

    print(f"[STT] api_url={api_url}")
    print(f"[STT] api_key={redacted(api_key)}")
    print(f"[STT] audio_bytes={len(audio_bytes)}")

    stt = BlazeSTTExtension(
        config={
            "api_url": api_url,
            "api_key": api_key,
            "language": "vi",
        }
    )
    result = stt.process(
        {
            "audio_data": audio_bytes,
            "audio_content_type": "audio/wav",
            "language": "vi",
        }
    )
    text = result.get("transcription") or ""
    print(f"[STT] status={result.get('status')} job_id={result.get('job_id')}")
    print(f"[STT] transcription[:240]={text[:240]!r}")
    if not text and result.get("status") not in ("completed", "processing"):
        print("[STT] FAIL")
        return False
    # Empty text can be valid for tone-only audio; still require no exception
    print("[STT] PASS")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test Blaze STT/TTS")
    parser.add_argument(
        "--audio",
        type=Path,
        default=None,
        help="WAV file for STT (default: /home/trung/test/2.wav or tone)",
    )
    parser.add_argument(
        "--text",
        default="Xin chào, đây là bài kiểm tra Blaze extension.",
        help="Text for TTS",
    )
    parser.add_argument(
        "--speaker-id",
        default=os.environ.get("BLAZE_TTS_SPEAKER_ID", "HN-Nam-2-BL"),
        help="Blaze speaker_id for TTS",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("/tmp/blaze_smoke_tts.wav"),
        help="Where to write downloaded TTS audio",
    )
    parser.add_argument("--skip-stt", action="store_true")
    parser.add_argument("--skip-tts", action="store_true")
    args = parser.parse_args()

    load_env()
    stt_key = os.environ.get("BLAZE_STT_API_KEY") or os.environ.get("BLAZE_API_KEY", "")
    tts_key = os.environ.get("BLAZE_TTS_API_KEY") or os.environ.get("BLAZE_API_KEY", "")
    stt_url = os.environ.get("BLAZE_STT_API_URL", "https://api.blaze.vn")
    tts_url = os.environ.get("BLAZE_TTS_API_URL", "https://api.blaze.vn")

    if not args.skip_stt and not stt_key:
        print("ERROR: BLAZE_STT_API_KEY / BLAZE_API_KEY not set")
        return 2
    if not args.skip_tts and not tts_key:
        print("ERROR: BLAZE_TTS_API_KEY / BLAZE_API_KEY not set")
        return 2

    ok = True
    if not args.skip_tts:
        try:
            ok = smoke_tts(tts_url, tts_key, args.text, args.speaker_id, args.out) and ok
        except Exception as exc:  # pylint: disable=broad-exception-caught
            print(f"[TTS] FAIL: {exc}")
            ok = False

    if not args.skip_stt:
        if args.audio and args.audio.is_file():
            audio = args.audio.read_bytes()
            print(f"[STT] using --audio {args.audio}")
        else:
            default = Path("/home/trung/test/2.wav")
            if default.is_file():
                audio = default.read_bytes()
                print(f"[STT] using {default}")
            else:
                audio = make_tone_wav()
                print("[STT] using synthetic tone WAV (no sample file found)")
        try:
            ok = smoke_stt(stt_url, stt_key, audio) and ok
        except Exception as exc:  # pylint: disable=broad-exception-caught
            print(f"[STT] FAIL: {exc}")
            ok = False

    print("\n" + ("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
