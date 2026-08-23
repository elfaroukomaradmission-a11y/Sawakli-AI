"""
Minimal Sawakli worker entrypoint.

Idles and touches a heartbeat file so the compose healthcheck can confirm
it's alive. Wire in real job dispatch (jobs/, orchestration/, scheduler/)
once that layer is designed.
"""

import pathlib
import time

HEARTBEAT_PATH = pathlib.Path("/tmp/worker_heartbeat")
INTERVAL_SECONDS = 5


def main() -> None:
    print("Sawakli worker started, idling...")
    while True:
        HEARTBEAT_PATH.touch()
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
