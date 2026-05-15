"""Container entrypoint — runs uvicorn with the stream-service ASGI app."""

from __future__ import annotations

import uvicorn


def main() -> None:
    uvicorn.run(
        "stream.app:app",
        host="0.0.0.0",
        port=8080,
        log_level="info",
        access_log=True,
        timeout_keep_alive=120,
    )


if __name__ == "__main__":
    main()
