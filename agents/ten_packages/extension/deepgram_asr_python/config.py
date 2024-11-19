from typing import Union

class DeepgramConfig:
    def __init__(self,
            api_key: str,
            language: str,
            model: str,
            sample_rate: Union[str, int]):
        self.api_key = api_key
        self.language = language
        self.model = model
        self.sample_rate = int(sample_rate)

        self.channels = 1
        self.encoding = 'linear16'
        self.interim_results = True
        self.punctuate = True

    @classmethod
    def default_config(cls):
        return cls(
            api_key="",
            language="en-US",
            model="nova-2",
            sample_rate=16000
        )