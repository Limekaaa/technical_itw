"""Wait for Gemini quota to clear, then launch the vision pass.

Probes every 10 min with ONE strict call on an already-labeled image
(negligible quota cost). On success, launches analysis/vision_run.py
detached and exits. Gives up after ~9 h.

Run detached:
  setsid nohup .venv/bin/python -u analysis/vision_waiter.py > analysis/tables/vision_waiter.log 2>&1 < /dev/null &
"""
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from analysis.vision_run import strict_is_photo_food  # noqa: E402

PROBE_IMAGE = str(REPO / "data" / "p05" / "food-images" / "IMG_2215.jpg")
WAIT_SECONDS = 600
MAX_WAITS = 200  # ~33 h, covers a full rolling-24h quota cycle


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] waiter: {msg}", flush=True)


def main():
    for i in range(1, MAX_WAITS + 1):
        try:
            val = strict_is_photo_food(PROBE_IMAGE)
            log(f"probe {i}: quota clear (answer={val}); launching vision_run.py")
            subprocess.Popen(
                [sys.executable, "-u", str(REPO / "analysis" / "vision_run.py")],
                stdout=open(REPO / "analysis" / "tables" / "vision_run.log", "a"),
                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                start_new_session=True, cwd=str(REPO))
            log("launched; waiter exiting")
            return
        except Exception as e:  # noqa: BLE001
            log(f"probe {i}/{MAX_WAITS}: still limited ({repr(e)[:120]}); sleeping {WAIT_SECONDS}s")
            time.sleep(WAIT_SECONDS)
    log("waiter: gave up after ~9 h without quota")


if __name__ == "__main__":
    main()
