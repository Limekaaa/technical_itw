"""Entry point: aggregate a player's window and save the Markdown report."""

import argparse
import re
from pathlib import Path
from dotenv import load_dotenv

from src.data_handling.aggregator import aggregate_all, render

BASE_DIR = Path(__file__).resolve().parent

load_dotenv()

def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate a player's daily report.")
    parser.add_argument("--player", default="p01")
    parser.add_argument("--date", default=None, help="Single day (takes precedence over --start/--end).")
    parser.add_argument("--start", default="2019-11-02")
    parser.add_argument("--end", default=None)
    parser.add_argument("--meal-timedelta", type=int, default=1800)
    args = parser.parse_args()

    start = args.date or args.start
    end = None if args.date else args.end
    data = aggregate_all(args.player, start, end, args.meal_timedelta)
    report = render(data)
    print(report)

    out_dir = BASE_DIR / "player_analysis"
    out_dir.mkdir(parents=True, exist_ok=True)
    if data["start_date"] == data["end_date"]:
        filename = f"{_safe_name(data['player_id'])}_{data['start_date']}.md"
    else:
        filename = f"{_safe_name(data['player_id'])}_{data['start_date']}_to_{data['end_date']}.md"
    out_path = out_dir / filename
    out_path.write_text(report)
    print(f"Saved report to {out_path}")


if __name__ == "__main__":
    main()
