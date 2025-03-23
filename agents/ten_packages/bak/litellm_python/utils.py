import time


def get_micro_ts():
    return int(time.time() * 1_000_000)


def is_punctuation(char: str):
    return char in [",", "，", ".", "。", "?", "？", "!", "！"]


def parse_sentence(sentence: str, content: str):
    for i, char in enumerate(content):
        sentence += char

        if is_punctuation(char):
            return sentence, content[i + 1 :], True

    return sentence, "", False
