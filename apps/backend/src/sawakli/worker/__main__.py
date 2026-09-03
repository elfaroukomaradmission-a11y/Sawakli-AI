import pathlib
import tempfile
import time

from sawakli.db.session import SessionLocal
from sawakli.worker.scheduler.loop import run_once

HEARTBEAT_PATH = pathlib.Path(tempfile.gettempdir()) / "worker_heartbeat"
INTERVAL_SECONDS = 5


def main() -> None:
    print("Sawakli worker started.")

    while True:
        db = SessionLocal()

        try:
            processed_jobs = run_once(db)

            print(f"Worker cycle complete. Processed: {len(processed_jobs)}")

            HEARTBEAT_PATH.touch()

        except Exception as exc:
            db.rollback()
            print(f"Worker cycle failed: {exc}")

        finally:
            db.close()

        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
