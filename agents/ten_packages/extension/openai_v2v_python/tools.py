import copy
from typing import Dict, Any
from functools import partial

from .log import logger

class ToolRegistry:
    tools: Dict[str, dict[str, Any]] = {}
    def register(self, name:str, description: str, callback, parameters: Any = None) -> None:
        info = {
            "type": "function",
            "name": name,
            "description": description,
            "callback": callback
        }
        if parameters:
            info["parameters"] = parameters
        self.tools[name] = info
        logger.info(f"register tool {name} {description}")

    def to_prompt(self) -> str:
        prompt = ""
        if self.tools:
            prompt = "You have several tools that you can get help from:\n"
            for name, t in self.tools.items():
                desc = t["description"]
                prompt += f"- ***{name}***: {desc}"
        return prompt
    
    def unregister(self, name:str) -> None:
        if name in self.tools:
            del self.tools[name]
            logger.info(f"unregister tool {name}")
    
    def get_tools(self) -> list[dict[str, Any]]:
        result = []
        for _, t in self.tools.items():
            info = copy.copy(t)
            del info["callback"]
            result.append(info)
        return result
    
    async def on_func_call(self, call_id: str, name: str, args: str, callback):
        try:
            if name in self.tools:
                t = self.tools[name]
                # FIXME add args check
                if t.get("callback"):
                    p = partial(callback, call_id)
                    await t["callback"](name, args, p)
            else:
                logger.warning(f"Failed to find func {name}")
        except:
            logger.exception(f"Failed to call func {name}")
            # TODO What to do if func call is dead
            callback(None)

if __name__ == "__main__":
    r = ToolRegistry()
    
    def weather_check(location:str = "", datetime:str = ""):
        logger.info(f"on weather check {location}, {datetime}")
    
    def on_tool_completion(result: Any):
        logger.info(f"on tool completion {result}")
    
    r.register(
        name="weather", description="This is a weather check func, if the user is asking about the weather. you need to summarize location and time information from the context as parameters. if the information is lack, please ask for more detail before calling.",
        callback=weather_check,
        parameters={
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The location or region for the weather check.",
                },
                "datetime": {
                    "type": "string",
                    "description": "The date and time for the weather check. The datetime should use format like 2024-10-01T16:42:00.",
                }
            },
            "required": ["location"],
        })
    print(r.to_prompt())
    print(r.get_tools())
    print(r.on_func_call("weather", {"location":"LA", "datetime":"2024-10-01T16:43:01"}, on_tool_completion))
    r.unregister("weather")
    print(r.to_prompt())
    print(r.get_tools())
    print(r.on_func_call("weather", {"location":"LA", "datetime":"2024-10-01T16:43:01"}, on_tool_completion))
    