import sys
from pathlib import Path

project_root = str(Path(__file__).resolve().parents[6])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import json
import threading

import pytest
from ten_runtime import App, TenEnv
from typing_extensions import override


class FakeApp(App):
    def __init__(self):
        super().__init__()
        self.event: threading.Event | None = None

    @override
    def on_init(self, ten_env: TenEnv) -> None:
        assert self.event
        self.event.set()
        ten_env.on_init_done()

    @override
    def on_configure(self, ten_env: TenEnv) -> None:
        ten_env.init_property_from_json(
            json.dumps(
                {
                    "ten": {
                        "log": {
                            "handlers": [
                                {
                                    "matchers": [{"level": "debug"}],
                                    "formatter": {
                                        "type": "plain",
                                        "colored": True,
                                    },
                                    "emitter": {
                                        "type": "console",
                                        "config": {"stream": "stdout"},
                                    },
                                }
                            ]
                        }
                    }
                }
            ),
        )
        ten_env.on_configure_done()


class FakeAppCtx:
    def __init__(self, event: threading.Event):
        self.fake_app: FakeApp | None = None
        self.event = event


def run_fake_app(fake_app_ctx: FakeAppCtx):
    app = FakeApp()
    app.event = fake_app_ctx.event
    fake_app_ctx.fake_app = app
    app.run(False)


@pytest.fixture(scope="session", autouse=True)
def global_setup_and_teardown():
    event = threading.Event()
    fake_app_ctx = FakeAppCtx(event)
    fake_app_thread = threading.Thread(
        target=run_fake_app,
        args=(fake_app_ctx,),
    )
    fake_app_thread.start()
    event.wait()

    assert fake_app_ctx.fake_app is not None
    yield

    fake_app_ctx.fake_app.close()
    fake_app_thread.join()
