# create a async client of coze here which is cancelable

import aiohttp
from typing import Optional, List, Dict, AsyncIterator, Any

from cozepy import Message, ChatEvent, Auth, COZE_COM_BASE_URL, ChatEventType, Chat
import traceback

def chat_stream_handler(event:str, event_data:Any) -> ChatEvent:
    if event == ChatEventType.DONE:
        raise StopAsyncIteration
    elif event == ChatEventType.ERROR:
        raise Exception(f"error event: {event_data}")  # TODO: error struct format
    elif event in [
        ChatEventType.CONVERSATION_MESSAGE_DELTA,
        ChatEventType.CONVERSATION_MESSAGE_COMPLETED,
    ]:
        return ChatEvent(event=event, message=Message.model_validate_json(event_data))
    elif event in [
        ChatEventType.CONVERSATION_CHAT_CREATED,
        ChatEventType.CONVERSATION_CHAT_IN_PROGRESS,
        ChatEventType.CONVERSATION_CHAT_COMPLETED,
        ChatEventType.CONVERSATION_CHAT_FAILED,
        ChatEventType.CONVERSATION_CHAT_REQUIRES_ACTION,
    ]:
        return ChatEvent(event=event, chat=Chat.model_validate_json(event_data))
    else:
        raise ValueError(f"invalid chat.event: {event}, {event_data}")

class AsyncChat(object):
    def __init__(self, auth: Auth, base_url: str):
        self._auth = auth
        self._base_url = base_url
        self._session = aiohttp.ClientSession()
    
    async def stream(
        self,
        *,
        bot_id: str,
        user_id: str,
        additional_messages: Optional[List[Message]] = None,
        custom_variables: Optional[Dict[str, str]] = None,
        auto_save_history: bool = True,
        meta_data: Optional[Dict[str, str]] = None,
        conversation_id: Optional[str] = None,
    ) -> AsyncIterator[ChatEvent]:
        try:
            url = f"{self._base_url}/v3/chat"
            headers = {}
            self._auth.authentication(headers)
            params = {
                "bot_id": bot_id,
                "user_id": user_id,
                "additional_messages": [i.model_dump() for i in additional_messages] if additional_messages else [],
                "stream": True,
                "custom_variables": custom_variables,
                "auto_save_history": auto_save_history,
                "conversation_id": conversation_id if conversation_id else None,
                "meta_data": meta_data,
            }
            async with self._session.post(url, json=params, headers=headers) as response:
                async for line in response.content:
                    if line:
                        decoded_line = line.decode('utf-8').strip()
                        if decoded_line:
                            event_data = decoded_line.split(":", 1)
                            if len(event_data) == 2:
                                if event_data[0] == "event":
                                    event = event_data[1]
                                    continue
                                elif event_data[0] == "data":
                                    data = event_data[1]
                                    yield chat_stream_handler(event=event.strip(), event_data=data.strip())
        except StopAsyncIteration:
            pass
    
    async def close(self):
        await self._session.close()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

class AsyncClient(object):
    def __init__(self, auth: Auth, base_url: str = COZE_COM_BASE_URL):
        self.auth = auth
        self.base_url = base_url

    def chat(self) -> AsyncChat:
        return AsyncChat(auth=self.auth, base_url=self.base_url)
    