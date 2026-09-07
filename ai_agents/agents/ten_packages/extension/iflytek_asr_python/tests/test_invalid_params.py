import asyncio

import pytest
from pydantic import ValidationError

from iflytek_asr_python.config import IFlytekAsrConfig
from iflytek_asr_python.extension import IFlytekAsrExtension

from .helpers import FakePropertyError, FakeTenEnv, data_as_dict


@pytest.mark.parametrize(
    "properties",
    [
        {
            "params": {
                "url": "ws://127.0.0.1:9990/tuling/ast/v3",
                "biz_id": "tenant-1",
                "reconnect_delay": 2.0,
                "reconnect_max_delay": 1.0,
            }
        },
        {
            "dump": True,
            "dump_path": "   ",
            "params": {
                "url": "ws://127.0.0.1:9990/tuling/ast/v3",
                "biz_id": "tenant-1",
            },
        },
    ],
)
def test_config_rejects_invalid_cross_field_values(
    properties: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        IFlytekAsrConfig.model_validate(properties)


def test_property_read_error_reports_fatal_without_crashing() -> None:
    async def run() -> None:
        ten_env = FakeTenEnv(
            {
                "params": {
                    "url": "ws://127.0.0.1:9990/tuling/ast/v3",
                    "biz_id": "tenant-1",
                }
            },
            property_error=FakePropertyError("property backend unavailable"),
        )
        extension = IFlytekAsrExtension("iflytek")

        await extension.on_init(ten_env)  # type: ignore[arg-type]

        errors = [
            data_as_dict(data)
            for data in ten_env.data
            if data.get_name() == "error"
        ]
        assert len(errors) == 1
        assert errors[0]["code"] == -1000
        assert "property backend unavailable" in errors[0]["message"]
        assert errors[0]["vendor_info"]["vendor"] == "iflytek"
        assert extension.config is None
        assert extension.client is None
        extension.stopped = True

    asyncio.run(run())
