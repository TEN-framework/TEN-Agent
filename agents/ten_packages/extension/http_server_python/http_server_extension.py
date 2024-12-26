from ten import (
    Extension,
    TenEnv,
    Cmd,
    StatusCode,
    CmdResult,
)
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from functools import partial


class HTTPHandler(BaseHTTPRequestHandler):
    def __init__(self, ten, *args, directory=None, **kwargs):
        ten.log_info("new handler: %s %s %s", directory, args, kwargs)
        self.ten = ten
        super().__init__(*args, **kwargs)

    def do_POST(self):
        self.ten.log_info("post request incoming %s", self.path)
        if self.path == "/cmd":
            try:
                content_length = int(self.headers["Content-Length"])
                input_file = self.rfile.read(content_length).decode("utf-8")
                self.ten.log_info("incoming request %s", input_file)
                self.ten.send_cmd(
                    Cmd.create_from_json(input_file),
                    lambda ten, result: ten.log_info(
                        "finish send_cmd from http server %s %s", input_file, result
                    ),
                )
                self.send_response_only(200)
                self.end_headers()
            except Exception as e:
                self.ten.log_warn(f"failed to handle request, err {e}")
                self.send_response_only(500)
                self.end_headers()
        else:
            self.ten.log_warn("invalid path: %s", self.path)
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

    def on_start(self, ten: TenEnv):
        self.listen_addr = ten.get_property_string("listen_addr")
        self.listen_port = ten.get_property_int("listen_port")

        # white_list = ten.get_property_string("cmd_white_list")
        # if len(white_list) > 0:
        #     self.cmd_white_list = white_list.split(",")

        ten.log_info(
            "HTTPServerExtension on_start %s:%d, %s",
            self.listen_addr,
            self.listen_port,
            self.cmd_white_list,
        )

        self.server = HTTPServer(
            (self.listen_addr, self.listen_port), partial(HTTPHandler, ten)
        )
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()

        ten.on_start_done()

    def on_stop(self, ten: TenEnv):
        ten.log_info("on_stop")
        self.server.shutdown()
        self.thread.join()
        ten.on_stop_done()

    def on_cmd(self, ten: TenEnv, cmd: Cmd):
        cmd_json = cmd.to_json()
        ten.log_info(f"on_cmd json: {cmd_json}")
        cmd_result = CmdResult.create(StatusCode.OK)
        cmd_result.set_property_string("detail", "ok")
        ten.return_result(cmd_result, cmd)
