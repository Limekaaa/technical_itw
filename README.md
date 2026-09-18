# Technical Interview — Multimodal Athlete Monitoring

Data-analysis repo for a technical interview. It aggregates multi-source athlete data (Fitbit, PMSYS questionnaires, self-reported logs, meal photos) into daily player reports, then builds a training-ready dataset to predict **next-day readiness**.

- **Players:** `p01`, `p03`, `p05` — one row per player × day over `2019-11-01 → 2020-03-31` (152 days, 456 rows, 290 labeled).
- **Pipeline:** daily aggregation → audit/EDA → pre-processing → correlation analysis → LOPO XGBoost validation → refit of one winning pipeline.
- **Online repo:** <https://github.com/Limekaaa/technical_itw>

## 1. Initialisation (run on any machine)

### 1.1 Prerequisites

- Python `>= 3.10`, [`uv`](https://docs.astral.sh/uv/) (`uv --version`), and Git.
- A Gemini API key (only needed for food-photo vision calls, see §1.4).

### 1.2 Clone and environment

```bash
git clone https://github.com/Limekaaa/technical_itw
cd technical_itw

# create + activate an isolated env
uv venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# install runtime deps (xgboost is pinned: validation used 3.2.0)
uv pip install \
  pandas numpy pillow openpyxl python-dotenv python-dateutil \
  scipy scikit-learn matplotlib pytest \
  "xgboost==3.2.0" "google-genai==2.23.0"
```

All entrypoints below assume the venv is activated. With `uv` you can also prefix any command with `uv run`, e.g. `uv run python main.py --help`.

### 1.3 Data folder

`data/` is gitignored (see `.gitignore`), so a fresh clone has **no data**. Copy it in before running anything. Exact layout:

```
data/
  participant-overview.xlsx   # 16 participants (p01–p16); only p01/p03/p05 have sensor-grade data
  p01/
    fitbit/
      calories.json
      distance.json
      steps.json
      heart_rate.json
      resting_heart_rate.json
      time_in_heart_rate_zones.json
      sleep.json
      exercise.json
      sleep_score.csv
    pmsys/
      wellness.csv
      srpe.csv
      injury.csv
    googledocs/
      reporting.csv
    food-images/              # 321 loose .jpg/.jpeg/.png
  p03/
    fitbit/                   # NOTE: no heart_rate.json for p03 (same 8 other files as p01)
      calories.json
      distance.json
      steps.json
      resting_heart_rate.json
      time_in_heart_rate_zones.json
      sleep.json
      exercise.json
      sleep_score.csv
    pmsys/
      wellness.csv
      srpe.csv
      injury.csv
    googledocs/
      reporting.csv
    food-images/              # 136 loose .jpg/.jpeg/.png
  p05/
    fitbit/                   # same 9 files as p01 (heart_rate.json present)
      calories.json
      distance.json
      steps.json
      heart_rate.json
      resting_heart_rate.json
      time_in_heart_rate_zones.json
      sleep.json
      exercise.json
      sleep_score.csv
    pmsys/
      wellness.csv
      srpe.csv
      injury.csv
    googledocs/
      reporting.csv
    food-images/              # 186 loose .jpg/.jpeg/.png
```

### 1.4 Gemini API key (only for vision)

Without a key, aggregation reports and the pre-processing build still run — photo-macro calls just return empty with a warning and macros stay `NaN`. With a key, day macros are estimated and cached.

- **Go to Google AI Studio:** open <https://aistudio.google.com/apikey>.
- **Sign in:** log in with your Google account.
- **Generate the key:** click **"Create API key"**.
- **Select a project:** choose **"Create API key in new project"** for a fresh start.
- **Copy and save:** click **Copy** and store the key securely — it is the password your app uses to call the Gemini API.

Then wire it up:

```bash
cp .env.public .env
# edit .env and set:
# GEMINI_API_KEY=<paste-your-key-here>
```

Verify with:

```bash
uv run python main.py --help
uv run pytest unit_tests/ -q   # mostly mocked/offline; aggregator nutrition paths may attempt vision calls if a key is set
```

## 2. Repository structure

| Path | What's inside |
|---|---|
| `main.py` | Single entrypoint. **Report mode** (default): daily/window Markdown report per player → stdout + `player_analysis/`. **`--preprocess` mode**: builds `output_dataset/training_dataset.csv`. |
| `data/` | Raw sources only (not committed). See §1.3. |
| `src/data_handling/` | Readers + daily aggregator. `fitbit_reader.py`, `pmsys_reader.py`, `reporting_reader.py`, `food_reader.py` (EXIF + Gemini), `macro_estimator.py` (cached day macros), `aggregator.py` (`aggregate_all` + `render`). |
| `src/utils/` | `date_handler.py` (`standardize_date`, window bounds) — every reader goes through it. |
| `src/pre_processing/` | Training-dataset builder. `pre_processor.py` (orchestrator) + `outliers_handler/` (sensor artifacts, physio bounds, non-wear, meal grouping) + `missing_values_handler/` (forward-fill, indicators). |
| `analysis/` | EDA + audit. `audit_full.py` generates `phase1/2a/2b/2c/3` reports + `tables/`; `correlation_analysis.py` → redundancy/label analysis; `vision_run.py` / `vision_waiter.py` / `vision_update.py` → food-vision audit; `training_metrics.csv`, `confusion_matrices.csv`; legacy `analyze_all.py` → `findings.md`. |
| `training_experiments/` | LOPO XGBoost validation (`config.py`, `features.py`, `data.py`, `model.py`, `metrics.py`, `run.py`) + `winning_pipeline.py` (final refit). |
| `output_dataset/` | Generated artifacts: `training_dataset.csv`, `data_dictionary.csv`, `final_training_dataset.csv`, `final_data_dictionary.csv`, `macro_cache.json`, `winning_pipeline_*`. |
| `player_analysis/` | Example generated reports (e.g. `p01_2019-11-01_to_2019-11-07.md`). |
| `unit_tests/` | `aggregators_test.py`, `pre_processing_tests.py`, `date_handler_tests.py`, `training_experiments_tests.py` (42 tests; vision mostly mocked). |
| `plan/` | `plan_data_processing.md` — the pre-processing spec the code implements. |

## 3. How to read the repo (reviewer guide)

### 3.1 Data handling — daily aggregation + nutrition from photos

**Code:**
- `src/data_handling/aggregator.py::aggregate_all` (plus `aggregate_activity`, `aggregate_sleep` with morning-attribution, `aggregate_questionnaire`, `aggregate_injury`, `aggregate_nutrition`, `render`). One call gathers, for a player + day/window: activity totals, sleep nights, wellness/sRPE/reporting answers, injury state, meal/photo counts.
- Readers: `fitbit_reader.py`, `pmsys_reader.py`, `reporting_reader.py` — each takes `(player_id, start_date, end_date=None)`; single date = full calendar day.
- Nutrition: `food_reader.py::_read_image_metadata` (Pillow EXIF `DateTime` → photo date), `photo_selector_by_date_player`, `is_photo_food`, `is_it_same_meal`, `helper_get_macro_nutrients_from_photos` / `get_macro_nutrients_from_photos` (Gemini JSON `calories/protein/carbohydrates/fats` + time-preselector/union-find meal grouping). `macro_estimator.py` is the training-build variant (one cached call per food-day → `macro_cache.json`). `outliers_handler/meal_grouping.py` is the offline deterministic 15 s grouping (no API).

**Read:** `player_analysis/*.md` first (concrete output), then `analysis/phase2c_food_injury.md` (§2C.2 for the data-derived 15 s threshold, §2C.4 for vision validation) and `analysis/lexic.md` §4 for image/EXIF vocabulary.

### 3.2 Database overview

**Code/data:** `data/` layout (§1.3) + `src/data_handling/*_reader.py` schemas.

**Read:** `analysis/phase1_schema_audit.md` + `analysis/tables/phase1_*.csv` (inventory, schema matrix, temporal horizon 2019-11-01→2020-03-31) and `analysis/lexic.md` §1 (per-source variable definitions). Note: `analysis/findings.md` / `analyze_all.py` is the early basic report, superseded by the `phase*.md` audit. Key facts: `heart_rate.json` missing for `p03`, p01 DST duplicates on 2020-03-29, food photos only Feb–Mar.

### 3.3 Data pre-processing

**Code:** `src/pre_processing/pre_processor.py` (`build_training_dataset`, `build_daily_row`, `add_rolling_load_features`, `add_slow_median_features`, `add_causal_label`, `ordered_columns`, `get_feature_columns`) orchestrates `outliers_handler/{sensor_artifacts,physio_bounds,nonwear,meal_grouping}.py` and `missing_values_handler/{forward_fill,indicators}.py`. Label is `readiness_next_day` (cleaned readiness shifted −1, causal); other subjective wellness items are banned from features. Spec: `plan/plan_data_processing.md`.

**Read:** `analysis/phase3_preprocessing_modeling.md` (cleaning checklist, day-grain alignment, feature catalogue) then `analysis/correlation_analysis.md` §§2–3/§6–7 (exact duplicates, redundancy groups, Tier-1/Tier-2 drop lists, minimal set) and `output_dataset/data_dictionary.csv`.

### 3.4 Modeling

**Code:** `training_experiments/` — `config.py` (A_expressive/B_balanced/C_robust, fixed, no tuning), `features.py` (S1 Tier-1 / S2 Tier-1+2 / S3 minimal-33), `data.py` (290 labeled rows, LOPO splits), `model.py` (per-participant demeaning, NaN-native XGBoost), `metrics.py` (MAE/RMSE/R² + rounded accuracy/QWK/confusion), `run.py` (27 fits), `winning_pipeline.py` (refit A+S3 on all rows).

**Read:** `analysis/training_experiments.md` (protocol, per-fold table, decision **A_expressive + S3_minimal**, honest limits) with `analysis/correlation_analysis.md` §§4–5 (participant confounding: pooled correlations mislead; within-person load/intensity → lower readiness).

## 4. Usage per brick

### 4.1 `main.py` — reports and dataset build

```bash
# single day (takes precedence over --start/--end)
uv run python main.py --player p01 --date 2019-11-02

# window (sleep is morning-attributed: nights ENDING in the window)
uv run python main.py --player p01 --start 2019-11-01 --end 2019-11-07

# another player + legacy 30-min meal grouping instead of 1800 s default
uv run python main.py --player p05 --date 2020-01-30 --meal-timedelta 1800

# build the training dataset (defaults: p01,p03,p05, full horizon)
uv run python main.py --preprocess
uv run python main.py --preprocess --players p01,p03 --out output_dataset/training_dataset.csv
```

Outputs: reports print to stdout and save to `player_analysis/<player>_<day[_to_day]>.md`; preprocess prints shape/label-availability/feature-count and writes `training_dataset.csv` + `data_dictionary.csv` (macros cached in `macro_cache.json`, resumable).

### 4.2 Training experiments

```bash
# validate 3 configs x 3 sets x 3 LOPO folds (writes analysis/training_metrics.csv, confusion_matrices.csv)
uv run python -m training_experiments.run

# refit winning A+S3 pipeline on all 290 labeled rows (writes final_* + model.ubj + demean params)
uv run python -m training_experiments.winning_pipeline
uv run python -m training_experiments.winning_pipeline --out-dir output_dataset
```

### 4.3 Analysis scripts and tests

```bash
uv run python analysis/audit_full.py            # regenerates phase*.md + tables/
uv run python analysis/correlation_analysis.py # regenerates correlation_*.csv, label_relevance.csv
uv run pytest unit_tests/ -q                   # fast, offline (vision mocked)
```

`vision_run.py` is the long resumable Gemini audit (`vision_cache.json`); you don't need to run it to review — read `tables/vision_summary.csv` + `phase2c_food_injury.md` instead.

## 5. Honest result in one paragraph

LOPO validation finds no reliable overall gain over a train-mean baseline: the only fold with target variance (p01) improves modestly, p03 is flat/unpredictable by construction, and the p05 "win" is level-matching. Models predict only classes 5–6 (QWK ≈ 0). Tier-2 redundancy removal and the 33-feature S3 set cost nothing measurable, so the validated deployable is **A_expressive + S3_minimal** — details and per-fold numbers in `analysis/training_experiments.md` §§2–6.
