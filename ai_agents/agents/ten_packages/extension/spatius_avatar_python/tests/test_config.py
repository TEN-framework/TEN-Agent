#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
from ..extension import SpatiusConfig


def test_extra_params_are_copied_from_params():
    extra_params = {"server_post_process": "false"}
    config = SpatiusConfig()
    config.params = {"extra_params": extra_params}

    config.update_params()

    extra_params["server_post_process"] = "true"
    assert config.extra_params == {"server_post_process": "false"}


def test_extra_params_default_to_empty_dict():
    config = SpatiusConfig()
    config.params = {}

    config.update_params()

    assert config.extra_params == {}
