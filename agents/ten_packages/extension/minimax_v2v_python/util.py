from datetime import datetime


def duration_in_ms(start: datetime, end: datetime) -> int:
    return int((end - start).total_seconds() * 1000)


def duration_in_ms_since(start: datetime) -> int:
    return duration_in_ms(start, datetime.now())


class Role(str):
    System = "system"
    User = "user"
    Assistant = "assistant"
