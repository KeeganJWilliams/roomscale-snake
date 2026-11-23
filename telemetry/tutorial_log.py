"""CSV of one tutorial run, for the user study.

One row per step, then a TOTAL row:

    step, seconds, wrong_turns, retries, skipped

`skipped` means a facilitator pressed N to move the player on, so a run
with any skipped step was assisted. The TOTAL row's `step` is TOTAL for a
finished run or ABORTED if it was quit early; its `seconds` is the time to
reach the finish screen.
"""

import csv
import logging
import pathlib
import time

log = logging.getLogger(__name__)

DEFAULT_DIR = pathlib.Path(__file__).parent / "logs"
HEADER = ("step", "seconds", "wrong_turns", "retries", "skipped")


def write_tutorial_log(tutorial, directory=None):
    """Write the run to telemetry/logs/tutorial_<timestamp>.csv. Returns the
    path, or None if it couldn't be written (never raises into the game)."""
    directory = pathlib.Path(directory or DEFAULT_DIR)
    path = directory / f"tutorial_{time.strftime('%Y%m%d_%H%M%S')}.csv"
    records = [r for r in tutorial.records if r.name != "done"]
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(HEADER)
            for r in records:
                writer.writerow([r.name, f"{r.seconds:.2f}", r.wrong_turns, r.retries,
                                 int(r.skipped)])
            writer.writerow(["ABORTED" if tutorial.aborted else "TOTAL",
                             f"{tutorial.completion_seconds or 0:.2f}",
                             sum(r.wrong_turns for r in records),
                             sum(r.retries for r in records),
                             int(tutorial.assisted)])
    except OSError:
        log.exception("could not write tutorial log %s", path)
        return None
    log.info("tutorial log -> %s", path)
    return path
