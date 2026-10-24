#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
#

import asyncio
from typing import Callable, Optional
from ten_ai_base.message import ModuleError, ModuleErrorCode


class ReconnectManager:
    """Manages reconnection attempts with exponential backoff"""

    def __init__(
        self,
        max_attempts: int = 5,
        base_delay: float = 0.5,
        logger: Optional[any] = None,
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.current_attempts = 0
        self.logger = logger

    def can_retry(self) -> bool:
        """Check if more retry attempts are available"""
        return self.current_attempts < self.max_attempts

    def mark_connection_successful(self) -> None:
        """Reset retry counter after successful connection"""
        self.current_attempts = 0

    def get_attempts_info(self) -> str:
        """Get current attempts information"""
        return f"{self.current_attempts}/{self.max_attempts}"

    async def handle_reconnect(
        self,
        connection_func: Callable,
        error_handler: Optional[Callable] = None,
    ) -> bool:
        """Handle reconnection with exponential backoff

        Args:
            connection_func: Async function to establish connection
            error_handler: Optional async function to handle errors

        Returns:
            bool: True if reconnection initiated, False if max attempts reached
        """
        if not self.can_retry():
            if self.logger:
                self.logger.log_error(
                    f"Max reconnection attempts ({self.max_attempts}) reached"
                )
            if error_handler:
                await error_handler(
                    ModuleError(
                        module="asr",
                        code=ModuleErrorCode.FATAL_ERROR.value,
                        message=f"Max reconnection attempts ({self.max_attempts}) reached",
                    )
                )
            return False

        self.current_attempts += 1
        delay = self.base_delay * (2 ** (self.current_attempts - 1))

        if self.logger:
            self.logger.log_info(
                f"Reconnecting in {delay}s (attempt {self.current_attempts}/{self.max_attempts})"
            )

        await asyncio.sleep(delay)

        try:
            await connection_func()
            return True
        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Reconnection attempt failed: {e}")
            if error_handler:
                await error_handler(
                    ModuleError(
                        module="asr",
                        code=ModuleErrorCode.NON_FATAL_ERROR.value,
                        message=f"Reconnection attempt {self.current_attempts} failed: {str(e)}",
                    )
                )
            return False
