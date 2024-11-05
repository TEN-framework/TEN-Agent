# cartesia_wrapper.py

import asyncio
import websockets
import json
import base64
import logging
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CartesiaError(Exception):
    """Custom exception class for Cartesia-related errors."""
    pass

class CartesiaConfig:
    # Configuration class for Cartesia API
    def __init__(self, api_key, model_id, voice_id, sample_rate, cartesia_version):
        self.api_key = api_key
        self.model_id = model_id
        self.voice_id = voice_id
        self.sample_rate = sample_rate
        self.cartesia_version = cartesia_version

class CartesiaWrapper:
    # Wrapper class for Cartesia API interactions
    def __init__(self, config: CartesiaConfig):
        self.config = config
        self.websocket = None
        self.context_id = 0

    async def connect(self):
        # Establish WebSocket connection to Cartesia API
        ws_url = f"wss://api.cartesia.ai/tts/websocket?api_key={self.config.api_key}&cartesia_version={self.config.cartesia_version}"
        try:
            self.websocket = await websockets.connect(ws_url)
            logger.info("Connected to Cartesia WebSocket")
        except Exception as e:
            logger.error(f"Failed to connect to Cartesia API: {str(e)}")
            raise CartesiaError(f"Connection failed: {str(e)}")

    async def synthesize(self, text: str):
        # Synthesize speech from text using Cartesia API
        if not self.websocket:
            await self.connect()

        if text.startswith("PAUSE_"):
            # Handle custom pause marker
            try:
                duration_ms = int(text.split("_")[1])
                return self.generate_silence(duration_ms)
            except (IndexError, ValueError):
                logger.error(f"Invalid pause format: {text}")
                raise CartesiaError(f"Invalid pause format: {text}")

        self.context_id += 1
        request = {
            "context_id": f"context_{self.context_id}",
            "model_id": self.config.model_id,
            "transcript": text,
            "voice": {"mode": "id", "id": self.config.voice_id},
            "output_format": {
                "container": "raw",
                "encoding": "pcm_s16le",
                "sample_rate": int(self.config.sample_rate)
            },
            "language": "en",
            "add_timestamps": False
        }

        try:
            # Send synthesis request
            await self.websocket.send(json.dumps(request))

            # Receive and process audio chunks
            audio_data = bytearray()
            while True:
                response = await self.websocket.recv()
                message = json.loads(response)

                if message['type'] == 'chunk':
                    chunk_data = base64.b64decode(message['data'])
                    audio_data.extend(chunk_data)
                elif message['type'] == 'done':
                    break
                elif message['type'] == 'error':
                    raise CartesiaError(f"Synthesis error: {message.get('error', 'Unknown error')}")
                else:
                    logger.warning(f"Unknown message type: {message['type']}")

            return audio_data
        except websockets.exceptions.ConnectionClosed:
            # Handle connection errors and retry
            logger.error("WebSocket connection closed unexpectedly. Attempting to reconnect...")
            await self.connect()
            return await self.synthesize(text)  # Retry the synthesis after reconnecting
        except Exception as e:
            logger.error(f"Error during synthesis: {str(e)}")
            raise CartesiaError(f"Synthesis failed: {str(e)}")

    def generate_silence(self, duration_ms: int) -> bytes:
        # Generate silent audio data
        sample_rate = self.config.sample_rate
        num_samples = int(sample_rate * duration_ms / 1000)
        return b"\x00" * (num_samples * 2)  # Assuming 16-bit audio

    async def close(self):
        # Close WebSocket connection
        if self.websocket:
            await self.websocket.close()
            logger.info("Closed WebSocket connection to Cartesia API")
