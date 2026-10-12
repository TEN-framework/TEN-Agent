#
# This file is part of TEN Framework.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the root directory of this source tree.
#
"""Observe only connections made through an injected dependency binding."""

from urllib.parse import urlsplit


def endpoint(url):
    parsed = urlsplit(url)
    return parsed.scheme, parsed.hostname, parsed.port, parsed.path


class ObservedWebSockets:
    """Delegate the library except for a case's matching connect calls."""

    def __init__(self, library, url, observer):
        self.library = library
        self.endpoint = endpoint(url)
        self.observer = observer

    def __getattr__(self, name):
        return getattr(self.library, name)

    def connect(self, uri, *args, **kwargs):
        if endpoint(uri) != self.endpoint:
            return self.library.connect(uri, *args, **kwargs)
        base = kwargs.get("create_connection") or self.library.ClientConnection
        observer = self.observer

        class ObservedConnection(base):
            """Keep the original connection API and cancellation behavior."""

            async def send(self, message, *send_args, **send_kwargs):
                observer.observe_send(message)
                return await super().send(message, *send_args, **send_kwargs)

            async def recv(self, *recv_args, **recv_kwargs):
                message = await super().recv(*recv_args, **recv_kwargs)
                observer.observe_receive(message)
                return message

        kwargs["create_connection"] = ObservedConnection
        return self.library.connect(uri, *args, **kwargs)
