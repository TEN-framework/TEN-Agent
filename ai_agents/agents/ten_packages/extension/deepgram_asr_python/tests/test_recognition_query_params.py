from unittest.mock import MagicMock

from ..recognition import DeepgramASRRecognition, DeepgramASRRecognitionCallback


class _NoopCallback(DeepgramASRRecognitionCallback):
    async def on_open(self):
        pass

    async def on_result(self, message_data):
        pass

    async def on_error(self, error_msg, error_code=None):
        pass

    async def on_close(
        self, vendor_code: int = 0, vendor_message: str = "closed"
    ):
        pass


def _recognition(config: dict) -> DeepgramASRRecognition:
    return DeepgramASRRecognition(
        api_key="test-key",
        audio_timeline=MagicMock(),
        ten_env=MagicMock(),
        config=config,
        callback=_NoopCallback(),
    )


def test_keyterm_list_expands_to_repeated_query_params():
    rec = _recognition(
        {
            "url": "wss://api.deepgram.com/v1/listen",
            "model": "nova-3",
            "sample_rate": 16000,
            "encoding": "linear16",
            "keyterm": ["Deepgram", "customer service"],
        }
    )

    url = rec.append_query_params(rec.url)

    assert "keyterm=Deepgram" in url
    assert "keyterm=customer%20service" in url
    assert url.count("keyterm=") == 2


def test_keyterm_string_preserved_for_legacy_encoded_phrase():
    rec = _recognition(
        {
            "url": "wss://api.deepgram.com/v2/listen",
            "model": "flux-general-en",
            "sample_rate": 16000,
            "encoding": "linear16",
            "keyterm": "term1%20term2",
        }
    )

    url = rec.append_query_params(rec.url)

    assert "keyterm=term1%20term2" in url
    assert url.count("keyterm=") == 1


def test_hotwords_and_keyterm_list_on_nova_3():
    rec = _recognition(
        {
            "url": "wss://api.deepgram.com/v1/listen",
            "model": "nova-3",
            "sample_rate": 16000,
            "encoding": "linear16",
            "hotwords": ["from_hotwords"],
            "keyterm": ["from_keyterm"],
        }
    )

    url = rec.append_query_params(rec.url)

    assert "keyterm=from_hotwords" in url
    assert "keyterm=from_keyterm" in url


def test_hotwords_on_nova_2_still_use_keywords():
    rec = _recognition(
        {
            "url": "wss://api.deepgram.com/v1/listen",
            "model": "nova-2",
            "sample_rate": 16000,
            "encoding": "linear16",
            "hotwords": ["bbbb|5", "aaaa|5"],
        }
    )

    url = rec.append_query_params(rec.url)

    assert "keywords=bbbb:5" in url
    assert "keywords=aaaa:5" in url
    assert "keyterm=" not in url
