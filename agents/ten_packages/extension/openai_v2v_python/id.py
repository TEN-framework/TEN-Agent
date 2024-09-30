import random
import string


def generate_rand_str(prefix: str, len: int = 16) -> str:
    # Generate a random string of specified length with the given prefix
    random_str = "".join(random.choices(string.ascii_letters + string.digits, k=len))
    return f"{prefix}_{random_str}"


def generate_client_event_id() -> str:
    return generate_rand_str("cevt")


def generate_event_id() -> str:
    return generate_rand_str("event")


def generate_response_id() -> str:
    return generate_rand_str("resp")
