"""A POST-answering HTTP server, so `POST And Expect Field` can be tested with
no Catalyst project and no network.

`python -m http.server` only answers GET, and the keyword under test asserts on
a POST response body, so a fixture is unavoidable. Kept to the standard library
on purpose: this file must not add a dependency to the harness.

Routes:
    POST /full   -> 200 {"result": "some text", "blank": ""}
    POST /empty  -> 200 {"result": ""}
    POST /none   -> 200 {"other": "value"}

Usage:
    python echo_server.py 8099
"""

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

BODIES = {
    "/full": {"result": "some text", "blank": ""},
    "/empty": {"result": ""},
    "/none": {"other": "value"},
}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        body = BODIES.get(self.path)
        payload = json.dumps(body if body is not None else {"error": "no such route"})
        self.send_response(200 if body is not None else 404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload.encode())

    def do_GET(self):
        # The readiness probe the test suite polls before sending any POST.
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        # Silence per-request logging; the Robot log is the record that matters.
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8099
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
