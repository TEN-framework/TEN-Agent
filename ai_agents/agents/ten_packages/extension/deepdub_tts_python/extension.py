import os
import traceback
from datetime import datetime
from typing import Optional

from ten_ai_base.const import LOG_CATEGORY_KEY_POINT
from ten_ai_base.helper import PCMWriter
from ten_ai_base.message import (
    ModuleError,
    ModuleErrorCode,
    ModuleErrorVendorInfo,
    ModuleType,
    TTSAudioEndReason,
)
from ten_ai_base.struct import TTSTextInput
from ten_ai_base.tts2 import AsyncTTS2BaseExtension
from ten_runtime import AsyncTenEnv

from .config import DeepdubTTSConfig
from .deepdub_tts import DeepdubStreamingClient, DeepdubTTSException


class DeepdubTTSExtension(AsyncTTS2BaseExtension):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.config: Optional[DeepdubTTSConfig] = None
        self.client: Optional[DeepdubStreamingClient] = None

        self.current_request_id: Optional[str] = None
        self.sent_ts: Optional[datetime] = None
        self.first_chunk: bool = True
        self.awaiting_finish: bool = False
        self.current_request_finished: bool = False
        self.total_audio_bytes: int = 0

        self.recorder_map: dict[str, PCMWriter] = {}

    # ---------- lifecycle ----------

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        try:
            await super().on_init(ten_env)
            ten_env.log_debug("on_init")

            if self.config is None:
                config_json, _ = await self.ten_env.get_property_to_json("")
                if not config_json or config_json.strip() == "{}":
                    raise ValueError("Configuration is empty.")
                self.config = DeepdubTTSConfig.model_validate_json(config_json)
                self.config.update_params()
                self.config.validate_params()
                ten_env.log_info(
                    f"config: {self.config.to_str(sensitive_handling=True)}",
                    category=LOG_CATEGORY_KEY_POINT,
                )

            self.client = DeepdubStreamingClient(
                config=self.config,
                ten_env=ten_env,
                on_audio=self._on_audio,
                on_finish=self._on_finish,
                on_error=self._on_error,
            )
            await self.client.start()
            ten_env.log_info("deepdub TTS client started (pre-warming)")
        except Exception as e:
            ten_env.log_error(f"on_init failed: {traceback.format_exc()}")
            await self.send_tts_error(
                self.current_request_id or "",
                ModuleError(
                    message=f"init error: {e}",
                    module=ModuleType.TTS,
                    code=int(ModuleErrorCode.FATAL_ERROR),
                    vendor_info=None,
                ),
            )

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        if self.client:
            await self.client.stop()
            self.client = None
        for rid, rec in list(self.recorder_map.items()):
            try:
                await rec.flush()
            except Exception as e:
                ten_env.log_error(f"recorder flush error ({rid}): {e}")
        self.recorder_map.clear()
        await super().on_stop(ten_env)

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await super().on_deinit(ten_env)

    def vendor(self) -> str:
        return "deepdub"

    def synthesize_audio_sample_rate(self) -> int:
        return self.config.sample_rate if self.config else 48000

    def synthesize_audio_channels(self) -> int:
        return self.config.channels if self.config else 1

    # ---------- request_tts ----------

    async def request_tts(self, t: TTSTextInput) -> None:
        try:
            if self.client is None:
                await self.send_tts_error(
                    t.request_id,
                    ModuleError(
                        message="client not initialized",
                        module=ModuleType.TTS,
                        code=int(ModuleErrorCode.FATAL_ERROR),
                        vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                    ),
                )
                if t.text_input_end:
                    await self.finish_request(
                        t.request_id, reason=TTSAudioEndReason.ERROR
                    )
                return

            self.ten_env.log_info(
                f"KEYPOINT request_tts: rid={t.request_id} end={t.text_input_end} text={t.text!r}"
            )

            if t.request_id != self.current_request_id:
                self.current_request_id = t.request_id
                self.sent_ts = datetime.now()
                self.first_chunk = True
                self.awaiting_finish = False
                self.current_request_finished = False
                self.total_audio_bytes = 0
                self._setup_recorder(t.request_id)

            if t.text:
                self.metrics_add_output_characters(len(t.text))
                await self.client.send_text(t.text)

            if t.text_input_end:
                self.current_request_finished = True
                self.awaiting_finish = True
                self.ten_env.log_info(
                    f"KEYPOINT awaiting isFinished for rid={t.request_id}"
                )

        except DeepdubTTSException as e:
            await self._send_error(e, t)
        except Exception as e:
            self.ten_env.log_error(
                f"request_tts error: {traceback.format_exc()}"
            )
            await self.send_tts_error(
                self.current_request_id or "",
                ModuleError(
                    message=str(e),
                    module=ModuleType.TTS,
                    code=int(ModuleErrorCode.NON_FATAL_ERROR),
                    vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                ),
            )
            if t.text_input_end:
                await self.finish_request(
                    self.current_request_id or "",
                    reason=TTSAudioEndReason.ERROR,
                )

    async def cancel_tts(self) -> None:
        try:
            if self.client:
                await self.client.cancel()
            if self.current_request_id and self.sent_ts:
                interval = int(
                    (datetime.now() - self.sent_ts).total_seconds() * 1000
                )
                await self.send_tts_audio_end(
                    request_id=self.current_request_id,
                    request_event_interval_ms=interval,
                    request_total_audio_duration_ms=self._audio_ms(),
                    reason=TTSAudioEndReason.INTERRUPTED,
                )
                await self.send_usage_metrics(self.current_request_id)
                await self._reset_request_state()
        except Exception as e:
            self.ten_env.log_error(f"cancel_tts error: {e}")

    # ---------- callbacks from streaming client ----------

    async def _on_audio(self, pcm: bytes) -> None:
        if not pcm or not self.current_request_id:
            return
        self.total_audio_bytes += len(pcm)
        self.metrics_add_recv_audio_chunks(pcm)
        if self.first_chunk:
            self.first_chunk = False
            await self.send_tts_audio_start(request_id=self.current_request_id)
            if self.sent_ts:
                ttfb = int(
                    (datetime.now() - self.sent_ts).total_seconds() * 1000
                )
                await self.send_tts_ttfb_metrics(
                    request_id=self.current_request_id,
                    ttfb_ms=ttfb,
                    extra_metadata={
                        "model": self.config.model if self.config else "",
                        "voice_prompt_id": (
                            self.config.voice_prompt_id if self.config else ""
                        ),
                    },
                )
        rec = self.recorder_map.get(self.current_request_id)
        if rec is not None:
            try:
                await rec.write(pcm)
            except Exception as e:
                self.ten_env.log_warn(f"recorder write error: {e}")
        await self.send_tts_audio_data(pcm, 0)

    async def _on_finish(self) -> None:
        # Vendor signalled end of audio for queued text. Only honour as a
        # request boundary if TEN sent text_input_end and we're awaiting it.
        if not self.awaiting_finish or not self.current_request_id:
            return
        rid = self.current_request_id
        interval = (
            int((datetime.now() - self.sent_ts).total_seconds() * 1000)
            if self.sent_ts
            else 0
        )
        duration = self._audio_ms()
        rec = self.recorder_map.get(rid)
        if rec is not None:
            try:
                await rec.flush()
            except Exception as e:
                self.ten_env.log_warn(f"recorder flush error: {e}")
        await self.send_tts_audio_end(
            request_id=rid,
            request_event_interval_ms=interval,
            request_total_audio_duration_ms=duration,
        )
        await self.send_usage_metrics(rid)
        await self.finish_request(rid)
        self.ten_env.log_info(
            f"KEYPOINT tts_audio_end rid={rid} interval={interval}ms duration={duration}ms"
        )
        await self._reset_request_state()

    async def _on_error(self, exc: DeepdubTTSException) -> None:
        self.ten_env.log_error(f"deepdub stream error: {exc}")
        if not self.current_request_id:
            return
        err = ModuleError(
            message=str(exc),
            module=ModuleType.TTS,
            code=int(ModuleErrorCode.NON_FATAL_ERROR),
            vendor_info=ModuleErrorVendorInfo(
                vendor=self.vendor(),
                code=str(exc.code),
                message=exc.message,
            ),
        )
        await self.send_tts_error(self.current_request_id, err)
        if self.current_request_finished:
            await self.finish_request(
                self.current_request_id,
                reason=TTSAudioEndReason.ERROR,
                error=err,
            )
            await self._reset_request_state()

    # ---------- helpers ----------

    def _audio_ms(self) -> int:
        if not self.config:
            return 0
        bps = 2
        ch = self.config.channels
        sr = self.config.sample_rate
        if sr <= 0:
            return 0
        return int(self.total_audio_bytes / (sr * bps * ch) * 1000)

    def _setup_recorder(self, rid: str) -> None:
        if not (self.config and self.config.dump and self.config.dump_path):
            return
        # Drop other recorders.
        for old_rid in [k for k in self.recorder_map if k != rid]:
            try:
                # Best-effort sync close; the framework reuses ids per turn.
                del self.recorder_map[old_rid]
            except Exception:
                pass
        if rid in self.recorder_map:
            return
        path = os.path.join(self.config.dump_path, f"deepdub_dump_{rid}.pcm")
        self.recorder_map[rid] = PCMWriter(path)

    async def _reset_request_state(self) -> None:
        self.current_request_id = None
        self.sent_ts = None
        self.first_chunk = True
        self.awaiting_finish = False
        self.current_request_finished = False
        self.total_audio_bytes = 0

    async def _send_error(
        self, exc: DeepdubTTSException, t: TTSTextInput
    ) -> None:
        err = ModuleError(
            message=str(exc),
            module=ModuleType.TTS,
            code=int(ModuleErrorCode.NON_FATAL_ERROR),
            vendor_info=ModuleErrorVendorInfo(
                vendor=self.vendor(),
                code=str(exc.code),
                message=exc.message,
            ),
        )
        await self.send_tts_error(self.current_request_id or "", err)
        if t.text_input_end:
            await self.finish_request(
                self.current_request_id or "",
                reason=TTSAudioEndReason.ERROR,
                error=err,
            )
            await self._reset_request_state()
