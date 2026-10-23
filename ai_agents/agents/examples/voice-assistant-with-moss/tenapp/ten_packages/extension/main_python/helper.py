#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#

import json
from typing import Any, AsyncGenerator, Optional
from ten_runtime import AsyncTenEnv, Cmd, CmdResult, Data, Loc, TenError


def is_punctuation(char):
    if char in [",", "，", ".", "。", "?", "？", "!", "！"]:
        return True
    return False


def parse_sentences(sentence_fragment, content):
    sentences = []
    current_sentence = sentence_fragment
    for char in content:
        current_sentence += char
        if is_punctuation(char):
            # Check if the current sentence contains non-punctuation characters
            stripped_sentence = current_sentence
            if any(c.isalnum() for c in stripped_sentence):
                sentences.append(stripped_sentence)
            current_sentence = ""  # Reset for the next sentence

    remain = current_sentence  # Any remaining characters form the incomplete sentence
    return sentences, remain


async def _send_cmd(
    ten_env: AsyncTenEnv, cmd_name: str, dest: str, payload: Any = None
) -> tuple[Optional[CmdResult], Optional[TenError]]:
    """
    Convenient method to send a command with a payload within app/graph w/o need to create a connection.
    Note: extension using this approach will contain logics that are meaningful for this graph only,
    as it will assume the target extension already exists in the graph.
    For generate purpose extension, it should try to prevent using this method.
    """
    cmd = Cmd.create(cmd_name)
    loc = Loc("", "", dest)
    cmd.set_dests([loc])
    if payload is not None:
        cmd.set_property_from_json(None, json.dumps(payload))
    ten_env.log_debug(f"send_cmd: cmd_name {cmd_name}, dest {dest}")

    return await ten_env.send_cmd(cmd)


async def _send_cmd_ex(
    ten_env: AsyncTenEnv, cmd_name: str, dest: str, payload: Any = None
) -> AsyncGenerator[tuple[Optional[CmdResult], Optional[TenError]], None]:
    """Convenient method to send a command with a payload within app/graph w/o need to create a connection.
    Note: extension using this approach will contain logics that are meaningful for this graph only,
    as it will assume the target extension already exists in the graph.
    For generate purpose extension, it should try to prevent using this method.
    """
    cmd = Cmd.create(cmd_name)
    loc = Loc("", "", dest)
    cmd.set_dests([loc])
    if payload is not None:
        cmd.set_property_from_json(None, json.dumps(payload))
    ten_env.log_debug(f"send_cmd_ex: cmd_name {cmd_name}, dest {dest}")

    async for cmd_result, ten_error in ten_env.send_cmd_ex(cmd):
        if cmd_result:
            ten_env.log_debug(f"send_cmd_ex: cmd_result {cmd_result}")
            yield cmd_result, ten_error


async def _send_data(
    ten_env: AsyncTenEnv, data_name: str, dest: str, payload: Any = None
) -> Optional[TenError]:
    """Convenient method to send data with a payload within app/graph w/o need to create a connection.
    Note: extension using this approach will contain logics that are meaningful for this graph only,
    as it will assume the target extension already exists in the graph.
    For generate purpose extension, it should try to prevent using this method.
    """
    data = Data.create(data_name)
    loc = Loc("", "", dest)
    data.set_dests([loc])
    if payload is not None:
        data.set_property_from_json(None, json.dumps(payload))
    ten_env.log_debug(f"send_data: data_name {data_name}, dest {dest}")
    return await ten_env.send_data(data)
