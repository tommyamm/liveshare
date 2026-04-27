import json
import pathlib
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


HOST = "127.0.0.1"
PORT = 8765
FILE_PATH = pathlib.Path("liveshare.py")


class LocalFileBridgeHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _read_content(self) -> str:
        if not FILE_PATH.exists():
            FILE_PATH.write_text("", encoding="utf-8")
            return ""
        return FILE_PATH.read_text(encoding="utf-8")

    def do_OPTIONS(self) -> None:
        self._send_json(HTTPStatus.NO_CONTENT, {})

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return

        if self.path == "/file":
            self._send_json(HTTPStatus.OK, {"content": self._read_content()})
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_PUT(self) -> None:
        self._handle_write()

    def do_POST(self) -> None:
        self._handle_write()

    def _handle_write(self) -> None:
        if self.path != "/file":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return

        length_header = self.headers.get("Content-Length")
        if not length_header:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "missing_length"})
            return

        raw_body = self.rfile.read(int(length_header))
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_json"})
            return

        content = payload.get("content")
        if not isinstance(content, str):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "content_must_be_string"})
            return

        FILE_PATH.write_text(content, encoding="utf-8")
        self._send_json(HTTPStatus.OK, {"status": "saved"})

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    httpd = ThreadingHTTPServer((HOST, PORT), LocalFileBridgeHandler)
    print(f"Local file bridge listening on http://{HOST}:{PORT}")
    print(f"Writing to {FILE_PATH.resolve()}")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nLocal bridge stopped")


if __name__ == "__main__":
    main()
