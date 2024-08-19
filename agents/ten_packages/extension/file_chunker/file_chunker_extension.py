#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-05.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
from ten import (
    Extension,
    TenEnv,
    Cmd,
    StatusCode,
    CmdResult,
)
from typing import List, Any
from .log import logger
from llama_index.core import SimpleDirectoryReader
from llama_index.core.node_parser import SentenceSplitter
import json
from datetime import datetime
import uuid, math
import queue, threading

CMD_FILE_CHUNK = "file_chunk"
UPSERT_VECTOR_CMD = "upsert_vector"
FILE_CHUNKED_CMD = "file_chunked"

# TODO: configable
CHUNK_SIZE = 200
CHUNK_OVERLAP = 20
BATCH_SIZE = 5


def batch(nodes, size):
    batch_texts = []
    for n in nodes:
        batch_texts.append(n.text)
        if len(batch_texts) == size:
            yield batch_texts[:]
            batch_texts.clear()
    if batch_texts:
        yield batch_texts


class FileChunkerExtension(Extension):
    def __init__(self, name: str):
        super().__init__(name)

        self.counters = {}
        self.expected = {}
        self.new_collection_name = ""
        self.file_chunked_event = threading.Event()

        self.thread = None
        self.queue = queue.Queue()
        self.stop = False

    def generate_collection_name(self) -> str:
        """
        follow rules: ^[a-z]+[a-z0-9_]*
        """

        return "coll_" + uuid.uuid1().hex.lower()

    def split(self, path: str) -> List[Any]:

        # load pdf file by path
        documents = SimpleDirectoryReader(
            input_files=[path], filename_as_id=True
        ).load_data()

        # split pdf file into chunks
        splitter = SentenceSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
        )
        nodes = splitter.get_nodes_from_documents(documents)
        logger.info(
            "file {} pages count {}, chunking count {}".format(
                path, len(documents), len(nodes)
            )
        )
        return nodes

    def create_collection(self, ten: TenEnv, collection_name: str, wait: bool):
        cmd_out = Cmd.create("create_collection")
        cmd_out.set_property_string("collection_name", collection_name)

        wait_event = threading.Event()
        ten.send_cmd(
            cmd_out,
            lambda ten, result: wait_event.set(),
        )
        if wait:
            wait_event.wait()

    def embedding(self, ten: TenEnv, path: str, texts: List[str]):
        logger.info(
            "generate embeddings for the file: {}, with batch size: {}".format(
                path, len(texts)
            )
        )

        cmd_out = Cmd.create("embed_batch")
        cmd_out.set_property_from_json("inputs", json.dumps(texts))
        ten.send_cmd(
            cmd_out,
            lambda ten, result: self.vector_store(
                ten, path, texts, result
            ),  # TODO: deal with error
        )

    def vector_store(self, ten: TenEnv, path: str, texts: List[str], result: CmdResult):
        logger.info("vector store start for one splitting of the file {}".format(path))
        file_name = path.split("/")[-1]
        embed_output_json = result.get_property_string("embeddings")
        embed_output = json.loads(embed_output_json)
        cmd_out = Cmd.create(UPSERT_VECTOR_CMD)
        cmd_out.set_property_string("collection_name", self.new_collection_name)
        cmd_out.set_property_string("file_name", file_name)
        embeddings = [record["embedding"] for record in embed_output]
        content = []
        for text, embedding in zip(texts, embeddings):
            content.append({"text": text, "embedding": embedding})
        cmd_out.set_property_string("content", json.dumps(content))
        # logger.info(json.dumps(content))
        ten.send_cmd(cmd_out, lambda ten, result: self.file_chunked(ten, path))

    def file_chunked(self, ten: TenEnv, path: str):
        if path in self.counters and path in self.expected:
            self.counters[path] += 1
            logger.info(
                "complete vector store for one splitting of the file: %s, current counter: %i, expected: %i",
                path,
                self.counters[path],
                self.expected[path],
            )
            if self.counters[path] == self.expected[path]:
                chunks_count = self.counters[path]
                del self.counters[path]
                del self.expected[path]
                logger.info(
                    "complete chunk for the file: {}, chunks_count {}".format(
                        path,
                        chunks_count,
                    )
                )
                cmd_out = Cmd.create(FILE_CHUNKED_CMD)
                cmd_out.set_property_string("path", path)
                cmd_out.set_property_string("collection", self.new_collection_name)
                ten.send_cmd(
                    cmd_out,
                    lambda ten, result: logger.info("send_cmd done"),
                )
                self.file_chunked_event.set()
        else:
            logger.error("missing counter for the file path: %s", path)

    def on_cmd(self, ten: TenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        if cmd_name == CMD_FILE_CHUNK:
            path = cmd.get_property_string("path")

            collection = None
            try:
                collection = cmd.get_property_string("collection")
            except Exception as e:
                logger.warning("missing collection property in cmd {}".format(cmd_name))

            self.queue.put((path, collection))  # make sure files are processed in order
        else:
            logger.info("unknown cmd {}".format(cmd_name))

        cmd_result = CmdResult.create(StatusCode.OK)
        cmd_result.set_property_string("detail", "ok")
        ten.return_result(cmd_result, cmd)

    def async_handler(self, ten: TenEnv) -> None:
        while not self.stop:
            value = self.queue.get()
            if value is None:
                break
            path, collection = value

            # start processing the file
            start_time = datetime.now()
            if collection is None:
                collection = self.generate_collection_name()
                logger.info("collection {} generated".format(collection))
            logger.info("start processing {}, collection {}".format(path, collection))

            # create collection
            self.create_collection(ten, collection, True)
            logger.info("collection {} created".format(collection))

            # split
            nodes = self.split(path)

            # reset counters and events
            self.new_collection_name = collection
            self.expected[path] = math.ceil(len(nodes) / BATCH_SIZE)
            self.counters[path] = 0
            self.file_chunked_event.clear()

            # trigger embedding and vector storing in parallel
            for texts in list(batch(nodes, BATCH_SIZE)):
                self.embedding(ten, path, texts)

            # wait for all chunks to be processed
            self.file_chunked_event.wait()

            logger.info(
                "finished processing {}, collection {}, cost {}ms".format(
                    path,
                    collection,
                    int((datetime.now() - start_time).total_seconds() * 1000),
                )
            )

    def on_start(self, ten: TenEnv) -> None:
        logger.info("on_start")

        self.stop = False
        self.thread = threading.Thread(target=self.async_handler, args=[ten])
        self.thread.start()

        ten.on_start_done()

    def on_stop(self, ten: TenEnv) -> None:
        logger.info("on_stop")

        self.stop = True
        if self.thread is not None:
            while not self.queue.empty():
                self.queue.get()
            self.queue.put(None)
            self.thread.join()
            self.thread = None

        ten.on_stop_done()
