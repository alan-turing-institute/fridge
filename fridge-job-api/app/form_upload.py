import asyncio
from fastapi import HTTPException, Request
from python_multipart.exceptions import FormParserError
from python_multipart.multipart import MultipartParser, parse_options_header


class FormFileReader:
    """
    A read-only file over the file in a multipart/form-data request, which reads the request
    body only as more of the file is asked for. This lets boto3 send the file on to S3 while it
    is still arriving, rather than FastAPI's UploadFile saving the whole body to disk first.

    Create it on the event loop, then read it from other threads (e.g. boto3's): each read
    waits for the event loop to fetch the next piece of the body.
    """

    def __init__(self, request: Request, field_name: str = "file"):
        mime_type, params = parse_options_header(
            request.headers.get("content-type", "")
        )
        if mime_type != b"multipart/form-data" or b"boundary" not in params:
            raise HTTPException(
                status_code=422, detail="Request body must be multipart/form-data."
            )
        self.field_name = field_name
        self.filename: str | None = None
        self.content_type: str | None = None

        self._loop = asyncio.get_running_loop()
        self._body = request.stream()
        self._parser = MultipartParser(
            params[b"boundary"],
            callbacks={
                "on_part_begin": self._on_part_begin,
                "on_header_field": self._on_header_field,
                "on_header_value": self._on_header_value,
                "on_header_end": self._on_header_end,
                "on_headers_finished": self._on_headers_finished,
                "on_part_data": self._on_part_data,
                "on_part_end": self._on_part_end,
            },
        )
        self._headers: dict[bytes, bytes] = {}
        self._header_field = b""
        self._header_value = b""
        # Whether the file field has not started yet, is being read, or has ended
        self._state = "before"
        self._buffer = bytearray()

    def open(self) -> None:
        """Read the body up to the start of the file, so that its name and type are known."""
        while self._state == "before":
            if not self._feed():
                raise HTTPException(
                    status_code=422, detail=f"Missing file field '{self.field_name}'."
                )

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return False

    def read(self, size: int = -1) -> bytes:
        """Read `size` bytes of the file, fewer only at its end, or the rest if `size` < 0."""
        while self._state != "done" and (size < 0 or len(self._buffer) < size):
            if not self._feed():
                raise HTTPException(
                    status_code=400, detail="Request body ended mid-file."
                )
        if size < 0:
            size = len(self._buffer)
        data = bytes(self._buffer[:size])
        del self._buffer[:size]
        return data

    def _feed(self) -> bool:
        """Pass the next piece of the body to the parser. Returns False at the end of the body."""
        chunk = asyncio.run_coroutine_threadsafe(
            self._next_chunk(), self._loop
        ).result()
        try:
            if not chunk:
                self._parser.finalize()
                return False
            self._parser.write(chunk)
            return True
        except FormParserError:
            raise HTTPException(status_code=400, detail="Invalid multipart data.")

    async def _next_chunk(self) -> bytes:
        # The body ends with an empty chunk
        return await anext(self._body, b"")

    def _on_part_begin(self) -> None:
        self._headers = {}

    def _on_header_field(self, data: bytes, start: int, end: int) -> None:
        self._header_field += data[start:end]

    def _on_header_value(self, data: bytes, start: int, end: int) -> None:
        self._header_value += data[start:end]

    def _on_header_end(self) -> None:
        self._headers[self._header_field.lower()] = self._header_value
        self._header_field = b""
        self._header_value = b""

    def _on_headers_finished(self) -> None:
        _, disposition = parse_options_header(self._headers.get(b"content-disposition"))
        # Only the first file in the named field is read. Other fields are ignored
        if (
            self._state == "before"
            and disposition.get(b"name") == self.field_name.encode()
            and b"filename" in disposition
        ):
            self.filename = disposition[b"filename"].decode()
            content_type = self._headers.get(b"content-type")
            self.content_type = content_type.decode() if content_type else None
            self._state = "reading"

    def _on_part_data(self, data: bytes, start: int, end: int) -> None:
        if self._state == "reading":
            self._buffer += data[start:end]

    def _on_part_end(self) -> None:
        if self._state == "reading":
            self._state = "done"
