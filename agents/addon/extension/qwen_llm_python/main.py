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
from .log import logger

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
        self.ongoing = ""

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

    def need_interrupt(self, ts: datetime.time) -> bool:
        return self.outdateTs > ts and (self.outdateTs - ts).total_seconds() > 1
    
    def call(self, messages: List[Any]):
        logger.info("before call %s", messages)
        response = dashscope.Generation.call("qwen-max",
                                messages=messages,
                                result_format='message',  # set the result to be "message"  format.
                                stream=False, # set streaming output
                                incremental_output=False  # get streaming output incrementally
                                )
        if response.status_code == HTTPStatus.OK:
            self.on_msg(response.output.choices[0]['message']['role'], response.output.choices[0]['message']['content'])
            logger.info("on response %s", response.output.choices[0]['message']['content'])
        else:
            logger.info("Failed to get response %s", response)
    
    def call_with_stream(self, rte: Rte, ts :datetime.time, inputText: str, messages: List[Any]):
        if self.need_interrupt(ts):
            logger.warning("out of date, %s, %s", self.outdateTs, ts)
            return
        if len(self.ongoing) > 0:
            messages.append({'role':'assistant', 'content':self.ongoing})
        messages.append({'role':'user', 'content':inputText})
        logger.info("before call %s %s", messages, ts)

        responses = dashscope.Generation.call("qwen-max",
                                messages=messages,
                                result_format='message',  # set the result to be "message"  format.
                                stream=True, # set streaming output
                                incremental_output=True  # get streaming output incrementally
                                )
        total = ""
        partial = ""
        for response in responses:
            if self.need_interrupt(ts):
                if len(self.ongoing) > 0:
                    self.on_msg('user', inputText)
                    self.on_msg('assistant', self.ongoing)
                    self.ongoing = ''
                logger.warning("out of date, %s, %s", self.outdateTs, ts)
                return
            if response.status_code == HTTPStatus.OK:
                temp = response.output.choices[0]['message']['content']
                if len(temp) == 0:
                    continue
                partial += temp
                self.ongoing += temp
                if (isEnd(temp) and len(partial) > 10) or len(partial) > 50:
                    d = Data.create("text_data")
                    d.set_property_bool("end_of_segment", isEnd(partial))
                    d.set_property_string("text", partial)
                    rte.send_data(d)
                    total += partial
                    partial = ""
            else:
                logger.info('Request id: %s, Status code: %s, error code: %s, error message: %s' % (
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
        self.ongoing = ""
        self.on_msg("user", inputText)
        self.on_msg("assistant", total)
        logger.info("on response %s", total)
    
    def on_init(
        self, rte: Rte, manifest: MetadataInfo, property: MetadataInfo
    ) -> None:
        logger.info("QWenLLMExtension on_init")
        rte.on_init_done(manifest, property)

    def on_start(self, rte: Rte) -> None:
        logger.info("QWenLLMExtension on_start")
        self.api_key = rte.get_property_string("api_key")
        self.mode = rte.get_property_string("model")
        self.prompt = rte.get_property_string("prompt")
        self.max_history = rte.get_property_int("max_memory_length")

        dashscope.api_key = self.api_key
        self.thread = threading.Thread(target=self.async_handle, args=[rte])
        self.thread.start()
        rte.on_start_done()

    def on_stop(self, rte: Rte) -> None:
        logger.info("QWenLLMExtension on_stop")
        self.stopped = True
        self.queue.put(None)
        self.flush()
        self.thread.join()
        rte.on_stop_done()

    def on_deinit(self, rte: Rte) -> None:
        logger.info("QWenLLMExtension on_deinit")
        rte.on_deinit_done()

    def flush(self):
        logger.info("QWenLLMExtension flush")
        while not self.queue.empty():
            self.queue.get()

    def on_data(self, rte: Rte, data: Data) -> None:
        logger.info("QWenLLMExtension on_data")
        is_final = data.get_property_bool("is_final")
        if not is_final:
            logger.info("ignore non final")
            return
        
        inputText = data.get_property_string("text")
        if len(inputText) == 0:
            logger.info("ignore empty text")
            return
        
        ts = datetime.now()
        
        logger.info("on data %s, %s", inputText, ts)
        self.queue.put((inputText, ts))
    
    def async_handle(self, rte: Rte):
        while not self.stopped:
            try:
                value = self.queue.get()
                if value is None:
                    break
                inputText, ts = value
                if self.need_interrupt(ts):
                    continue
                logger.info("fetch from queue %s", inputText)
                history = self.get_messages()
                self.call_with_stream(rte, ts, inputText, history)
            except Exception as e:
                logger.exception(e)

    def on_cmd(self, rte: Rte, cmd: Cmd) -> None:
        logger.info("QWenLLMExtension on_cmd")
        cmd_json = cmd.to_json()
        logger.info("QWenLLMExtension on_cmd json: %s", cmd_json)

        cmdName = cmd.get_name()
        if cmdName == "flush":
            self.outdateTs = datetime.now()
            #self.flush()
            cmd_out = Cmd.create("flush")
            rte.send_cmd(cmd_out, lambda rte, result: print("QWenLLMExtensionAddon send_cmd done"))
        else:
            logger.info("unknown cmd %s", cmdName)

        cmd_result = CmdResult.create(StatusCode.OK)
        rte.return_result(cmd_result, cmd)

    def on_image_frame(self, rte: Rte, image_frame: ImageFrame) -> None:
        logger.info("QWenLLMExtension on_cmd")

@register_addon_as_extension("qwen_llm_python")
class QWenLLMExtensionAddon(Addon):
    def on_init(self, rte: Rte, manifest, property) -> None:
        logger.info("QWenLLMExtensionAddon on_init")
        rte.on_init_done(manifest, property)
        return

    def on_create_instance(self, rte: Rte, addon_name: str, context) -> Extension:
        logger.info("on_create_instance")
        rte.on_create_instance_done(QWenLLMExtension(addon_name), context)

    def on_deinit(self, rte: Rte) -> None:
        logger.info("QWenLLMExtensionAddon on_deinit")
        rte.on_deinit_done()
        return
