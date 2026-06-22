import pandas as pd
from sqlalchemy import create_engine
import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from backend.app.database import DATABASE_URL

def seed_database():
    csv_path = PROJECT_ROOT / "data" / "raw" / "astram_event_data.csv"
    if not csv_path.exists():
        print(f"Error: {csv_path} does not exist.")
        return

    print(f"Loading raw events from {csv_path}...")
    df = pd.read_csv(csv_path, na_values=["NULL", "[]", ""], low_memory=False)

    # Rename columns to match database schema
    df = df.rename(columns={"id": "event_id"})

    # Normalize / Clean
    df["event_cause"] = df["event_cause"].replace({"Debris": "debris"})
    df["requires_road_closure"] = df["requires_road_closure"].astype(str).str.upper() == "TRUE"

    # Parse datetimes
    for col in ["start_datetime", "end_datetime"]:
        df[col] = pd.to_datetime(df[col], utc=True, errors="coerce", format="mixed")

    # Select only columns present in the schema
    schema_cols = [
        "event_id", "event_type", "event_cause", "corridor",
        "latitude", "longitude", "requires_road_closure", "priority",
        "start_datetime", "end_datetime", "description"
    ]
    
    # Filter columns and clean up
    df_to_load = df[[col for col in schema_cols if col in df.columns]].copy()
    df_to_load = df_to_load.drop_duplicates(subset=["event_id"])
    df_to_load = df_to_load.dropna(subset=["event_id"])

    # Connect to the database and write rows
    engine = create_engine(DATABASE_URL)
    print(f"Writing {len(df_to_load)} events to database ({DATABASE_URL})...")
    
    # We clear any existing events first to avoid duplicate primary key errors
    with engine.connect() as conn:
        # Using a raw delete to be safe
        from sqlalchemy import text
        conn.execute(text("TRUNCATE TABLE outcomes CASCADE;"))
        conn.execute(text("TRUNCATE TABLE predictions CASCADE;"))
        conn.execute(text("TRUNCATE TABLE events CASCADE;"))
        conn.commit()

    df_to_load.to_sql("events", con=engine, if_exists="append", index=False)
    print("Database seeding completed successfully!")

if __name__ == "__main__":
    seed_database()
