#
# Copyright © 2025 Agora
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0, with certain conditions.
# Refer to the "LICENSE" file in the root directory for more information.
#
import pytest
import sys
import os
from ten import (
    unregister_all_addons_and_cleanup,
)


@pytest.fixture(scope="session", autouse=True)
def global_setup_and_teardown():
    # Set the environment variable.
    os.environ["TEN_DISABLE_ADDON_UNREGISTER_AFTER_APP_CLOSE"] = "true"

    # Verify the environment variable is correctly set.
    if (
        "TEN_DISABLE_ADDON_UNREGISTER_AFTER_APP_CLOSE" not in os.environ
        or os.environ["TEN_DISABLE_ADDON_UNREGISTER_AFTER_APP_CLOSE"] != "true"
    ):
        print(
            "Failed to set TEN_DISABLE_ADDON_UNREGISTER_AFTER_APP_CLOSE",
            file=sys.stderr,
        )
        sys.exit(1)

    # Yield control to the test; after the test execution is complete, continue
    # with the teardown process.
    yield

    # Teardown part.
    unregister_all_addons_and_cleanup()
