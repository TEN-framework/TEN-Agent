import aiohttp
from typing import Optional, Dict, Any

class HomeAssistantAPI:
    """Home Assistant REST API client"""
    
    def __init__(self, host: str, token: str, verify_ssl: bool = True, timeout: int = 10):
        """Initialize the client
        
        Args:
            host: Home Assistant address (e.g., http://192.168.1.100:8123)
            token: Long-lived access token
            verify_ssl: Whether to verify SSL certificates
            timeout: Timeout time (seconds)
        """
        self.host = host.rstrip('/')
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self._api_url = f"{self.host}/api"
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(headers=self.headers)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

    async def _request(self, method: str, endpoint: str, data: Dict = None) -> Any:
        """Send API request"""
        if not self.session:
            self.session = aiohttp.ClientSession(headers=self.headers)

        url = f"{self._api_url}/{endpoint.lstrip('/')}"
        async with self.session.request(method, url, json=data, ssl=self.verify_ssl) as response:
            if response.status == 401:
                raise Exception("Authentication failed")
            if response.status not in [200, 201]:
                raise Exception(f"API request failed: {response.status}")
            return await response.json()

    # API methods
    async def get_config(self):
        """Get Home Assistant configuration"""
        return await self._request("GET", "config")

    async def get_events(self):
        """Get available event list"""
        return await self._request("GET", "events")

    async def get_services(self):
        """Get available service list"""
        return await self._request("GET", "services")

    async def get_states(self):
        """Get all entity states"""
        return await self._request("GET", "states")

    async def get_state(self, entity_id: str):
        """Get specific entity state"""
        return await self._request("GET", f"states/{entity_id}")

    async def set_state(self, entity_id: str, state: str, attributes: Dict = None):
        """Set entity state"""
        data = {"state": state}
        if attributes:
            data["attributes"] = attributes
        return await self._request("POST", f"states/{entity_id}", data)

    async def call_service(self, domain: str, service: str, service_data: Dict = None):
        """Call service"""
        return await self._request("POST", f"services/{domain}/{service}", service_data)

    # Device control methods
    async def control_device(self, domain: str, service: str, entity_id: str, **service_data):
        """Control device"""
        data = {"entity_id": entity_id, **service_data}
        return await self.call_service(domain, service, data)

    async def turn_on(self, entity_id: str, **kwargs):
        """Turn on device"""
        domain = entity_id.split('.')[0]
        return await self.control_device(domain, "turn_on", entity_id, **kwargs)

    async def turn_off(self, entity_id: str, **kwargs):
        """Turn off device"""
        domain = entity_id.split('.')[0]
        return await self.control_device(domain, "turn_off", entity_id, **kwargs)

    # Xiaomi device specific methods
    async def set_xiaomi_light(self, entity_id: str, brightness: Optional[int] = None, 
                             color_temp: Optional[int] = None):
        """Control Xiaomi light"""
        data = {}
        if brightness is not None:
            data["brightness"] = brightness
        if color_temp is not None:
            data["color_temp"] = color_temp
        return await self.turn_on(entity_id, **data)

    async def set_xiaomi_fan_speed(self, entity_id: str, speed: str):
        """Set Xiaomi fan speed"""
        return await self.control_device("fan", "set_speed", entity_id, speed=speed) 