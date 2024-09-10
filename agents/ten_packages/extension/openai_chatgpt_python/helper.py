#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-08.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
from ten.data import Data
from .log import logger


def get_property_bool(data: Data, property_name: str) -> bool:
    """Helper to get boolean property from data with error handling."""
    try:
        return data.get_property_bool(property_name)
    except Exception as err:
        logger.warn(f"GetProperty {property_name} failed: {err}")
        return False

def get_property_string(data: Data, property_name: str) -> str:
    """Helper to get string property from data with error handling."""
    try:
        return data.get_property_string(property_name)
    except Exception as err:
        logger.warn(f"GetProperty {property_name} failed: {err}")
        return ""
    
def get_property_int(data: Data, property_name: str) -> int:
    """Helper to get int property from data with error handling."""
    try:
        return data.get_property_int(property_name)
    except Exception as err:
        logger.warn(f"GetProperty {property_name} failed: {err}")
        return 0
    
def get_property_float(data: Data, property_name: str) -> float:
    """Helper to get float property from data with error handling."""
    try:
        return data.get_property_float(property_name)
    except Exception as err:
        logger.warn(f"GetProperty {property_name} failed: {err}")
        return 0.0