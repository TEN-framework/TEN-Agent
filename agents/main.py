#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-05.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
from glob import glob
import importlib.util
import os
from os.path import dirname
from rte_runtime_python import (
    App,
)


def log(msg):
    print("[PYTHON] {}".format(msg))


class TestApp(App):
    def on_init(self, rte, manifest, property):
        log("app on_init")
        rte.on_init_done(manifest, property)

    def on_deinit(self, rte) -> None:
        log("app on_deinit")
        rte.on_deinit_done()


if __name__ == "__main__":

    basedir = dirname(__file__)
    log("app init")

    for module in glob(os.path.join(basedir, "addon/extension/*")):
        if os.path.isdir(module):
            module_name = os.path.basename(module)
            spec = importlib.util.find_spec(
                "addon.extension.{}".format(module_name)
            )
            if spec is not None:
                mod = importlib.import_module(
                    "addon.extension.{}".format(module_name)
                )
                print("imported module: {}".format(module_name))

    app = TestApp()
    log("app created")

    app.run(False)
    log("app run done")
