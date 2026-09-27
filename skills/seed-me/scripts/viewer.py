import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlsplit

from session import atomic_write_text, load, writer


ASSET = Path(__file__).resolve().parents[1] / "assets/ledger-view.html"


def snapshot_page(ledger):
    template = ASSET.read_text(encoding="utf-8")
    marker = '{"__LEDGER_JSON__":true,"revision":0,"goal":null,"origin":null,"frontier":[],"nodes":[]}'
    if template.count(marker) != 1:
        raise ValueError("viewer template requires one snapshot marker")
    data = json.dumps(ledger, ensure_ascii=True, allow_nan=False).replace("<", "\\u003c")
    return template.replace(marker, data)


def save_snapshot(directory):
    directory = Path(directory).resolve()
    with writer(directory):
        destination = directory / "ledger-view.html"
        if destination.is_symlink():
            raise ValueError("viewer destination must not be a symlink")
        atomic_write_text(destination, snapshot_page(load(directory)))
    return destination


def make_server(directory, port=0):
    directory = Path(directory).resolve()
    save_snapshot(directory)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            host = self.headers.get("Host", "").split(":")[0]
            if host not in ("127.0.0.1", "localhost"):
                self.send_error(403)
                return
            path = urlsplit(self.path).path
            if path in ("/", "/ledger-view.html", "/ledger.json"):
                try:
                    ledger = load(directory)
                    if path == "/ledger.json":
                        body = json.dumps(ledger, ensure_ascii=False, allow_nan=False).encode()
                        content_type = "application/json; charset=utf-8"
                    else:
                        body = snapshot_page(ledger).encode("utf-8")
                        content_type = "text/html; charset=utf-8"
                except (ValueError, OSError, KeyError, TypeError):
                    self.send_error(503, "Ledger unavailable or invalid")
                    return
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
    parser.add_argument("--snapshot", action="store_true")
    args = parser.parse_args()
    try:
        if args.snapshot or load(args.session)["status"] != "active":
            print(save_snapshot(args.session).as_uri(), flush=True)
            return
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
