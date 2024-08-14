from typing import Union

class TranscribeConfig:
    def __init__(self, 
            region: str, 
            access_key: str, 
            secret_key: str, 
            sample_rate: Union[str, int],
            lang_code: str):
        self.region = region
        self.access_key = access_key
        self.secret_key = secret_key

        self.lang_code = lang_code
        self.sample_rate = int(sample_rate)

        self.media_encoding = 'pcm'
        self.bytes_per_sample = 2,
        self.channel_nums = 1

    @classmethod
    def default_config(cls):
        return cls(
            region="us-east-1",
            access_key="",
            secret_key="",
            sample_rate=16000,
            lang_code='en-US'
        )