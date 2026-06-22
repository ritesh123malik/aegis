"""
Aegis — feature engineering for Astram event data.

Transforms raw Bengaluru traffic-event records into model-ready features.
Pipeline order: load -> parse datetimes -> build disruption labels on the full
dataset -> drop dead columns for the training feature matrix -> clean planned
event durations for the duration model.

Raw CSV: data/raw/astram_event_data.csv (8,173 rows × 46 columns).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths & constants (adjust here for judges / reproducibility)
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_PATH = PROJECT_ROOT / "data" / "raw" / "astram_event_data.csv"

# Verified 91%+ null — excluded from the model-training feature matrix only.
# route_path and assigned_to_police_id stay in the untouched raw copy for later
# recommendation-engine / diversion-route work.
DEAD_COLUMNS = [
    "comment",
    "map_file",
    "meta_data",
    "direction",
    "resolved_at_address",
    "resolved_at_latitude",
    "resolved_at_longitude",
    "resolved_by_id",
    "resolved_datetime",
    "route_path",
    "citizen_accident_id",
    "assigned_to_police_id",
    "age_of_truck",
    "reason_breakdown",
    "cargo_material",
    "end_address",
]

# 30 days — stale / unclosed planned tickets, not real event durations.
MAX_PLANNED_DURATION_MINUTES = 43_200

# Guard rails for clean_planned_event_durations (467 planned rows in source data).
PLANNED_DURATION_ROW_MIN = 350
PLANNED_DURATION_ROW_MAX = 430

# Severity label from (requires_road_closure, priority) — NOT event_cause.
DISRUPTION_CLASS_MAP: dict[tuple[bool, str], str] = {
    (False, "Low"): "Low",
    (False, "High"): "Medium",
    (True, "Low"): "High",
    (True, "High"): "Critical",
}


def load_raw_events(path: str) -> pd.DataFrame:
    """Load the Astram CSV, treating literal 'NULL' and '[]' as missing values."""
    # Astram exports encode missing values as strings, not empty cells.
    return pd.read_csv(path, na_values=["NULL", "[]", ""], low_memory=False)


def drop_dead_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Remove high-null columns from the training feature set (not from raw storage)."""
    # Only drop columns that exist — safe if a subset was already removed upstream.
    cols_to_drop = [col for col in DEAD_COLUMNS if col in df.columns]
    return df.drop(columns=cols_to_drop)


