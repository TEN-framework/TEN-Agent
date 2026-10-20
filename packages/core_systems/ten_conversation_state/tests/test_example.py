#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
"""Exercise durable recovery with separate Python processes."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ExampleTests(unittest.TestCase):
    def test_restart_restores_workflow(self):
        script = (
            Path(__file__).resolve().parents[1]
            / "examples"
            / "resume_workflow.py"
        )
        with tempfile.TemporaryDirectory() as directory:
            database = str(Path(directory) / "conversation.db")
            saved = subprocess.run(
                [sys.executable, str(script), "checkpoint", database],
                check=True,
                capture_output=True,
                text=True,
                timeout=20,
            )
            restored = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "resume",
                    database,
                    "--checkpoint-id",
                    saved.stdout.strip(),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=20,
            )
            self.assertIn("Continue at: confirm_itinerary", restored.stdout)
            self.assertIn("no tool operation replayed", restored.stdout)


if __name__ == "__main__":
    unittest.main()
