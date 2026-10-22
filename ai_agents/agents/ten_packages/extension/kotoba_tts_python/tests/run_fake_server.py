#
# Kotoba TTS extension for the TEN framework.
# Licensed under the Apache License, Version 2.0.
#
"""Run the fake Kotoba service on a fixed port, for the TEN guarder suite.

python3 tests/run_fake_server.py 8765
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fake_kotoba_server import FakeKotobaServer, Scenario  # noqa: E402


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = FakeKotobaServer(
        Scenario(chunks_per_response=25, samples_per_chunk=1600)
    )
    server.fixed_port = port
    server.start()
    print(f"fake kotoba tts listening on {server.url}", flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        server.stop()


if __name__ == "__main__":
    main()
