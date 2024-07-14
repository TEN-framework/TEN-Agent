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
import argparse
from os.path import dirname

def log(msg):
    print("[PYTHON] {}".format(msg))

def process_args():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--manifest", help="The absolute path of manifest.json"
    )
    return parser.parse_args()

if __name__ == "__main__":
    args = process_args()

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

    from rte_runtime_python import App, MetadataType
    class TestApp(App):
        def on_init(self, rte, manifest, property):
            log("app on_init")
            
            # Using the default manifest.json if not specified.
            if self.manifest_path:
                log("set manifest: {}".format(self.manifest_path))
                manifest.set(MetadataType.JSON_FILENAME, self.manifest_path)

            rte.on_init_done(manifest, property)

        def on_deinit(self, rte) -> None:
            log("app on_deinit")
            rte.on_deinit_done()

        def set_manifest_path(self, manifest_path):
            self.manifest_path = manifest_path

    app = TestApp()
    app.set_manifest_path(args.manifest)
    log("app created")

    app.run(False)
    log("app run done")
