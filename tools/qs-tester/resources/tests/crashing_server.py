"""A server that dies mid-request, so the crash assertion can be tested offline.

`agents/microsoft-dotnet` documents a trigger that deliberately kills its own
process: "Call `step_two_compare` — crashes before completing (process exits)",
and of the documented curl, "The process exits — this is expected". So its suite
cannot assert a status code; what it must assert is that the request did NOT
complete, and for the right reason.

Three routes, because the keyword has to tell three outcomes apart and only one
of them is the documented behaviour:

    POST /crash  print the tool markers, then os._exit(1) without responding.
                 The client sees the connection drop. This is the documented flow.
    POST /ok     answer 200 normally. This is the crash having silently stopped
                 happening — exactly the bug found in Program.cs on 2026-08-28,
                 where the crash line sat committed and commented out — and the
                 assertion has to FAIL here, or it would ship that bug green.
    POST /hang   never respond. The client times out. This is NOT a crash: it is
                 the shape of Catalyst's attach window, where a workflow call
                 hangs forever (measured on agents/langgraph, 2026-08-27).
                 agents/microsoft-dotnet has no attach gate, so a hang is a live
                 possibility there, and letting one pass as "crashed" would hide
                 it behind an assertion that looks satisfied.

Usage: python crashing_server.py <port>
"""

from __future__ import annotations

import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802 - name fixed by BaseHTTPRequestHandler
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)

        if self.path == "/ok":
            payload = b'{"response": "all three steps complete"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        if self.path == "/hang":
            # Longer than any timeout a caller will use, so the client is always
            # the one that gives up — the real shape of the attach-window hang.
            time.sleep(600)
            return

        # /crash: the documented flow. The markers land in the log first, exactly
        # as the .NET app's Console.WriteLine calls do, and then the process dies
        # without writing a response.
        print(">>> TOOL 1: Searching venues in 'Austin'...", flush=True)
        print(">>> TOOL 1 COMPLETE: Found 3 venues", flush=True)
        print(">>> TOOL 2: Comparing venues...", flush=True)
        # os._exit, not sys.exit: this must not unwind, run handlers or let the
        # server write a 500. The app under test calls Environment.Exit(1), which
        # is the same abrupt shape.
        os._exit(1)

    def log_message(self, fmt, *args):
        sys.stdout.write("%s %s -> %s\n" % (self.command, self.path, fmt % args))
        sys.stdout.flush()


def main():
    port = int(sys.argv[1])
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    print(f"listening on {port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
