import aiohttp
import json
from typing import Optional, Any

from .config import CekuraMetricsConfig
from .session import Session


class CekuraClient:
    def __init__(self, config: CekuraMetricsConfig):
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "X-CEKURA-API-KEY": self.config.api_key,
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=30),
            )
        return self._session
    
    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
    
    async def send_session(self, session: Session) -> dict[str, Any]:
        payload = session.to_observe_payload(
            agent_id=self.config.agent_id,
            assistant_id=self.config.assistant_id,
            metric_ids=self.config.metric_ids,
        )
        
        http_session = await self._get_session()
        
        async with http_session.post(
            self.config.observe_endpoint,
            json=payload,
        ) as response:
            response_text = await response.text()
            
            if response.status == 201:
                return json.loads(response_text)
            else:
                raise CekuraAPIError(
                    f"Failed to send session to Cekura: {response.status} - {response_text}",
                    status_code=response.status,
                    response_body=response_text,
                )


class CekuraAPIError(Exception):
    def __init__(self, message: str, status_code: int = 0, response_body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body
