"""Container entrypoint — runs uvicorn with the stream-service ASGI app."""

from __future__ import annotations

import logging

import uvicorn


def main() -> None:
    # uvicorn only configures its own loggers by default. Configure the
    # root logger so our `log.info(...)` calls in sqs_poller etc. land in
    # CloudWatch alongside uvicorn's access logs.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

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
