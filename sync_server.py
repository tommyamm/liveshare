import asyncio
import json
import pathlib
import socket
import threading
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional, Set

from websockets.asyncio.server import ServerConnection, serve


HOST = "0.0.0.0"
HTTP_PORT = 8000
WS_PORT = 5678
FILE_PATH = pathlib.Path("liveshare.py")
WEB_DIR = pathlib.Path(__file__).with_name("web")


def detect_lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            lan_ip = sock.getsockname()[0]
            if lan_ip and not lan_ip.startswith("127."):
                return lan_ip
    except OSError:
        pass

    try:
        hostname_ip = socket.gethostbyname(socket.gethostname())
        if hostname_ip and not hostname_ip.startswith("127."):
            return hostname_ip
    except OSError:
        pass

    return "127.0.0.1"


class SyncServer:
    def __init__(self, file_path: pathlib.Path) -> None:
        self.file_path = file_path
        self.clients: Set[ServerConnection] = set()
        self.current_content = self._load_initial_content()

    def _load_initial_content(self) -> str:
        if self.file_path.exists():
            return self.file_path.read_text(encoding="utf-8")
        return ""

    def _write_file(self, content: str) -> None:
        self.file_path.write_text(content, encoding="utf-8")

    async def send_state(self, websocket: ServerConnection) -> None:
        await websocket.send(
            json.dumps(
                {
                    "type": "sync",
                    "content": self.current_content,
                    "participants": len(self.clients),
                }
            )
        )

    async def broadcast_presence(self) -> None:
        if not self.clients:
            return

        message = json.dumps(
            {"type": "presence", "participants": len(self.clients)}
        )
        await asyncio.gather(
            *(client.send(message) for client in self.clients),
            return_exceptions=True,
        )

    async def broadcast_content(
        self, content: str, sender: Optional[ServerConnection]
    ) -> None:
        recipients = [client for client in self.clients if client != sender]
        if not recipients:
            return

        message = json.dumps(
            {
                "type": "sync",
                "content": content,
                "participants": len(self.clients),
            }
        )
        await asyncio.gather(
            *(client.send(message) for client in recipients),
            return_exceptions=True,
        )

    async def handler(self, websocket: ServerConnection) -> None:
        self.clients.add(websocket)
        print(f"Browser connected: {websocket.remote_address}")
        await self.send_state(websocket)
        await self.broadcast_presence()

        try:
            async for raw_message in websocket:
                try:
                    payload = json.loads(raw_message)
                except json.JSONDecodeError:
                    print("Ignored invalid JSON message")
                    continue

                if payload.get("type") != "sync":
                    print(f"Ignored unknown message type: {payload.get('type')}")
                    continue

                content = payload.get("content")
                if not isinstance(content, str):
                    print("Ignored sync message without text content")
                    continue

                if content == self.current_content:
                    continue

                self.current_content = content
                self._write_file(content)
                await self.broadcast_content(content, sender=websocket)
        finally:
            self.clients.discard(websocket)
            print(f"Browser disconnected: {websocket.remote_address}")
            await self.broadcast_presence()


class EditorHTTPRequestHandler(SimpleHTTPRequestHandler):
    share_url = f"http://127.0.0.1:{HTTP_PORT}"
    local_url = f"http://127.0.0.1:{HTTP_PORT}"

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def do_GET(self) -> None:
        if self.path == "/api/session":
            payload = json.dumps(
                {
                    "shareUrl": self.share_url,
                    "localUrl": self.local_url,
                    "httpPort": HTTP_PORT,
                    "wsPort": WS_PORT,
                }
            ).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        super().do_GET()


def run_http_server(share_url: str, local_url: str) -> None:
    EditorHTTPRequestHandler.share_url = share_url
    EditorHTTPRequestHandler.local_url = local_url
    handler = EditorHTTPRequestHandler
    httpd = ThreadingHTTPServer((HOST, HTTP_PORT), handler)
    print(f"Editor UI listening on {local_url}")
    print(f"Share this URL with the student: {share_url}")
    httpd.serve_forever()


async def main() -> None:
    lan_ip = detect_lan_ip()
    local_url = f"http://127.0.0.1:{HTTP_PORT}"
    share_url = f"http://{lan_ip}:{HTTP_PORT}"
    http_thread = threading.Thread(
        target=run_http_server,
        args=(share_url, local_url),
        daemon=True,
    )
    http_thread.start()

    server = SyncServer(FILE_PATH)
    async with serve(server.handler, HOST, WS_PORT):
        print(f"WebSocket sync listening on ws://0.0.0.0:{WS_PORT}")
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped")
