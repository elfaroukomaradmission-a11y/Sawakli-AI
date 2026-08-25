import subprocess
import sys
import time
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import delete, func, select

from sawakli.db.models.jobs import Job
from sawakli.db.session import SessionLocal

# Number of worker processes running concurrently.
WORKER_COUNT = 5

# Test dataset: 100 PENDING and 100 RUNNING jobs.
PENDING_COUNT = 100
RUNNING_COUNT = 100

# Let the workers run multiple cycles.
RUN_SECONDS = 10


def create_jobs() -> None:
    db = SessionLocal()

    try:
        # Start with a clean database.
        db.execute(delete(Job))
        db.commit()

        now = datetime.now(UTC)

        # Create jobs for the claim pipeline.
        jobs = [
            Job(
                id=uuid4(),
                organization_id=uuid4(),
                campaign_ids=[],
                status="PENDING",
                priority="HIGH",
                created_at=now,
            )
            for _ in range(PENDING_COUNT)
        ]

        # Create jobs for the execution pipeline.
        jobs.extend(
            Job(
                id=uuid4(),
                organization_id=uuid4(),
                campaign_ids=[],
                status="RUNNING",
                priority="HIGH",
                created_at=now,
            )
            for _ in range(RUNNING_COUNT)
        )

        db.add_all(jobs)
        db.commit()

    finally:
        db.close()


def test_multiple_workers():
    create_jobs()

    # Start real worker processes using the production entry point.
    workers = [
        subprocess.Popen(
            [sys.executable, "-m", "sawakli.worker"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for _ in range(WORKER_COUNT)
    ]

    try:
        # Let all workers run concurrently.
        time.sleep(RUN_SECONDS)

    finally:
        # Stop all workers after the test period.
        for worker in workers:
            worker.terminate()

        for worker in workers:
            worker.wait(timeout=5)

    db = SessionLocal()

    try:
        # Confirm that all test jobs still exist.
        total = db.scalar(select(func.count()).select_from(Job))

        pending = db.scalar(select(func.count()).select_from(Job).where(Job.status == "PENDING"))

        running = db.scalar(select(func.count()).select_from(Job).where(Job.status == "RUNNING"))

        assert total == PENDING_COUNT + RUNNING_COUNT

        # Confirm that the workers actually processed jobs.
        assert pending < PENDING_COUNT or running < RUNNING_COUNT

    finally:
        db.close()
