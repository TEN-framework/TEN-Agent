"""TEN adapter for Jev's typed decision API."""

import asyncio
import json
import logging
from typing import Optional

from ten_runtime import AsyncExtension, AsyncTenEnv, Cmd, CmdResult, StatusCode
from typesafe_sdk import AsyncTypeSafeClient, TypeSafeError

from .config import JevConfig
from .decision import DecisionError, evaluate


class TypeSafeJevExtension(AsyncExtension):
    def __init__(self, name: str):
        super().__init__(name)
        self.config = JevConfig()
        self.client: Optional[AsyncTypeSafeClient] = None
        self.pending: dict[str, asyncio.Task] = {}

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        config_json, error = await ten_env.get_property_to_json("")
        if error:
            ten_env.log_error("config: failed to read Jev properties")
            return
        try:
            self.config = JevConfig.model_validate_json(config_json)
        except ValueError:
            ten_env.log_error("config: invalid Jev properties")
            return

        ten_env.log_info(f"config: {self.config.safe_summary()}")
        if not self.config.params.api_key:
            ten_env.log_error("config: Jev API key is missing")
            return

        # The SDK's DEBUG level includes unredacted request/response bodies.
        logging.getLogger("typesafe_sdk").setLevel(logging.INFO)
        try:
            self.client = AsyncTypeSafeClient(
                api_key=self.config.params.api_key,
                base_url=self.config.params.base_url,
                model=self.config.params.model,
            )
        except TypeSafeError:
            ten_env.log_error("config: Jev client initialization failed")

    async def on_stop(self, _ten_env: AsyncTenEnv) -> None:
        for task in tuple(self.pending.values()):
            task.cancel()
        if self.pending:
            await asyncio.gather(
                *tuple(self.pending.values()), return_exceptions=True
            )
        if self.client:
            await self.client.aclose()
            self.client = None

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        request_id = ""
        status = StatusCode.ERROR
        result_payload: dict = {"error_code": "invalid_request"}
        try:
            payload_json, error = cmd.get_property_to_json(None)
            if error:
                raise DecisionError("invalid_request")
            payload = json.loads(payload_json)
            request_id = (
                payload.get("request_id", "")
                if isinstance(payload, dict)
                else ""
            )
            if cmd.get_name() == "abort":
                if not isinstance(request_id, str) or not request_id:
                    raise DecisionError("invalid_request")
                task = self.pending.get(request_id)
                if task:
                    task.cancel()
                status = StatusCode.OK
                result_payload = {
                    "request_id": request_id,
                    "cancelled": task is not None,
                }
            elif cmd.get_name() == "decision_evaluate":
                if not isinstance(request_id, str) or not request_id:
                    raise DecisionError("invalid_request")
                if request_id in self.pending:
                    raise DecisionError("duplicate_request_id")
                task = asyncio.create_task(
                    evaluate(
                        self.client, payload, self.config.params.timeout_ms
                    )
                )
                self.pending[request_id] = task
                try:
                    result_payload = await task
                    status = StatusCode.OK
                finally:
                    self.pending.pop(request_id, None)
            else:
                raise DecisionError("unknown_command")
        except asyncio.CancelledError:
            result_payload = {"error_code": "cancelled"}
        except DecisionError as error:
            result_payload = {"error_code": error.code}
        except (TypeError, ValueError, KeyError):
            result_payload = {"error_code": "invalid_request"}
        except Exception:
            ten_env.log_error("Jev decision failed unexpectedly")
            result_payload = {"error_code": "internal_error"}

        if isinstance(request_id, str) and request_id:
            result_payload.setdefault("request_id", request_id)
        cmd_result = CmdResult.create(status, cmd)
        cmd_result.set_property_from_json(None, json.dumps(result_payload))
        await ten_env.return_result(cmd_result)
