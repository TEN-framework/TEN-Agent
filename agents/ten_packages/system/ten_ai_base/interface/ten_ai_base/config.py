import builtins
import json

from typing import TypeVar, Type, List
from ten import AsyncTenEnv, TenEnv
from dataclasses import dataclass, fields


T = TypeVar('T', bound='BaseConfig')


@dataclass
class BaseConfig:
    """
    Base class for implementing configuration. 
    Extra configuration fields can be added in inherited class. 
    """

    @classmethod
    def create(cls: Type[T], ten_env: TenEnv) -> T:
        c = cls()
        c._init(ten_env)
        return c

    @classmethod
    async def create_async(cls: Type[T], ten_env: AsyncTenEnv) -> T:
        c = cls()
        await c._init_async(ten_env)
        return c

    def _init(obj, ten_env: TenEnv):
        """
        Get property from ten_env to initialize the dataclass config.    
        """
        for field in fields(obj):
            # TODO: 'is_property_exist' has a bug that can not be used in async extension currently, use it instead of try .. except once fixed
            # if not ten_env.is_property_exist(field.name):
            #     continue
            try:
                match field.type:
                    case builtins.str:
                        val = ten_env.get_property_string(field.name)
                        if val:
                            setattr(obj, field.name, val)
                    case builtins.int:
                        val = ten_env.get_property_int(field.name)
                        setattr(obj, field.name, val)
                    case builtins.bool:
                        val = ten_env.get_property_bool(field.name)
                        setattr(obj, field.name, val)
                    case builtins.float:
                        val = ten_env.get_property_float(field.name)
                        setattr(obj, field.name, val)
                    case _:
                        val = ten_env.get_property_to_json(field.name)
                        setattr(obj, field.name, json.loads(val))
            except Exception as e:
                pass

    async def _init_async(obj, ten_env: AsyncTenEnv):
        """
        Get property from ten_env to initialize the dataclass config.    
        """
        for field in fields(obj):
            try:
                match field.type:
                    case builtins.str:
                        val = await ten_env.get_property_string(field.name)
                        if val:
                            setattr(obj, field.name, val)
                    case builtins.int:
                        val = await ten_env.get_property_int(field.name)
                        setattr(obj, field.name, val)
                    case builtins.bool:
                        val = await ten_env.get_property_bool(field.name)
                        setattr(obj, field.name, val)
                    case builtins.float:
                        val = await ten_env.get_property_float(field.name)
                        setattr(obj, field.name, val)
                    case _:
                        val = await ten_env.get_property_to_json(field.name)
                        setattr(obj, field.name, json.loads(val))
            except Exception as e:
                pass