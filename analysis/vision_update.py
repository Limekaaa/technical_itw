"""Fold Gemini vision cache into audit tables (run AFTER vision_run.py completes).

Reads analysis/tables/vision_cache.json, writes:
  - is_food / is_food_error columns into tables/phase2c_food_files_{p01,p03,p05}.csv
  - tables/vision_summary.csv (per-participant food/non-food counts + file lists)
  - tables/vision_same_meal_pairs.csv (candidate pairs + decisions + gaps)
Then re-run render: .venv/bin/python -u -c "import sys; sys.path.insert(0,'analysis'); from audit_full import render_all; render_all()"
"""
import json
import sys
from pathlib import Path
from datetime import datetime

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
import pandas as pd  # noqa: E402

TAB = REPO / "analysis" / "tables"
CACHE = TAB / "vision_cache.json"
PARTICIPANTS = ["p01", "p03", "p05"]


def main():
    cache = json.loads(CACHE.read_text())
    is_food = cache.get("is_food", {})
    same = cache.get("same_meal", {})
    print(f"cache: {len(is_food)} is_food, {len(same)} pairs")

    summary_rows = []
    for p in PARTICIPANTS:
        fp = TAB / f"phase2c_food_files_{p}.csv"
        df = pd.read_csv(fp)
        base = REPO / "data" / p / "food-images"
        keys = [(str(base / f)) for f in df["file"]]
        df["is_food"] = [("YES" if is_food.get(k, {}).get("is_food") else "NO")
                         if k in is_food else "PENDING" for k in keys]
        df["is_food_error"] = [is_food.get(k, {}).get("error") or "" for k in keys]
        df["is_food_model"] = [is_food.get(k, {}).get("model", "gemini-3.5-flash-lite")
                               if k in is_food else "" for k in keys]
        df.to_csv(fp, index=False)
        sub = df[df["is_food"] != "PENDING"]
        n_yes = int((sub["is_food"] == "YES").sum())
        n_no = int((sub["is_food"] == "NO").sum())
        mod = "; ".join(f"{m}:{n}" for m, n in sorted(sub["is_food_model"].value_counts().items()))
        no_files = "; ".join(sorted(sub.loc[sub["is_food"] == "NO", "file"].tolist()))
        summary_rows.append(dict(participant=p, n_images=len(df),
                                 n_food_YES=n_yes, n_food_NO=n_no,
                                 n_pending=int((df["is_food"] == "PENDING").sum()),
                                 models=mod,
                                 non_food_files=no_files if no_files else "—"))
    pd.DataFrame(summary_rows).to_csv(TAB / "vision_summary.csv", index=False)

    pair_rows = []
    for key, v in same.items():
        try:
            f1, f2 = key.split("||")
        except ValueError:
            continue
        pair_rows.append(dict(participant=v.get("p", ""),
                              file1=Path(f1).name, file2=Path(f2).name,
                              same_meal=bool(v.get("same_meal")),
                              model=v.get("model", "gemini-3.5-flash-lite"),
                              error=v.get("error") or ""))
    pdf = pd.DataFrame(pair_rows)
    # attach time gaps from EXIF datetimes in food files tables
    dt_map = {}
    for p in PARTICIPANTS:
        df = pd.read_csv(TAB / f"phase2c_food_files_{p}.csv")
        for _, r in df.iterrows():
            if r.get("datetime"):
                try:
                    dt_map[(p, r["file"])] = datetime.fromisoformat(str(r["datetime"]))
                except ValueError:
                    pass
    if len(pdf):
        gaps = []
        for _, r in pdf.iterrows():
            a = dt_map.get((r["participant"], r["file1"]))
            b = dt_map.get((r["participant"], r["file2"]))
            gaps.append(abs((b - a).total_seconds()) if a and b else float("nan"))
        pdf["gap_s"] = gaps
    pdf.to_csv(TAB / "vision_same_meal_pairs.csv", index=False)
    print("wrote vision_summary.csv + vision_same_meal_pairs.csv")
    print(pd.DataFrame(summary_rows).to_string())


if __name__ == "__main__":
    main()
