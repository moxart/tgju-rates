"""``--serve``: the routes in api.py over HTTP, with a thread that polls the feed every interval.

It's built on http.server to stay dependency-free, which is fine on localhost or a home network.
On the open internet it belongs behind a reverse proxy that handles TLS and rate limits.
"""

import json
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from tgju_rates import __version__
from tgju_rates.api import API_PREFIX, Api

LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")


INTERNAL_ERROR = 500
# Seconds a connection may sit idle, so clients that open connections and send nothing can't pile up threads.
REQUEST_TIMEOUT = 15


class ApiHandler(BaseHTTPRequestHandler):
    server_version = f"tgju-rates/{__version__}"
    timeout = REQUEST_TIMEOUT

    def do_GET(self):
        url = urlsplit(self.path)
        params = {name: values[-1] for name, values in parse_qs(url.query).items()}
        try:
            status, payload = self.server.api.handle(url.path, params)
            # allow_nan=False: Infinity and NaN aren't JSON, so a result like that is a bug, not a response.
            body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
        except Exception:
            # The traceback goes to the server's log; the client only learns that something broke.
            self.log_error("error answering %s\n%s", self.path, traceback.format_exc())
            status = INTERNAL_ERROR
            body = json.dumps({"error": "internal error"}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        # Read-only public prices, so any page (such as a home dashboard) may fetch them.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


def bind(host, port):
    """A server listening on the address, so a taken port fails before the slow start-up fetch.

    Raises OSError when the address is taken or not allowed. ``serve`` gives it the API.
    """
    server = ThreadingHTTPServer((host, port), ApiHandler)
    server.daemon_threads = True
    return server


def poll_forever(store, stop):
    while not stop.wait(store.poll_delay()):
        store.poll()


def serve(server, store):
    """Poll once, then answer requests and poll every interval until Ctrl+C or SIGTERM."""
    server.api = Api(store)
    store.poll()
    if store.error:
        print(f"Warning: {store.error}", file=sys.stderr)
    stop = threading.Event()
    threading.Thread(target=poll_forever, args=(store, stop), daemon=True).start()
    host, port = server.server_address[:2]
    print(f"Serving the API on http://{host}:{port}{API_PREFIX}/ (Ctrl+C to stop)", file=sys.stderr)
    try:
        server.serve_forever()
    finally:
        stop.set()
        server.server_close()
