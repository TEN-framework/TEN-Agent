#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-08.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#

from ten import (
    AudioFrame,
    VideoFrame,
    Extension,
    TenEnv,
    Cmd,
    StatusCode,
    CmdResult,
    Data,
)
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import datetime
import asyncio
import queue
import threading
import json
from .log import logger
from typing import List

DATA_IN_TEXT_DATA_PROPERTY_IS_FINAL = "is_final"
DATA_IN_TEXT_DATA_PROPERTY_TEXT = "text"
DATA_IN_TEXT_DATA_PROPERTY_STREAM_ID = "stream_id"

PROPERTY_CREDENTIALS = "credentials"
PROPERTY_CHANNEL_NAME = "channel_name"
PROPERTY_COLLECTION_NAME = "collection_name"
PROPERTY_TTL = "ttl"

RETRIEVE_CMD = "retrieve"
CMD_OUT_PROPERTY_RESPONSE = "response"
DOC_EXPIRE_PATH = "expireAt"
DOC_CONTENTS_PATH = "contents"
CONTENT_ID_PATH = "id"
CONTENT_TS_PATH = "ts"
CONTENT_INPUT_PATH = "input"
DEFAULT_TTL = 1 # days

def get_current_time():
    # Get the current time
    start_time = datetime.datetime.now()
    # Get the number of microseconds since the Unix epoch
    unix_microseconds = int(start_time.timestamp() * 1_000_000)
    return unix_microseconds

def order_by_ts(contents: List[str]) -> List[str]:
    tmp = []
    for c in contents:
        tmp.append(json.loads(c))
    sorted_contents = sorted(tmp, key=lambda x: x[CONTENT_TS_PATH])
    res = []
    for sc in sorted_contents:
        res.append(json.dumps({CONTENT_ID_PATH: sc[CONTENT_ID_PATH], CONTENT_INPUT_PATH: sc[CONTENT_INPUT_PATH]}))
    return res

@firestore.transactional
def update_in_transaction(transaction, doc_ref, content):
    transaction.update(doc_ref, content)

@firestore.transactional
def read_in_transaction(transaction, doc_ref):
    doc = doc_ref.get(transaction=transaction)
    if doc.exists:
        return doc.to_dict()
    return None