def parse_datetimes(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce event timestamp columns to timezone-aware UTC datetimes."""
    out = df.copy()
    datetime_columns = [
        "start_datetime",
        "end_datetime",
        "modified_datetime",
        "closed_datetime",
    ]
    for column in datetime_columns:
        if column in out.columns:
            out[column] = pd.to_datetime(out[column], utc=True, errors="coerce", format="mixed")
    return out


def normalize_event_cause(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse the Debris/debris duplicate to a single canonical event_cause value."""
    out = df.copy()
    out["event_cause"] = out["event_cause"].replace({"Debris": "debris"})
    return out


def _coerce_requires_road_closure(series: pd.Series) -> pd.Series:
    """Coerce requires_road_closure to bool — CSV may store TRUE/FALSE strings or bools."""

    def to_bool(value):
        if pd.isna(value):
            return pd.NA
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        text = str(value).strip().lower()
        if text in {"true", "t", "1", "yes"}:
            return True
        if text in {"false", "f", "0", "no"}:
            return False
        raise ValueError(f"Unrecognized requires_road_closure value: {value!r}")

    return series.map(to_bool)


def build_disruption_class(df: pd.DataFrame) -> pd.DataFrame:
    """
    Assign disruption_class from (requires_road_closure, priority) on the full dataset.

    Key is NOT event_cause — two rows with the same cause can differ in severity when
    closure requirement or priority differs. Rows with null priority (~2) are dropped.
    """
    out = normalize_event_cause(df)

    # priority has ~0.02% nulls (2 rows) — drop rather than impute.
    out = out.loc[out["priority"].notna()].copy()

    closure_bool = _coerce_requires_road_closure(out["requires_road_closure"])
    if closure_bool.isna().any():
        raise ValueError("Unexpected null requires_road_closure after coercion.")

    out["disruption_class"] = [
        DISRUPTION_CLASS_MAP[(bool(closure), str(priority))]
        for closure, priority in zip(closure_bool, out["priority"], strict=True)
    ]

    return out


def add_temporal_features(df: pd.DataFrame) -> pd.DataFrame:
    """Derive cyclic temporal features from the start_datetime column."""
    out = df.copy()
    if "start_datetime" not in out.columns:
        raise ValueError("Missing 'start_datetime' column in DataFrame.")

    dt_series = pd.to_datetime(out["start_datetime"])

    out["hour"] = dt_series.dt.hour.astype(int)
    out["hour_sin"] = np.sin(2 * np.pi * out["hour"] / 24)
    out["hour_cos"] = np.cos(2 * np.pi * out["hour"] / 24)
    out["day_of_week"] = dt_series.dt.dayofweek.astype(int)
    out["is_weekend"] = out["day_of_week"].isin([5, 6])
    out["month"] = dt_series.dt.month.astype(int)
    return out


# IMPORTANT: When this function is called from a cross-validation training loop,
# fit_on must be set to the TRAINING FOLD ONLY, never the full dataset and never
# the test fold, to prevent data leakage from validation/test rows into features.
def add_corridor_frequency_feature(
    df: pd.DataFrame, fit_on: pd.DataFrame = None
) -> pd.DataFrame:
    """
    Adds corridor_event_rate feature based on the frequency of (corridor, event_cause)
    pairs in the fit_on dataset.
    """
    if fit_on is None:
        fit_on = df

    numerator = fit_on.groupby(["corridor", "event_cause"]).size()
    denominator = fit_on.groupby("corridor").size()
    rates = numerator / denominator

    out = df.copy()
    idx = pd.MultiIndex.from_frame(out[["corridor", "event_cause"]])
    out["corridor_event_rate"] = idx.map(rates).fillna(0.0)
    return out


def clean_planned_event_durations(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter planned events to rows with plausible, positive durations.

    Used for the duration prediction model — not applied to unplanned incidents.
    """
    # Scope to planned events only (467 rows in the verified dataset).
    planned = df.loc[df["event_type"] == "planned"].copy()

    # Drop the single planned row with no end_datetime (expected in real data).
    planned = planned.loc[planned["end_datetime"].notna()]

    # Duration in minutes from verified start/end timestamps.
    planned["duration_minutes"] = (
        (planned["end_datetime"] - planned["start_datetime"]).dt.total_seconds() / 60
    )

    # Remove anonymization/logging artifacts with zero or negative duration (~46 rows).
    planned = planned.loc[planned["duration_minutes"] > 0]

    # Remove stale tickets left open beyond 30 days (~22 rows).
    planned = planned.loc[planned["duration_minutes"] <= MAX_PLANNED_DURATION_MINUTES]

    row_count = len(planned)
    if row_count < PLANNED_DURATION_ROW_MIN or row_count > PLANNED_DURATION_ROW_MAX:
        raise ValueError(
            f"clean_planned_event_durations produced {row_count} rows; "
            f"expected roughly {PLANNED_DURATION_ROW_MIN}–{PLANNED_DURATION_ROW_MAX}. "
            "Run diagnose_planned_duration_filters() before proceeding."
        )

    return planned


def split_planned_event_durations(
    planned_df: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split planned events into single-day planned events (<= 48 hours)
    and multi-day planned disruptions (> 48 hours).
    """
    multiday_threshold = 2880  # 48 hours in minutes

    multiday = planned_df.loc[planned_df["duration_minutes"] > multiday_threshold].copy()
    single_day = planned_df.loc[planned_df["duration_minutes"] <= multiday_threshold].copy()

    print("\n=== Split Planned Event Durations ===")
    print(f"Total input planned rows: {len(planned_df)}")

    print(f"\nMulti-day planned disruptions (> 48h) row count: {len(multiday)}")
    print("Event cause breakdown:")
    print(multiday["event_cause"].value_counts().to_string())

    print(f"\nSingle-day planned events (<= 48h) row count: {len(single_day)}")
    print("Event cause breakdown:")
    print(single_day["event_cause"].value_counts().to_string())
    print("=====================================\n")

    return single_day, multiday


def diagnose_planned_duration_filters(raw_df: pd.DataFrame, timed_df: pd.DataFrame) -> None:
    """Print a row-level audit of planned-event duration filtering (467 planned rows)."""
    planned_raw = raw_df.loc[raw_df["event_type"] == "planned"].copy()
    planned_timed = timed_df.loc[timed_df["event_type"] == "planned"].copy()

    total_planned = len(planned_raw)
    null_end = int(planned_timed["end_datetime"].isna().sum())
    with_end = planned_timed.loc[planned_timed["end_datetime"].notna()].copy()
    with_end["duration_minutes"] = (
        (with_end["end_datetime"] - with_end["start_datetime"]).dt.total_seconds() / 60
    )

    non_positive = with_end.loc[with_end["duration_minutes"] <= 0]
    zero_duration = int((with_end["duration_minutes"] == 0).sum())
    negative_duration = int((with_end["duration_minutes"] < 0).sum())
    after_positive = with_end.loc[with_end["duration_minutes"] > 0]
    stale = after_positive.loc[after_positive["duration_minutes"] > MAX_PLANNED_DURATION_MINUTES]
    surviving = after_positive.loc[after_positive["duration_minutes"] <= MAX_PLANNED_DURATION_MINUTES]

    print("=== Planned duration filter audit ===")
    print(f"Total planned rows:                         {total_planned}")
    print(f"Planned rows with null end_datetime:          {null_end}")
    print(f"Planned rows with duration_minutes <= 0:      {len(non_positive)}")
    print(f"  of which duration_minutes == 0:             {zero_duration}")
    print(f"  of which duration_minutes < 0:              {negative_duration}")
    print(f"Planned rows with duration_minutes > 43200:   {len(stale)}")
    print(f"Surviving planned rows:                       {len(surviving)}")
    accounted = null_end + len(non_positive) + len(stale) + len(surviving)
    print(f"Sum of buckets (should equal {total_planned}): {accounted}")

    if len(non_positive) > 0:
        print("\nSample rows with duration_minutes <= 0 (raw strings + parsed + duration):")
        sample = non_positive.head(8)
        for _, row in sample.iterrows():
            raw_row = planned_raw.loc[planned_raw["id"] == row["id"]].iloc[0]
            print(
                f"  id={row['id']} | "
                f"raw_start={raw_row['start_datetime']!r} | "
                f"raw_end={raw_row['end_datetime']!r} | "
                f"parsed_start={row['start_datetime']} | "
                f"parsed_end={row['end_datetime']} | "
                f"duration_minutes={row['duration_minutes']:.4f}"
            )


if __name__ == "__main__":
    raw_path = DEFAULT_RAW_PATH
    if not raw_path.exists():
        raise FileNotFoundError(
            f"Expected dataset at {raw_path}. "
            "Copy the Astram anonymized CSV to data/raw/astram_event_data.csv."
        )

    # Keep a full untouched copy — route_path & assigned_to_police_id needed later.
    raw_full = load_raw_events(str(raw_path))
    timed = parse_datetimes(raw_full)

    diagnose_planned_duration_filters(raw_full, timed)

    labeled = build_disruption_class(timed)
    temporal = add_temporal_features(labeled)
    corridor_freq = add_corridor_frequency_feature(temporal, fit_on=None)
    feature_matrix = drop_dead_columns(corridor_freq)

    # Save the full feature matrix for the severity model
    processed_dir = PROJECT_ROOT / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    feature_matrix.to_parquet(processed_dir / "severity_features.parquet", index=False)
    print(f"Saved full feature matrix to {processed_dir / 'severity_features.parquet'}")

    print(f"\nRaw rows:              {len(raw_full):,}")
    print(f"Full labeled rows:     {len(labeled):,}  (8173 - 2 priority-null)")
    print(f"Feature matrix cols:   {len(feature_matrix.columns)}")
    print("\nDisruption class distribution (full labeled dataset):")
    print(labeled["disruption_class"].value_counts().to_string())

    print("\n=== Feature engineering summary stats ===")
    print("\ncorridor_event_rate describe:")
    print(corridor_freq["corridor_event_rate"].describe().to_string())
    print("\nhour_sin and hour_cos describe:")
    print(corridor_freq[["hour_sin", "hour_cos"]].describe().to_string())

    try:
        planned_training = clean_planned_event_durations(feature_matrix)

        # Split into single-day and multi-day
        single_day, multiday = split_planned_event_durations(planned_training)

        # Save single-day planned events for duration model
        single_day.to_parquet(processed_dir / "cleaned_events.parquet", index=False)
        print(f"Saved single-day planned events to {processed_dir / 'cleaned_events.parquet'}")

        # Save multi-day planned disruptions
        # Note: these may warrant a separate, simpler model (e.g. predicting whether a disruption
        # is short-term vs. long-term-project, rather than predicting exact duration) as future work.
        multiday.to_parquet(processed_dir / "multiday_planned_disruptions.parquet", index=False)
        print(f"Saved multi-day planned disruptions to {processed_dir / 'multiday_planned_disruptions.parquet'}")

        print(f"\nPlanned training rows (single-day): {len(single_day):,}")
    except ValueError as exc:
        print(f"\nclean_planned_event_durations: {exc}")
        print("Resolve the audit above before running 03_train_duration_model.py.")
