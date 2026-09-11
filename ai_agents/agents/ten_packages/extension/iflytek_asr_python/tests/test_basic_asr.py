import asyncio

from iflytek_asr_python.client import IFlytekAsrClient
from iflytek_asr_python.extension import IFlytekAsrExtension

from .helpers import FakeTenEnv


def test_on_init_loads_property_and_constructs_vendor_client() -> None:
    async def run() -> None:
        ten_env = FakeTenEnv(
            {
                "params": {
                    "url": "ws://127.0.0.1:9990/tuling/ast/v3",
                    "app_id": "app-1",
                    "biz_id": "tenant-1",
                    "language": "zh-CN",
                }
            }
        )
        extension = IFlytekAsrExtension("iflytek")

        await extension.on_init(ten_env)  # type: ignore[arg-type]

        assert extension.config is not None
        assert extension.config.biz_id == "tenant-1"
        assert extension.config.vendor_language() == "zh"
        assert isinstance(extension.client, IFlytekAsrClient)
        assert not [data for data in ten_env.data if data.get_name() == "error"]
        extension.stopped = True

    asyncio.run(run())
