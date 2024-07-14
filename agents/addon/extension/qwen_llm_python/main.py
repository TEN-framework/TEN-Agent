#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-05.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
from rte_runtime_python import (
    Addon,
    Extension,
    register_addon_as_extension,
    Rte,
    Cmd,
    Data,
    StatusCode,
    CmdResult,
    MetadataInfo,
    RTE_PIXEL_FMT,
)
from rte_runtime_python.image_frame import ImageFrame
from typing import List, Any
import dashscope
import queue
from datetime import datetime
import threading
from http import HTTPStatus

def isEnd(content: str) -> bool:
    last = content[len(content)-1]
    return last == ',' or last == '，' or \
        last == '.' or last == '。' or \
		last == '?' or last == '？' or \
		last == '!' or last == '！'

class QWenLLMExtension(Extension):
    def __init__(self, name: str):
        super().__init__(name)
        self.history = []
        self.api_key = ""
        self.model = ""
        self.prompt = ""
        self.max_history = 10
        self.stopped = False
        self.thread = None
        self.outdateTs = datetime.now()

        self.queue = queue.Queue()
        self.mutex = threading.Lock()

    def on_msg(self, role: str, content: str) -> None:
        self.mutex.acquire()
        try:
            self.history.append({'role': role, 'content': content})
            if len(self.history) > self.max_history:
                self.history = self.history[1:]
        finally:
            self.mutex.release()

    def get_messages(self) -> List[Any]:
        messages = []
        if len(self.prompt) > 0:
            messages.append({'role': 'system', 'content': self.prompt})
        self.mutex.acquire()
        try:
            for h in self.history:
                messages.append(h)
        finally:
            self.mutex.release()
        return messages
        
    def call(self, messages: List[Any]):
        print("before call", messages)
        response = dashscope.Generation.call("qwen-max",
                                messages=messages,
                                result_format='message',  # set the result to be "message"  format.
                                stream=False, # set streaming output
                                incremental_output=False  # get streaming output incrementally
                                )
        if response.status_code == HTTPStatus.OK:
            self.on_msg(response.output.choices[0]['message']['role'], response.output.choices[0]['message']['content'])
            print("on response", response.output.choices[0]['message']['content'])
        else:
            print("Failed to get response", response)
    
    def call_with_stream(self, rte: Rte, ts :datetime.time, messages: List[Any]):
        print("before call", messages)
        if self.outdateTs > ts:
            return
        responses = dashscope.Generation.call("qwen-max",
                                messages=messages,
                                result_format='message',  # set the result to be "message"  format.
                                stream=True, # set streaming output
                                incremental_output=True  # get streaming output incrementally
                                )
        total = ""
        partial = ""
        for response in responses:
            if self.outdateTs > ts:
              return
            if response.status_code == HTTPStatus.OK:
                temp = response.output.choices[0]['message']['content']
                partial += temp
                if isEnd(temp):
                    d = Data.create("text_data")
                    d.set_property_bool("end_of_segment", isEnd(partial))
                    d.set_property_string("text", partial)
                    rte.send_data(d)
                    total += partial
                    partial = ""
            else:
                print('Request id: %s, Status code: %s, error code: %s, error message: %s' % (
                    response.request_id, response.status_code,
                    response.code, response.message
                ))
                return
        if len(partial) > 0:
            d = Data.create("text_data")
            d.set_property_bool("end_of_segment", True)
            d.set_property_string("text", partial)
            rte.send_data(d)
            total += partial
            partial = ""
        self.on_msg("assistant", total)
        print("on response", total)
    
    def on_init(
        self, rte: Rte, manifest: MetadataInfo, property: MetadataInfo
    ) -> None:
        print("QWenLLMExtension on_init")
        rte.on_init_done(manifest, property)

    def on_start(self, rte: Rte) -> None:
        print("QWenLLMExtension on_start")
        self.api_key = rte.get_property_string("api_key")
        self.mode = rte.get_property_string("model")
        self.prompt = rte.get_property_string("prompt")
        self.max_history = rte.get_property_int("max_memory_length")

        dashscope.api_key = self.api_key
        self.thread = threading.Thread(target=self.async_handle, args=[rte])
        self.thread.start()
        rte.on_start_done()

    def on_stop(self, rte: Rte) -> None:
        print("QWenLLMExtension on_stop")
        self.stopped = True
        self.flush()
        self.thread.join()
        rte.on_stop_done()

    def on_deinit(self, rte: Rte) -> None:
        print("QWenLLMExtension on_deinit")
        rte.on_deinit_done()

    def flush(self):
        print("QWenLLMExtension flush")
        while not self.queue.empty():
            self.queue.get()

    def on_data(self, rte: Rte, data: Data) -> None:
        print("QWenLLMExtension on_data")
        is_final = data.get_property_bool("is_final")
        if not is_final:
            print("ignore non final")
            return
        
        inputText = data.get_property_string("text")
        if len(inputText) == 0:
            print("ignore empty text")
            return
        
        ts = datetime.now()
        
        print("on data ", inputText, ts)
        self.queue.put((inputText, ts))
    
    def async_handle(self, rte: Rte):
        while not self.stopped:
            inputText, ts = self.queue.get()
            if self.outdateTs > ts:
                continue
            print("fetch from queue", inputText)
            self.on_msg("user", inputText)
            messages = self.get_messages()
            self.call_with_stream(rte, ts, messages)

    def on_cmd(self, rte: Rte, cmd: Cmd) -> None:
        print("QWenLLMExtension on_cmd")
        cmd_json = cmd.to_json()
        print("QWenLLMExtension on_cmd json: " + cmd_json)

        cmdName = cmd.get_name()
        if cmdName == "flush":
            self.outdateTs = datetime.now()
            self.flush()
        else:
            print("unknown cmd", cmdName)

        cmd_result = CmdResult.create(StatusCode.OK)
        rte.return_result(cmd_result, cmd)

    def on_image_frame(self, rte: Rte, image_frame: ImageFrame) -> None:
        print("QWenLLMExtension on_cmd")

@register_addon_as_extension("qwen_llm_python")
class QWenLLMExtensionAddon(Addon):
    def on_init(self, rte: Rte, manifest, property) -> None:
        print("QWenLLMExtensionAddon on_init")
        rte.on_init_done(manifest, property)
        return

    def on_create_instance(self, rte: Rte, addon_name: str) -> Extension:
        print("QWenLLMExtensionAddon on_create_instance")
        return QWenLLMExtension(addon_name)

    def on_deinit(self, rte: Rte) -> None:
        print("QWenLLMExtensionAddon on_deinit")
        rte.on_deinit_done()
        return
