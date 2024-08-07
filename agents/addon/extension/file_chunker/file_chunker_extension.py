#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-05.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
from rte import (
    Extension,
    RteEnv,
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

CMD_FILE_DOWNLOADED = "file_downloaded"
UPSERT_VECTOR_CMD = "upsert_vector"
FILE_CHUNKED_CMD = "file_chunked"
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
        logger.info("pages in pdf: {}, chunking count: {}", len(documents), len(nodes))
        return nodes

    def embedding(self, rte: RteEnv, path: str, texts: List[str]):
        logger.info(
            "generate embeddings for the file: {}, with batch size: {}".format(
                path, len(texts)
            )
        )

        cmd_out = Cmd.create("embed_batch")
        cmd_out.set_property_from_json("inputs", json.dumps(texts))
        rte.send_cmd(
            cmd_out, lambda rte, result: self.vector_store(rte, path, texts, result)
        )

    def vector_store(self, rte: RteEnv, path: str, texts: List[str], result: CmdResult):
        logger.info("vector store start for file {}".format(path))
        file_name = path.split("/")[-1]
        embedOutputJson = result.get_property_string("output")
        embedOutput = json.loads(embedOutputJson)
        cmd_out = Cmd.create(UPSERT_VECTOR_CMD)
        cmd_out.set_property_string("collection_name", self.new_collection_name)
        cmd_out.set_property_string("file_name", file_name)
        embeddings = [record["embedding"] for record in embedOutput["embeddings"]]
        content = []
        for text, embedding in zip(texts, embeddings):
            content.append({"text": text, "embedding": embedding})
        cmd_out.set_property_string("content", json.dumps(content))
        rte.send_cmd(cmd_out, lambda rte, result: self.file_chunked(rte, path))

    def file_chunked(self, rte: RteEnv, path: str):
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
                    "complete chunk for the file: {}, chunks_count {}, latency {}ms ".format(
                        path,
                        chunks_count,
                        int((datetime.now() - self.start_time).total_seconds() * 1000),
                    )
                )
                cmd_out = Cmd.create(FILE_CHUNKED_CMD)
                cmd_out.set_property_string("path", path)
                cmd_out.set_property_string("collection_name", self.new_collection_name)
                rte.send_cmd(
                    cmd_out,
                    lambda rte, result: logger.info("send_cmd done"),
                )
                self.file_chunked_event.set()
        else:
            logger.error("missing counter for the file path: %s", path)

    def on_cmd(self, rte: RteEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        if cmd_name == CMD_FILE_DOWNLOADED:
            path = cmd.get_property_string("path")
            self.queue.put(path)  # make sure files are processed in order
        else:
            logger.info("unknown cmd {}".format(cmd_name))

        cmd_result = CmdResult.create(StatusCode.OK)
        cmd_result.set_property_string("detail", "ok")
        rte.return_result(cmd_result, cmd)

    def async_handler(self, rte: RteEnv) -> None:
        while not self.stop:
            path = self.queue.get()
            if path is None:
                break

            # start processing the file
            start_time = datetime.now()
            collection_name = self.generate_collection_name()
            logger.info(
                "start processing {}, collection_name {}".format(path, collection_name)
            )

            # split
            nodes = self.split(path)

            # reset counters and events
            self.new_collection_name = collection_name
            self.expected[path] = math.ceil(len(nodes) / BATCH_SIZE)
            self.counters[path] = 0
            self.file_chunked_event.clear()

            # trigger embedding and vector storing in parallel
            for texts in list(batch(nodes, BATCH_SIZE)):
                self.embedding(rte, path, texts)

            # wait for all chunks to be processed
            self.file_chunked_event.wait()

            logger.info(
                "finished processing {}, collection_name {}, cost {}ms".format(
                    path,
                    collection_name,
                    (datetime.now() - start_time).microseconds / 1000,
                )
            )

    def on_start(self, rte: RteEnv) -> None:
        logger.info("on_start")

        self.stop = False
        self.thread = threading.Thread(target=self.async_handler, args=[rte])
        self.thread.start()

        rte.on_start_done()

    def on_stop(self, rte: RteEnv) -> None:
        logger.info("on_stop")

        self.stop = True
        if self.thread is not None:
            while not self.queue.empty():
                self.queue.get()
            self.queue.put(None)
            self.thread.join()
            self.thread = None

        rte.on_stop_done()
