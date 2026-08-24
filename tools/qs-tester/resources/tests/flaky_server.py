"""A local endpoint that answers 500 a fixed number of times, then 200.

Stands in for Catalyst's app channel during the startup window. `diagrid dev run`
prints `Connected App ID ...` and the app answers `GET /` locally several seconds
before Catalyst can actually route to it; until then service invocation returns
500 `ERR_DIRECT_INVOKE ... app is not in a healthy state`. That window is what
`Wait Until Not Server Error` absorbs, and this server reproduces its shape with
no Catalyst project and no credentials.

Requests to a path other than /order answer 404, so the gate's other required
property -- that it absorbs 5xx *only*, and lets a 4xx through to the strict
assertion immediately -- is testable too.

Usage: python flaky_server.py <port> <failures>
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    failures_left = 0

    def do_POST(self):  # noqa: N802 - name fixed by BaseHTTPRequestHandler
        length = int(self.headers.get("content-length", 0))
        self.rfile.read(length)

        if self.path != "/order":
            self._respond(404, {"error": "not found"})
            return
        if Handler.failures_left > 0:
            Handler.failures_left -= 1
            self._respond(500, {"error": "app is not in a healthy state"})
            return
        self._respond(200, {"message": "Invocation successful", "orderId": 1})

    def _respond(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        # One line per request on stdout, which the Robot suite captures to a
        # log file. The default goes to stderr and interleaves confusingly.
        sys.stdout.write("%s %s -> %s\n" % (self.command, self.path, fmt % args))
        sys.stdout.flush()


def main():
    port = int(sys.argv[1])
    Handler.failures_left = int(sys.argv[2])
    server = HTTPServer(("127.0.0.1", port), Handler)
    # The Robot suite waits for this line before sending anything, so it must be
    # flushed: stdout is a file here, not a tty, so it is block-buffered.
    print(f"listening on {port}, failing {Handler.failures_left} time(s)", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
