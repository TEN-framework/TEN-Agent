from typing import Union

class VolcengineConfig:
    def __init__(self,
            app_id: str,
            access_token: str,
            resource_id: str):
        self.app_id = app_id
        self.access_token = access_token
        self.resource_id = resource_id
        # 默认为 16000，目前只支持16000
        self.sample_rate = 16000

        self.channels = 1
        self.format = "pcm"
        self.codec = "raw"
        self.punctuate = True

    @classmethod
    def default_config(cls):
        return cls(
            app_id="",
            access_token="",
            resource_id="",
        )