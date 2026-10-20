#!/usr/bin/env python3
"""
Telnyx Server for Voice Call Handling
Handles call creation, media streaming, and webhook status
"""
import asyncio
import aiohttp
import json
import os
import signal
import sys
from typing import Dict, Any, Optional
from datetime import datetime
from urllib.parse import quote
from urllib import request as urllib_request

import uvicorn
from fastapi import FastAPI, Request, HTTPException, WebSocket
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .config import TelnyxConfig


class TelnyxCallServer:
    """Server for handling Telnyx calls, media streaming, and webhooks"""

    def __init__(self, config: TelnyxConfig, ten_env=None):
        self.config = config
        self.ten_env = ten_env
        self.app = FastAPI(title="Telnyx Call Server")

        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Allow all origins
            allow_credentials=True,
            allow_methods=["*"],  # Allow all methods
            allow_headers=["*"],  # Allow all headers
        )

        # Active call sessions
        self.active_call_sessions: Dict[str, Dict[str, Any]] = {}

        # Setup routes
        self._setup_routes()

    def _log_info(self, message: str):
        """Log info message using ten_env if available"""
        if self.ten_env:
            self.ten_env.log_info(message)
        else:
            print(f"INFO: {message}")

    def _log_error(self, message: str):
        """Log error message using ten_env if available"""
        if self.ten_env:
            self.ten_env.log_error(message)
        else:
            print(f"ERROR: {message}")

    def _log_debug(self, message: str):
        """Log debug message using ten_env if available"""
        if self.ten_env:
            self.ten_env.log_debug(message)
        else:
            print(f"DEBUG: {message}")

    def _media_ws_url(self) -> Optional[str]:
        if not self.config.telnyx_public_server_url:
            return None

        ws_protocol = "wss" if self.config.telnyx_use_wss else "ws"
        return f"{ws_protocol}://{self.config.telnyx_public_server_url}/media"

    def _webhook_url(self) -> Optional[str]:
        if not self.config.telnyx_public_server_url:
            return None

        http_protocol = "https" if self.config.telnyx_use_https else "http"
        return (
            f"{http_protocol}://"
            f"{self.config.telnyx_public_server_url}/webhook/status"
        )

    def _streaming_params(self) -> Dict[str, Any]:
        media_ws_url = self._media_ws_url()
        if not media_ws_url:
            return {}

        return {
            "stream_url": media_ws_url,
            "stream_track": "both_tracks",
            "stream_codec": "PCMU",
            "stream_bidirectional_mode": "rtp",
            "stream_bidirectional_codec": "PCMU",
        }

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.telnyx_api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _post_telnyx(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"https://api.telnyx.com/v2{path}"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=self._headers(),
                json=payload,
            ) as response:
                response_body = await response.text()
                if response.status >= 400:
                    raise HTTPException(
                        status_code=response.status,
                        detail=response_body,
                    )
                if not response_body:
                    return {}
                return json.loads(response_body)

    def _post_telnyx_sync(
        self, path: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        request = urllib_request.Request(
            f"https://api.telnyx.com/v2{path}",
            data=data,
            headers=self._headers(),
            method="POST",
        )
        with urllib_request.urlopen(request, timeout=10) as response:
            response_body = response.read().decode("utf-8")
            if not response_body:
                return {}
            return json.loads(response_body)

    async def _dial_call(self, phone_number: str) -> Dict[str, Any]:
        call_params = {
            "to": phone_number,
            "from": self.config.telnyx_from_number,
            "connection_id": self.config.telnyx_connection_id,
            **self._streaming_params(),
        }

        webhook_url = self._webhook_url()
        if webhook_url:
            call_params["webhook_url"] = webhook_url
            call_params["webhook_url_method"] = "POST"

        return await self._post_telnyx("/calls", call_params)

    async def _hangup_call(self, call_control_id: str) -> Dict[str, Any]:
        encoded_call_control_id = quote(call_control_id, safe="")
        return await self._post_telnyx(
            f"/calls/{encoded_call_control_id}/actions/hangup", {}
        )

    async def _answer_call(self, call_control_id: str) -> Dict[str, Any]:
        encoded_call_control_id = quote(call_control_id, safe="")
        return await self._post_telnyx(
            f"/calls/{encoded_call_control_id}/actions/answer",
            self._streaming_params(),
        )

    def _get_or_create_session(self, call_control_id: str) -> Dict[str, Any]:
        if call_control_id not in self.active_call_sessions:
            self.active_call_sessions[call_control_id] = {
                "call_id": call_control_id,
                "status": "unknown",
                "created_at": datetime.now().isoformat(),
            }

        return self.active_call_sessions[call_control_id]

    @staticmethod
    def _parse_telnyx_event(
        body: Dict[str, Any]
    ) -> tuple[Optional[str], Dict[str, Any]]:
        data = body.get("data") or {}
        return data.get("event_type"), data.get("payload") or {}

    def _update_session_from_event(
        self, event_type: Optional[str], payload: Dict[str, Any]
    ) -> Optional[str]:
        call_control_id = payload.get("call_control_id")
        if not call_control_id:
            return None

        session = self._get_or_create_session(call_control_id)
        session.update(
            {
                "call_id": call_control_id,
                "call_control_id": call_control_id,
                "call_leg_id": payload.get("call_leg_id"),
                "call_session_id": payload.get("call_session_id"),
                "phone_number": payload.get("to") or session.get("phone_number"),
                "from_number": payload.get("from") or session.get("from_number"),
                "direction": payload.get("direction") or session.get("direction"),
                "status": payload.get("state") or event_type or session["status"],
                "last_event": event_type,
                "updated_at": datetime.now().isoformat(),
            }
        )

        if event_type in {"call.hangup", "streaming.stopped", "streaming.failed"}:
            session["status"] = "completed"
            session["ended_at"] = datetime.now().isoformat()

        return call_control_id

    def _setup_routes(self):
        """Setup FastAPI routes"""

        @self.app.post("/api/call")
        async def create_call(request: Request):
            """Create a new outbound call"""
            try:
                body = await request.json()
                phone_number = body.get("phone_number")
                message = body.get("message", "Hello from Telnyx!")

                if not phone_number:
                    raise HTTPException(
                        status_code=400, detail="phone_number is required"
                    )

                self._log_info(
                    f"Creating call to {phone_number} with message: {message}"
                )

                if self._media_ws_url():
                    self._log_info(
                        f"Adding media stream to WebSocket: {self._media_ws_url()}"
                    )
                else:
                    self._log_info(
                        "No public server URL configured - media streaming disabled"
                    )

                response = await self._dial_call(phone_number)
                call_data = response.get("data", response)

                # Store call session
                call_id = (
                    call_data.get("call_control_id")
                    or call_data.get("call_leg_id")
                    or call_data.get("id")
                )
                if not call_id:
                    raise HTTPException(
                        status_code=502,
                        detail="Telnyx call response did not include a call id",
                    )

                self.active_call_sessions[call_id] = {
                    "phone_number": phone_number,
                    "message": message,
                    "call_id": call_id,
                    "call_control_id": call_data.get("call_control_id"),
                    "call_leg_id": call_data.get("call_leg_id"),
                    "call_session_id": call_data.get("call_session_id"),
                    "status": "initiated",
                    "created_at": datetime.now().isoformat(),
                }

                self._log_info(f"Call created successfully: {call_id}")

                return JSONResponse(
                    content={
                        "success": True,
                        "call_id": call_id,
                        "status": "initiated",
                        "phone_number": phone_number,
                        "message": message,
                    }
                )

            except HTTPException:
                raise
            except Exception as e:
                self._log_error(f"Failed to create call: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.delete("/api/call/{call_id}")
        async def end_call(call_id: str):
            """End a call by ID"""
            try:
                if call_id not in self.active_call_sessions:
                    raise HTTPException(
                        status_code=404, detail="Call not found"
                    )

                self._log_info(f"Ending call: {call_id}")

                await self._hangup_call(call_id)

                # Update session status
                if call_id in self.active_call_sessions:
                    self.active_call_sessions[call_id]["status"] = "completed"
                    self.active_call_sessions[call_id][
                        "ended_at"
                    ] = datetime.now().isoformat()

                self._log_info(f"Call {call_id} ended successfully")

                return JSONResponse(
                    content={
                        "success": True,
                        "call_id": call_id,
                        "status": "completed",
                    }
                )

            except HTTPException:
                raise
            except Exception as e:
                self._log_error(f"Failed to end call {call_id}: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/call/{call_id}")
        async def get_call_status(call_id: str):
            """Get call status by ID"""
            try:
                if call_id not in self.active_call_sessions:
                    raise HTTPException(
                        status_code=404, detail="Call not found"
                    )

                session = self.active_call_sessions[call_id]

                return JSONResponse(
                    content={
                        "success": True,
                        "call_id": call_id,
                        "status": session["status"],
                        "phone_number": session.get("phone_number"),
                        "message": session.get("message"),
                        "created_at": session["created_at"],
                        "ended_at": session.get("ended_at"),
                    }
                )

            except HTTPException:
                raise
            except Exception as e:
                self._log_error(
                    f"Failed to get call status {call_id}: {str(e)}"
                )
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/calls")
        async def list_calls():
            """List all active calls"""
            return JSONResponse(
                content={
                    "success": True,
                    "active_calls": len(self.active_call_sessions),
                    "calls": list(self.active_call_sessions.keys()),
                }
            )

        @self.app.post("/webhook/status")
        async def handle_status_webhook(request: Request):
            """Handle Telnyx status webhook"""
            try:
                body = await request.json()
                event_type, payload = self._parse_telnyx_event(body)
                call_id = self._update_session_from_event(event_type, payload)

                self._log_info(
                    f"Status webhook received for call {call_id}: {event_type}"
                )

                if (
                    event_type == "call.initiated"
                    and payload.get("direction") == "incoming"
                    and call_id
                ):
                    await self._answer_call(call_id)

                return JSONResponse(content={"success": True})

            except HTTPException:
                raise
            except Exception as e:
                self._log_error(f"Failed to handle status webhook: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            return JSONResponse(
                content={
                    "status": "healthy",
                    "active_calls": len(self.active_call_sessions),
                    "server_time": datetime.now().isoformat(),
                }
            )

        @self.app.get("/api/config")
        async def get_config():
            """Get server configuration"""
            # Build URLs with configurable protocols
            media_ws_url = None
            webhook_url = None

            if self.config.telnyx_public_server_url:
                media_ws_url = self._media_ws_url()
                webhook_url = self._webhook_url()

            return JSONResponse(
                content={
                    "telnyx_from_number": self.config.telnyx_from_number,
                    "server_port": self.config.telnyx_server_port,
                    "public_server_url": (
                        self.config.telnyx_public_server_url
                        if self.config.telnyx_public_server_url
                        else None
                    ),
                    "use_https": self.config.telnyx_use_https,
                    "use_wss": self.config.telnyx_use_wss,
                    "media_stream_enabled": bool(
                        self.config.telnyx_public_server_url
                    ),
                    "media_ws_url": media_ws_url,
                    "webhook_enabled": bool(
                        self.config.telnyx_public_server_url
                    ),
                    "webhook_url": webhook_url,
                }
            )

        # WebSocket endpoint for media streaming
        @self.app.websocket("/media")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for Telnyx media streaming"""
            self._log_info(
                f"WebSocket connection attempt from: {websocket.client}"
            )

            try:
                # Accept the connection immediately
                await websocket.accept()
                self._log_info(
                    f"WebSocket connection established: {websocket.client}"
                )

                # Send initial message to confirm connection
                await websocket.send_text(
                    '{"type": "connected", "message": "WebSocket connection established"}'
                )

                # Initialize call_id to None to prevent NameError
                call_id = None

                while True:
                    # Receive message from Telnyx
                    data = await websocket.receive_text()
                    self._log_debug(
                        f"Received WebSocket message: {data[:100]}..."
                    )

                    # Parse Telnyx media stream message
                    try:
                        import json

                        message = json.loads(data)

                        if message.get("event") == "media":
                            # Extract audio payload and call ID
                            audio_payload = message.get("media", {}).get(
                                "payload", ""
                            )
                            stream_id = message.get("stream_id", "")

                            if audio_payload and call_id:
                                # Forward audio to TEN framework
                                if (
                                    hasattr(self, "extension_instance")
                                    and self.extension_instance
                                ):
                                    await self.extension_instance._forward_audio_to_ten(
                                        audio_payload, stream_id
                                    )
                                else:
                                    self._log_debug(
                                        "Extension instance not available for audio forwarding"
                                    )

                        elif message.get("event") == "start":
                            self._log_info(f"Media stream started: {message}")
                            stream_id = message.get("stream_id", "")
                            start = message.get("start", {})
                            call_id = start.get("call_control_id", "")
                            if call_id and call_id not in self.active_call_sessions:
                                self.active_call_sessions[call_id] = {
                                    "call_id": call_id,
                                    "call_control_id": call_id,
                                    "call_session_id": start.get("call_session_id"),
                                    "phone_number": start.get("to"),
                                    "from_number": start.get("from"),
                                    "status": "streaming",
                                    "created_at": datetime.now().isoformat(),
                                }

                            self.active_call_sessions[call_id][
                                "stream_id"
                            ] = stream_id
                            self.active_call_sessions[call_id][
                                "websocket"
                            ] = websocket

                            # Notify extension that websocket is connected
                            if (
                                hasattr(self, "extension_instance")
                                and self.extension_instance
                            ):
                                await self.extension_instance.on_websocket_connected(
                                    call_id
                                )
                        elif message.get("event") == "stop":
                            self._log_info(f"Media stream stopped: {message}")

                    except json.JSONDecodeError:
                        self._log_debug(
                            f"Received non-JSON message: {data[:100]}..."
                        )
                    except Exception as e:
                        self._log_error(f"Error processing media message: {e}")

            except Exception as e:
                self._log_error(f"WebSocket error: {e}")
                # Try to close the connection gracefully
                try:
                    await websocket.close()
                except:
                    pass
            finally:
                self._log_info("WebSocket connection closed")

    async def start_server(self, host: str = "0.0.0.0", port: int = 8080):
        """Start the server with both HTTP and WebSocket support"""
        self._log_info(f"Starting Telnyx Call Server on {host}:{port}")
        self._log_info(
            "Server supports both HTTP API and WebSocket media streaming on the same port"
        )

        # Check if SSL is required
        use_ssl = self.config.telnyx_use_https or self.config.telnyx_use_wss

        if use_ssl:
            # For development with ngrok, we'll use HTTP but let ngrok handle SSL
            self._log_info(
                "SSL/WSS requested - using HTTP server (ngrok will handle SSL termination)"
            )
            ssl_keyfile = None
            ssl_certfile = None
        else:
            ssl_keyfile = None
            ssl_certfile = None

        # Start server with HTTP and WebSocket support
        config = uvicorn.Config(
            app=self.app,
            host=host,
            port=port,
            log_level="info",
            ssl_keyfile=ssl_keyfile,
            ssl_certfile=ssl_certfile,
        )

        server = uvicorn.Server(config)
        await server.serve()

    def cleanup(self):
        """Cleanup resources"""
        self._log_info("Cleaning up Telnyx Call Server")
        for call_id in list(self.active_call_sessions.keys()):
            try:
                encoded_call_control_id = quote(call_id, safe="")
                self._post_telnyx_sync(
                    f"/calls/{encoded_call_control_id}/actions/hangup", {}
                )
                self._log_info(f"Ended call {call_id}")
            except Exception as e:
                self._log_error(f"Failed to end call {call_id}: {str(e)}")


async def main():
    """Main function to run the server"""
    # Load configuration from environment variables
    config = TelnyxConfig(
        telnyx_api_key=os.getenv("TELNYX_API_KEY", ""),
        telnyx_connection_id=os.getenv("TELNYX_CONNECTION_ID", ""),
        telnyx_from_number=os.getenv("TELNYX_FROM_NUMBER", ""),
        telnyx_server_port=int(os.getenv("TELNYX_SERVER_PORT", "8000")),
        telnyx_public_server_url=os.getenv("TELNYX_PUBLIC_SERVER_URL", ""),
        telnyx_use_https=os.getenv("TELNYX_USE_HTTPS", "true").lower()
        == "true",
        telnyx_use_wss=os.getenv("TELNYX_USE_WSS", "true").lower() == "true",
    )

    # Validate required configuration
    if (
        not config.telnyx_api_key
        or not config.telnyx_connection_id
        or not config.telnyx_from_number
    ):
        print("Error: Missing required Telnyx configuration")
        print(
            "Please set TELNYX_API_KEY, TELNYX_CONNECTION_ID, and TELNYX_FROM_NUMBER"
        )
        sys.exit(1)

    # Create and start server
    server = TelnyxCallServer(config)

    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        print(f"Received signal {signum}, shutting down...")
        server.cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        await server.start_server()
    except KeyboardInterrupt:
        print("Server interrupted, shutting down...")
        server.cleanup()
    except Exception as e:
        print(f"Server error: {e}")
        server.cleanup()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
