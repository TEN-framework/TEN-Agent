from typing import List, Dict, Any, Optional
from .client import HomeAssistantAPI

class DeviceController:
    def __init__(self, host: str, token: str):
        self.ha = HomeAssistantAPI(host, token)
    
    async def __aenter__(self):
        await self.ha.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.ha.__aexit__(exc_type, exc_val, exc_tb)

    async def get_all_devices(self) -> List[Dict[str, Any]]:
        """Get all controllable devices
        
        Returns:
            List[Dict]: Device list, each device includes ID, type, state, and supported operations
        """
        devices = []
        states = await self.ha.get_states()
        services = await self.ha.get_services()
        
        # Controllable device types
        controllable_domains = {
            'light',      # Light
            'switch',     # Switch
            'climate',    # Air Conditioner/Heater
            'fan',        # Fan
            'cover',      # Curtain
            'media_player', # Media Player
            'vacuum',     # Vacuum Cleaner
            'water_heater', # Water Heater
            'camera',     # Camera
        }
        
        for state in states:
            entity_id = state['entity_id']
            domain = entity_id.split('.')[0]
            
            # Only include controllable devices
            if domain not in controllable_domains:
                continue
            
            # Get the services supported by this domain
            domain_services = []
            for service in services:
                if service['domain'] == domain:
                    domain_services = list(service.get('services', {}).keys())
                    break
            
            # Only include devices with available services
            if not domain_services:
                continue
            
            device = {
                'entity_id': entity_id,
                'name': state['attributes'].get('friendly_name', entity_id),
                'domain': domain,
                'state': state['state'],
                'attributes': state['attributes'],
                'supported_services': domain_services
            }
            devices.append(device)
        
        return devices

    async def control_device(self, 
                           entity_id: str, 
                           action: str, 
                           **params) -> Dict[str, Any]:
        """General method for controlling devices
        
        Args:
            entity_id: Device ID (e.g., light.bed_light)
            action: Action name (e.g., turn_on, turn_off, set_brightness)
            **params: Action parameters
        
        Returns:
            Dict: Operation result
        """
        domain = entity_id.split('.')[0]
        
        # Special action handling
        if action == 'set_brightness' and domain == 'light':
            result = await self.ha.turn_on(entity_id, brightness=params.get('brightness', 255))
        elif action == 'set_temperature' and domain == 'climate':
            result = await self.ha.control_device(domain, 'set_temperature', 
                                                entity_id, temperature=params.get('temperature'))
        else:
            result = await self.ha.control_device(domain, action, entity_id, **params)
        
        # Get the updated state
        new_state = await self.ha.get_state(entity_id)
        
        return {
            'success': True,
            'entity_id': entity_id,
            'action': action,
            'params': params,
            'result': result,
            'new_state': new_state
        }

    async def get_device_info(self, entity_id: str) -> Dict[str, Any]:
        """Get detailed information of a single device
        
        Args:
            entity_id: Device ID
            
        Returns:
            Dict: Device detailed information
        """
        state = await self.ha.get_state(entity_id)
        domain = entity_id.split('.')[0]
        
        services = await self.ha.get_services()
        domain_services = []
        for service in services:
            if service['domain'] == domain:
                domain_services = list(service.get('services', {}).keys())
                break
        
        return {
            'entity_id': entity_id,
            'name': state['attributes'].get('friendly_name', entity_id),
            'domain': domain,
            'state': state['state'],
            'attributes': state['attributes'],
            'supported_services': domain_services
        }

    async def get_devices_by_type(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all controllable devices by type
        
        Returns:
            Dict[str, List[Dict]]: Device list categorized by device type
            {
                'light': [device list],
                'switch': [device list],
                ...
            }
        """
        devices = await self.get_all_devices()
        
        categorized_devices = {}
        for device in devices:
            domain = device['domain']
            if domain not in categorized_devices:
                categorized_devices[domain] = {
                    'name': domain,
                    'devices': []
                }
            categorized_devices[domain]['devices'].append(device)
        
        return categorized_devices 