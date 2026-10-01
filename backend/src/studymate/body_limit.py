import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

MAX_PDF_BYTES = 25 * 1024 * 1024
MAX_REQUEST_BYTES = MAX_PDF_BYTES + 1024 * 1024


class UploadBodyLimit:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "POST" or scope["path"] != "/api/documents":
            await self.app(scope, receive, send)
            return

        headers = dict(scope["headers"])
        try:
            content_length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            content_length = 0

        if content_length > MAX_REQUEST_BYTES:
            await self._reject(send)
            return

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > MAX_REQUEST_BYTES:
                await self._reject(send)
                return
            body.extend(chunk)
            if not message.get("more_body", False):
                break

        replayed = False

        async def replay_receive() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay_receive, send)

    @staticmethod
    async def _reject(send: Send) -> None:
        body = json.dumps({"detail": "Upload exceeds the 25 MiB PDF limit"}).encode()
        await send({
            "type": "http.response.start",
            "status": 413,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
        })
        await send({"type": "http.response.body", "body": body})
