"""ECS Fargate entrypoint — runs Worker handler in a continuous poll loop."""

from __future__ import annotations

import logging
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("worker-loop")

from worker.handler import lambda_handler

POLL_INTERVAL_SECONDS = 10


def main() -> None:
    import os
    import anthropic
    token = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
    logger.info(
        "Worker starting — token_len=%d prefix=%s has_newline=%s sdk=%s",
        len(token), token[:15] + "...", "\n" in token, anthropic.__version__,
    )
    logger.info("Worker starting continuous poll loop")
    while True:
        try:
            result = lambda_handler({}, None)
            processed = result.get("processed", 0)
            errors = result.get("errors", 0)
            if processed > 0 or errors > 0:
                logger.info(f"Poll: processed={processed}, errors={errors}")
        except Exception as e:
            logger.error(f"Poll error: {e}", exc_info=True)
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
