# -*- coding: utf-8 -*-

import asyncio
import threading
from typing import Coroutine
from concurrent.futures import Future


from alibabacloud_gpdb20160503.client import Client as gpdb20160503Client
from alibabacloud_tea_openapi import models as open_api_models


# maybe need multiple clients
class AliGPDBClient:
    def __init__(self, ten_env, access_key_id, access_key_secret, endpoint):
        self.stopEvent = asyncio.Event()
        self.loop = None
        self.tasks = asyncio.Queue()
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.endpoint = endpoint
        self.client = self.create_client()
        self.thread = threading.Thread(
            target=asyncio.run, args=(self.__thread_routine(),)
        )
        self.thread.start()
        self.ten_env = ten_env

    async def stop_thread(self):
        self.stopEvent.set()

    def create_client(self) -> gpdb20160503Client:
        config = open_api_models.Config(
            access_key_id=self.access_key_id,
            access_key_secret=self.access_key_secret,
            endpoint=self.endpoint,
        )
        return gpdb20160503Client(config)

    def get(self) -> gpdb20160503Client:
        return self.client

    def close(self):
        if (self.loop is not None) and self.thread.is_alive():
            self.stopEvent.set()
            asyncio.run_coroutine_threadsafe(self.stop_thread(), self.loop)
            self.thread.join()

    async def __thread_routine(self):
        self.ten_env.log_info("client __thread_routine start")
        self.loop = asyncio.get_running_loop()
        tasks = set()
        while not self.stopEvent.is_set():
            if not self.tasks.empty():
                coro, future = await self.tasks.get()
                try:
                    task = asyncio.create_task(coro)
                    tasks.add(task)
                    task.add_done_callback(lambda t: future.set_result(t.result()))
                except Exception as e:
                    future.set_exception(e)
            elif tasks:
                done, tasks = await asyncio.wait(
                    tasks, return_when=asyncio.FIRST_COMPLETED
                )
                for task in done:
                    if task.exception():
                        self.ten_env.log_error(f"task exception: {task.exception()}")
                        future.set_exception(task.exception())
            else:
                await asyncio.sleep(0.1)
        self.ten_env.log_info("client __thread_routine end")

    async def submit_task(self, coro: Coroutine) -> Future:
        future = Future()
        await self.tasks.put((coro, future))
        return future

    def submit_task_with_new_thread(self, coro: Coroutine) -> Future:
        future = Future()

        def run_coro_in_new_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(coro)
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)
            finally:
                loop.close()

        thread = threading.Thread(target=run_coro_in_new_thread)
        thread.start()
        return future
