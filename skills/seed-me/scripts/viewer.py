import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlsplit

from session import load


ASSET = Path(__file__).resolve().parents[1] / "assets/ledger-view.html"


def make_server(directory, port=0):
    directory = Path(directory).resolve()
    load(directory)
    page = ASSET.read_bytes()
    destination = directory / "ledger-view.html"
    if destination.is_symlink():
        raise ValueError("viewer destination must not be a symlink")
    destination.write_bytes(page)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            host = self.headers.get("Host", "").split(":")[0]
            if host not in ("127.0.0.1", "localhost"):
                self.send_error(403)
                return
            path = urlsplit(self.path).path
            if path in ("/", "/ledger-view.html"):
                body, content_type = page, "text/html; charset=utf-8"
            elif path == "/ledger.json":
                try:
                    body = json.dumps(load(directory), ensure_ascii=False, allow_nan=False).encode()
                except (ValueError, OSError, KeyError, TypeError):
                    self.send_error(503, "Ledger unavailable or invalid")
                    return
                content_type = "application/json; charset=utf-8"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            pass

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("session", type=Path)
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    try:
        server = make_server(args.session, args.port)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, str(error) + "\n")
    print(f"http://127.0.0.1:{server.server_port}/ledger-view.html", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
