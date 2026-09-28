import asyncio
import websockets
from abc import ABC, abstractmethod
from contextlib import suppress
import logging
from ten_ai_base.utils import redact_url
from .log import get_logger
import time


class WebSocketClient(ABC):
    """
    A reusable and robust WebSocket client base class.
    It handles connection, automatic reconnection, concurrent read/write operations, and graceful shutdown logic.
    Subclasses need to implement the hook methods: on_open, on_message, on_close, and on_error.
    """

    def __init__(
        self,
        uri: str,
        auto_reconnect: bool = True,
        reconnect_delay: int = 1,
        reconnect_max_retries: int = 10,
        reconnect_max_delay: int = 60,
        reconnect_delay_multiplier: int = 2,
        reconnect_timeout: int = 0,
        logger: logging.Logger | None = None,
        keep_alive_interval: int | None = None,
        keep_alive_data: str | bytes | None = None,
        **kwargs,
    ):
        """
        Initialize the WebSocket client.

        Args:
            uri: WebSocket connection URI
            auto_reconnect: Whether to automatically reconnect on connection loss
            reconnect_delay: Reconnection delay in seconds
            reconnect_max_retries: Maximum number of reconnection attempts, 0 means infinite reconnection
            reconnect_max_delay: Maximum reconnection delay in seconds, 0 means no limit
            reconnect_delay_multiplier: Reconnection delay multiplier, each reconnection delay is multiplied by this factor
            kwargs: Additional parameters passed to websockets.connect
        """
        self._uri = uri
        self._kwargs = kwargs
        self._auto_reconnect = auto_reconnect
        self._reconnect_initial_delay = reconnect_delay
        self._reconnect_max_retries = reconnect_max_retries
        self._reconnect_max_delay = reconnect_max_delay
        self._reconnect_delay_multiplier = reconnect_delay_multiplier
        self._reconnect_timeout = reconnect_timeout
        self._keep_alive_interval = keep_alive_interval
        self._keep_alive_data = (
            keep_alive_data if keep_alive_data is not None else b""
        )
        self._is_connected = False

        if logger is None:
            self._logger = get_logger()
        else:
            self._logger = logger

        self._reconnect_retries = 0
        self._reconnect_delay = self._reconnect_initial_delay
        self._reconnect_total_delay = 0
        self._last_send_time = 0
        self._websocket: websockets.ClientConnection | None = None
        self._message_queue: asyncio.Queue[str | bytes] = asyncio.Queue()
        self._shutdown_event = asyncio.Event()
        self._main_task: asyncio.Task | None = None

    # Abstract methods
    async def on_open(self):
        """Called when WebSocket connection is successfully established."""

    @abstractmethod
    async def on_message(self, message: str | bytes):
        """Called when a message is received from the server."""
        raise NotImplementedError

    async def on_close(self, code: int | None, reason: str | None):
        """Called when WebSocket connection is closed."""

    async def on_error(self, error: Exception):
        """Called when a connection or communication error occurs."""

    async def on_disconnect(self):
        """Called when the client is disconnected."""

    async def on_reconnect(self):
        """Called before reconnecting."""

    # Internal methods

    async def _receiver_handler(self):
        """Handle received messages and call on_message and on_close when appropriate."""
        while not self._shutdown_event.is_set():
            try:
                if self._websocket is None:
                    break
                message = await self._websocket.recv()
                await self.on_message(message)
            except websockets.exceptions.ConnectionClosed:
                assert self._websocket is not None
                self._logger.warning(
                    f"Receiver: Connection closed (code={self._websocket.close_code}, reason='{self._websocket.close_reason}')."
                )
                await self.on_close(
                    self._websocket.close_code, self._websocket.close_reason
                )
                break  # Exit loop, let main loop handle reconnection
            except Exception as e:
                self._logger.error(
                    f"Receiver: An unexpected error occurred: {e}"
                )
                await self.on_error(e)
                break

    async def _sender_handler(self):
        """Get messages from queue and send them."""
        while not self._shutdown_event.is_set():
            if not self.is_connected():
                await asyncio.sleep(0.01)
                continue
            try:
                message = await asyncio.wait_for(
                    self._message_queue.get(), timeout=1.0
                )
                if self._websocket is None:
                    break
                await self._websocket.send(message)
                self._message_queue.task_done()
                self._last_send_time = time.time()
            except asyncio.TimeoutError:
                continue
            except websockets.exceptions.ConnectionClosed:
                self._logger.warning(
                    "Sender: Connection closed, cannot send message."
                )
                # Put message back in queue for retry after reconnection
                # Note: If queue is large, more complex logic may be needed here
                # await self._message_queue.put(message)
                break
            except Exception as e:
                self._logger.error(f"Sender: An unexpected error occurred: {e}")
                await self.on_error(e)
                break

    async def _keep_alive_handler(self):
        """Send keep-alive data to the server."""
        while not self._shutdown_event.is_set():
            await asyncio.sleep(1)
            if self._keep_alive_interval is not None:
                if (
                    time.time() - self._last_send_time
                    > self._keep_alive_interval
                ):
                    await self.send(self._keep_alive_data)
                    self._last_send_time = time.time()

    async def _run(self):
        """Main run loop, handles connection and automatic reconnection."""
        while not self._shutdown_event.is_set():
            try:
                self._logger.info(
                    f"Attempting to connect to {redact_url(self._uri)}..."
                )
                async with websockets.connect(
                    self._uri, logger=self._logger, **self._kwargs
                ) as websocket:
                    self._websocket = websocket
                    self._logger.info("Connection established.")
                    # Reset reconnection state
                    self._reconnect_delay = self._reconnect_initial_delay
                    self._reconnect_total_delay = 0
                    self._reconnect_retries = 0
                    await self.on_open()
                    self._is_connected = True

                    receiver_task = asyncio.create_task(
                        self._receiver_handler()
                    )
                    sender_task = asyncio.create_task(self._sender_handler())
                    keep_alive_task = asyncio.create_task(
                        self._keep_alive_handler()
                    )

                    _, pending = await asyncio.wait(
                        [receiver_task, sender_task, keep_alive_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    if keep_alive_task in pending:
                        keep_alive_task.cancel()
                    if sender_task in pending:
                        sender_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await asyncio.gather(*pending)
                    await self.on_disconnect()
                    self._websocket = None
                    self._is_connected = False
            except (
                websockets.exceptions.WebSocketException,
                ConnectionRefusedError,
                OSError,
            ) as e:
                self._logger.warning(f"Connection failed: {e}")
                await self.on_error(e)
            except Exception as e:
                self._logger.error(
                    "Unexpected ASR client error: error_type=%s", type(e).__name__
                )
                await self.on_error(e)

            if not self._shutdown_event.is_set():
                if not self._auto_reconnect:
                    self._logger.info(
                        "Connection ended and auto_reconnect is disabled; "
                        "exiting run loop."
                    )
                    break
                if (
                    self._reconnect_max_retries > 0
                    and self._reconnect_retries > self._reconnect_max_retries
                ):
                    msg = f"Reached maximum reconnection attempts ({self._reconnect_max_retries}). Giving up."
                    self._logger.warning(msg)
                    raise RuntimeError(msg)
                if (
                    self._reconnect_timeout > 0
                    and self._reconnect_total_delay > self._reconnect_timeout
                ):
                    msg = f"Reached maximum reconnection timeout ({self._reconnect_timeout}). Giving up."
                    self._logger.warning(msg)
                    raise RuntimeError(msg)

                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_total_delay += self._reconnect_delay
                self._reconnect_retries += 1

                if self._reconnect_max_delay > 0:
                    self._reconnect_delay = min(
                        self._reconnect_delay
                        * self._reconnect_delay_multiplier,
                        self._reconnect_max_delay,
                    )
                else:
                    self._reconnect_delay = (
                        self._reconnect_delay * self._reconnect_delay_multiplier
                    )

                self._logger.info(
                    f"Will retry in {self._reconnect_delay:.2f} seconds..."
                )

                await self.on_reconnect()

        if self._websocket is not None:
            # on_disconnect may be not called when the connection is unexpected closed.
            await self.on_disconnect()
            self._websocket = None
        return

    # Public methods

    async def start(self):
        """Start the client and keep it running."""
        if self._main_task and not self._main_task.done():
            self._logger.warning("Client is already running.")
            return
        self._shutdown_event.clear()
        self._main_task = asyncio.create_task(self._run())
        await self._main_task

    async def stop(self):
        """Gracefully stop the client."""
        if not self._main_task or self._shutdown_event.is_set():
            self._logger.warning(
                "Client is not running or already shutting down."
            )
            return

        self._logger.info("Initiating shutdown...")
        self._shutdown_event.set()

        if (
            self._websocket
            and not self._websocket.state != websockets.State.CLOSED
        ):
            await self._websocket.close(
                code=1000, reason="Client shutting down"
            )

        # Wait for main task to complete
        if self._main_task:
            with suppress(asyncio.CancelledError):
                await self._main_task

        self._logger.info("Shutdown complete.")

    async def send(self, message: str | bytes):
        """
        Send a message to the server.
        This is a thread-safe async method that puts the message in a queue for sending.
        """
        await self._message_queue.put(message)

    def is_connected(self) -> bool:
        """Check if the client is alive."""
        return (
            not self._shutdown_event.is_set()
            and self._websocket is not None
            and self._websocket.state == websockets.State.OPEN
            and self._is_connected
        )

    def is_running(self) -> bool:
        """Check if the client main task is active."""
        return self._main_task is not None and not self._main_task.done()
