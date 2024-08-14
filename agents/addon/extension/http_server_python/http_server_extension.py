from rte import (
    Extension,
    RteEnv,
    Cmd,
    StatusCode,
    CmdResult,
)
from .log import logger
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from functools import partial


class HTTPHandler(BaseHTTPRequestHandler):
    def __init__(self, rte, *args, directory=None, **kwargs):
        logger.info("new handler: %s %s %s", directory, args, kwargs)
        self.rte = rte
        super().__init__(*args, **kwargs)

    def do_POST(self):
        logger.info("post request incoming %s", self.path)
        if self.path == "/cmd":
            try:
                content_length = int(self.headers["Content-Length"])
                input = self.rfile.read(content_length).decode("utf-8")
                logger.info("incoming request %s", input)
                self.rte.send_cmd(
                    Cmd.create_from_json(input),
                    lambda rte, result: logger.info(
                        "finish send_cmd from http server %s %s", input, result
                    ),
                )
                self.send_response_only(200)
                self.end_headers()
            except Exception as e:
                logger.warning("failed to handle request, err {}".format(e))
                self.send_response_only(500)
                self.end_headers()
        else:
            logger.warning("invalid path: %s", self.path)
            self.send_response_only(404)
            self.end_headers()


class HTTPServerExtension(Extension):
    def __init__(self, name: str):
        super().__init__(name)
        self.listen_addr = "127.0.0.1"
        self.listen_port = 8888
        self.cmd_white_list = None
        self.server = None
        self.thread = None

    def on_start(self, rte: RteEnv):
        self.listen_addr = rte.get_property_string("listen_addr")
        self.listen_port = rte.get_property_int("listen_port")
        """
            white_list = rte.get_property_string("cmd_white_list")
            if len(white_list) > 0:
                self.cmd_white_list = white_list.split(",")
        """

        logger.info(
            "HTTPServerExtension on_start %s:%d, %s",
            self.listen_addr,
            self.listen_port,
            self.cmd_white_list,
        )

        self.server = HTTPServer(
            (self.listen_addr, self.listen_port), partial(HTTPHandler, rte)
        )
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()

        rte.on_start_done()

    def on_stop(self, rte: RteEnv):
        logger.info("on_stop")
        self.server.shutdown()
        self.thread.join()
        rte.on_stop_done()

    def on_cmd(self, rte: RteEnv, cmd: Cmd):
        cmd_json = cmd.to_json()
        logger.info("on_cmd json: " + cmd_json)
        cmd_result = CmdResult.create(StatusCode.OK)
        cmd_result.set_property_string("detail", "ok")
        rte.return_result(cmd_result, cmd)
