import asyncio
from typing import Callable, Awaitable, Optional
from ten_ai_base.message import ModuleError, ModuleErrorCode
from .const import MODULE_NAME_ASR


class ReconnectManager:
    """
    Manages reconnection attempts with fixed retry limit and exponential backoff strategy.

    Features:
    - Fixed retry limit (default: 5 attempts)
    - Exponential backoff strategy: 300ms, 600ms, 1.2s, 2.4s, 4.8s
    - Automatic counter reset after successful connection
    - Detailed logging for monitoring and debugging
    """

    def __init__(
        self,
        max_attempts: int = 5,
        base_delay: float = 0.3,  # 300 milliseconds
        logger=None,
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.logger = logger

        # State tracking
        self.attempts = 0
        self._connection_successful = False

    def reset_counter(self):
        """Reset reconnection counter"""
        self.attempts = 0
        if self.logger:
            self.logger.log_debug("Reconnect counter reset")

    def mark_connection_successful(self):
        """Mark connection as successful and reset counter"""
        self._connection_successful = True
        self.reset_counter()

    def can_retry(self) -> bool:
        """Check if more reconnection attempts are allowed"""
        return self.attempts < self.max_attempts

    def get_attempts_info(self) -> dict:
        """Get current reconnection attempts information"""
        return {
            "current_attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "can_retry": self.can_retry(),
        }

    async def handle_reconnect(
        self,
        connection_func: Callable[[], Awaitable[None]],
        error_handler: Optional[
            Callable[[ModuleError], Awaitable[None]]
        ] = None,
    ) -> bool:
        """
        Handle a single reconnection attempt with backoff delay.

        Args:
            connection_func: Async function to establish connection
            error_handler: Optional async function to handle errors

        Returns:
            True if connection function executed successfully, False if attempt failed
            Note: Actual connection success is determined by callback calling mark_connection_successful()
        """
        if not self.can_retry():
            if self.logger:
                self.logger.log_error(
                    f"Maximum reconnection attempts ({self.max_attempts}) reached. No more attempts allowed."
                )
            if error_handler:
                await error_handler(
                    ModuleError(
                        module=MODULE_NAME_ASR,
                        code=ModuleErrorCode.FATAL_ERROR.value,
                        message=f"Failed to reconnect after {self.max_attempts} attempts",
                    )
                )
            return False

        self._connection_successful = False
        self.attempts += 1

        # Calculate exponential backoff delay: 2^(attempts-1) * base_delay
        delay = self.base_delay * (2 ** (self.attempts - 1))

        if self.logger:
            self.logger.log_warn(
                f"Attempting reconnection #{self.attempts}/{self.max_attempts} "
                f"after {delay} seconds delay..."
            )

        try:
            await asyncio.sleep(delay)
            await connection_func()

            # Connection function completed successfully
            # Actual connection success will be determined by callback
            if self.logger:
                self.logger.log_debug(
                    f"Connection function completed for attempt #{self.attempts}"
                )
            return True

        except Exception as e:
            if self.logger:
                self.logger.log_error(
                    f"Reconnection attempt #{self.attempts} failed: {e}"
                )

            # If this was the last attempt, send error
            if self.attempts >= self.max_attempts:
                if error_handler:
                    await error_handler(
                        ModuleError(
                            module=MODULE_NAME_ASR,
                            code=ModuleErrorCode.FATAL_ERROR.value,
                            message=f"All reconnection attempts failed. Last error: {str(e)}",
                        )
                    )

            return False