class TSDBFirestoreExtension(Extension):
    def __init__(self, name: str):
        super().__init__(name)
        self.stopped = False
        self.thread = None
        self.queue = queue.Queue()
        self.stopEvent = asyncio.Event()
        self.cmd_thread = None
        self.loop = None
        self.credentials = None
        self.channel_name = ""
        self.collection_name = ""
        self.ttl = DEFAULT_TTL
        self.client = None
        self.document_ref = None

    async def __thread_routine(self, ten_env: TenEnv):
        logger.info("__thread_routine start")
        self.loop = asyncio.get_running_loop()
        ten_env.on_start_done()
        await self.stopEvent.wait()

    async def stop_thread(self):
        self.stopEvent.set()

    def on_init(self, ten_env: TenEnv) -> None:
        logger.info("TSDBFirestoreExtension on_init")
        ten_env.on_init_done()

    def on_start(self, ten_env: TenEnv) -> None:
        logger.info("TSDBFirestoreExtension on_start")

        try:
            self.credentials = ten_env.get_property_to_json(PROPERTY_CREDENTIALS)
        except Exception as err:
            logger.error(f"GetProperty required {PROPERTY_CREDENTIALS} failed, err: {err}")
            return 
        
        try:
            self.channel_name = ten_env.get_property_string(PROPERTY_CHANNEL_NAME)
        except Exception as err:
            logger.error(f"GetProperty required {PROPERTY_CHANNEL_NAME} failed, err: {err}")
            return 

        try:
            self.collection_name = ten_env.get_property_string(PROPERTY_COLLECTION_NAME)
        except Exception as err:
            logger.error(f"GetProperty required {PROPERTY_COLLECTION_NAME} failed, err: {err}")
            return

        # start firestore db
        cred = credentials.Certificate(self.credentials)
        firebase_admin.initialize_app(cred)
        self.client = firestore.client()

        self.document_ref = self.client.collection(self.collection_name).document(self.channel_name)
        # update ttl
        expiration_time = datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=self.ttl)
        exists = self.document_ref.get().exists
        if exists:
            self.document_ref.update(
                {
                    DOC_EXPIRE_PATH: expiration_time
                }
            )
            logger.info(f"reset document ttl, {self.ttl} day(s), for the channel {self.channel_name}")
        else:
            # not exists yet, set to create one
            self.document_ref.set(
                {
                    DOC_EXPIRE_PATH: expiration_time
                }
            )
            logger.info(f"create new document and set ttl, {self.ttl} day(s), for the channel {self.channel_name}")

        # start the loop to handle data in 
        self.thread = threading.Thread(target=self.async_handle, args=[ten_env])
        self.thread.start()

        # start the loop to handle cmd in
        self.cmd_thread = threading.Thread(
            target=asyncio.run, args=(self.__thread_routine(ten_env),)
        )
        self.cmd_thread.start()

    def async_handle(self, ten_env: TenEnv) -> None:
        while not self.stopped:
            try:
                value = self.queue.get()
                if value is None:
                    logger.info("exit handle loop")
                    break
                ts, input, id = value
                content_str = json.dumps({CONTENT_ID_PATH: id, CONTENT_INPUT_PATH: input, CONTENT_TS_PATH: ts})
                update_in_transaction(
                    self.client.transaction(),
                    self.document_ref, 
                    {
                        DOC_CONTENTS_PATH: firestore.ArrayUnion([content_str])
                    }
                )
                logger.info(f"append {content_str} to firestore document {self.channel_name}")
            except Exception as e:
                logger.exception("Failed to store chat contents")

    def on_stop(self, ten_env: TenEnv) -> None:
        logger.info("TSDBFirestoreExtension on_stop")
        
        # clear the queue and stop the thread to process data in
        self.stopped = True
        while not self.queue.empty():
            self.queue.get()
        self.queue.put(None)
        if self.thread is not None:
            self.thread.join()
            self.thread = None

        # stop the thread to process cmd in
        if self.cmd_thread is not None and self.cmd_thread.is_alive():
            asyncio.run_coroutine_threadsafe(self.stop_thread(), self.loop)
            self.cmd_thread.join()
            self.cmd_thread = None

        ten_env.on_stop_done()

    def on_deinit(self, ten_env: TenEnv) -> None:
        logger.info("TSDBFirestoreExtension on_deinit")
        ten_env.on_deinit_done()

    def on_cmd(self, ten_env: TenEnv, cmd: Cmd) -> None:
        try:
            cmd_name = cmd.get_name()
            logger.info("on_cmd name {}".format(cmd_name))
            if cmd_name == RETRIEVE_CMD:
                asyncio.run_coroutine_threadsafe(
                    self.retrieve(ten_env, cmd), self.loop
                )
            else:
                logger.info("unknown cmd name {}".format(cmd_name))
                cmd_result = CmdResult.create(StatusCode.ERROR)
                ten_env.return_result(cmd_result, cmd)
        except Exception as e:
            ten_env.return_result(CmdResult.create(StatusCode.ERROR), cmd)
        
    async def retrieve(self, ten_env: TenEnv, cmd: Cmd):
        doc_dict = read_in_transaction(self.client.transaction(), self.document_ref)
        if doc_dict is not None:
            if DOC_CONTENTS_PATH in doc_dict:
                contents = doc_dict[DOC_CONTENTS_PATH]
                ret = CmdResult.create(StatusCode.OK)
                ret.set_property_from_json(CMD_OUT_PROPERTY_RESPONSE, order_by_ts(contents))
                ten_env.return_result(ret, cmd)
            else:
                logger.info(f"no contents for the channel {self.channel_name}")
                ten_env.return_result(CmdResult.create(StatusCode.ERROR), cmd)
        else:
            logger.info(f"no corresponding document found for the channel {self.channel_name}")
            ten_env.return_result(CmdResult.create(StatusCode.ERROR), cmd)      

    def on_data(self, ten_env: TenEnv, data: Data) -> None:
        logger.info(f"TSDBFirestoreExtension on_data")

        # assume 'data' is an object from which we can get properties
        try:
            is_final = data.get_property_bool(DATA_IN_TEXT_DATA_PROPERTY_IS_FINAL)
            if not is_final:
                logger.info("ignore non-final input")
                return
        except Exception as err:
            logger.info(
                f"OnData GetProperty {DATA_IN_TEXT_DATA_PROPERTY_IS_FINAL} failed, err: {err}"
            )
            return
        # get input text
        try:
            input_text = data.get_property_string(DATA_IN_TEXT_DATA_PROPERTY_TEXT)
            if not input_text:
                logger.info("ignore empty text")
                return
            logger.info(f"OnData input text: [{input_text}]")
        except Exception as err:
            logger.info(
                f"OnData GetProperty {DATA_IN_TEXT_DATA_PROPERTY_TEXT} failed, err: {err}"
            )
            return
        # get stream id
        try:
            stream_id = data.get_property_int(DATA_IN_TEXT_DATA_PROPERTY_STREAM_ID)
            if not stream_id:
                logger.warning("ignore empty stream_id")
                return
        except Exception as err:
            logger.info(
                f"OnData GetProperty {DATA_IN_TEXT_DATA_PROPERTY_STREAM_ID} failed, err: {err}"
            )
            return

        ts = get_current_time()
        self.queue.put((ts, input_text, stream_id))
    
    def on_audio_frame(self, ten_env: TenEnv, audio_frame: AudioFrame) -> None:
        pass

    def on_video_frame(self, ten_env: TenEnv, video_frame: VideoFrame) -> None:
        pass
