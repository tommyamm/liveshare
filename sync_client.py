import asyncio
import json
import pathlib
import sys
from typing import Optional

import websockets


PORT = 5678
POLL_INTERVAL = 0.3
FILE_PATH = pathlib.Path("liveshare.py")


class SyncClient:
    def __init__(self, server_host: str, file_path: pathlib.Path) -> None:
        self.server_host = server_host
        self.file_path = file_path
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.last_local_content = self._ensure_file_exists()
        self.last_received_content: Optional[str] = None

    def _ensure_file_exists(self) -> str:
        if not self.file_path.exists():
            self.file_path.write_text("", encoding="utf-8")
            return ""
        return self.file_path.read_text(encoding="utf-8")

    def _read_file(self) -> str:
        return self.file_path.read_text(encoding="utf-8")

    def _write_file(self, content: str) -> None:
        self.file_path.write_text(content, encoding="utf-8")

    async def send_local_changes(self) -> None:
        assert self.websocket is not None

        while True:
            await asyncio.sleep(POLL_INTERVAL)

            try:
                content = self._read_file()
            except FileNotFoundError:
                self._write_file("")
                content = ""

            if content == self.last_local_content:
                continue

            if content == self.last_received_content:
                self.last_local_content = content
                self.last_received_content = None
                continue

            await self.websocket.send(json.dumps({"type": "sync", "content": content}))
            self.last_local_content = content
            print("Sent local update")

    async def receive_remote_changes(self) -> None:
        assert self.websocket is not None

        async for raw_message in self.websocket:
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

            if content == self.last_local_content:
                continue

            self.last_received_content = content
            self._write_file(content)
            self.last_local_content = content
            print("Applied remote update")

    async def run(self) -> None:
        uri = f"ws://{self.server_host}:{PORT}"
        print(f"Connecting to {uri}")

        async with websockets.connect(uri) as websocket:
            self.websocket = websocket
            await asyncio.gather(
                self.send_local_changes(),
                self.receive_remote_changes(),
            )


def main() -> None:
    server_host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    client = SyncClient(server_host, FILE_PATH)

    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        print("\nClient stopped")


if __name__ == "__main__":
    main()
