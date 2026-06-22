"""
Aegis — End-to-End Endpoint Testing.

Tests create event endpoints, datetime timezone serialization, and predict endpoints
for both planned (duration model) and unplanned (severity model) events.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add project root to sys.path to enable robust imports
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# Detect database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://aegis:aegis@localhost:5432/aegis")
IS_SQLITE = DATABASE_URL.startswith("sqlite")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from backend.app.database import Base
from backend.app.main import app

def run_tests() -> None:
    # Initialize database metadata
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(bind=engine)
    print(f"Database initialized: {DATABASE_URL}")

    client = TestClient(app)

    event_id = None
    unplanned_event_id = None

    try:
        # --- TEST 1: Timezone Check ---
        print("\n=== Test 1: Timezone Check ===")
        # POST a test event with a timezone-aware ISO string
        event_payload = {
            "event_type": "planned",
            "event_cause": "construction",
            "corridor": "Mysore Road",
            "latitude": 12.97,
            "longitude": 77.59,
            "requires_road_closure": True,
            "priority": "High",
            "start_datetime": "2024-01-30T21:21:10+00:00",
            "description": "Test event"
        }
        res_post = client.post("/events", json=event_payload)
        assert res_post.status_code == 200, f"POST /events failed: {res_post.text}"
        event_id = res_post.json()["event_id"]
        print(f"Created event ID: {event_id}")

        # Query the database directly via raw SQL to check what database actually stores
        with engine.connect() as conn:
            stmt = text("SELECT start_datetime FROM events WHERE event_id = :event_id")
            result = conn.execute(stmt, {"event_id": event_id}).fetchone()
            raw_stored_val = result[0]
            print(f"Raw database stored value: {raw_stored_val}")

        # Fetch the event back via GET /events/{event_id}
        res_get = client.get(f"/events/{event_id}")
        assert res_get.status_code == 200, f"GET /events failed: {res_get.text}"
        api_retrieved_val = res_get.json()["start_datetime"]
        print(f"GET API response value:      {api_retrieved_val}")

        # --- TEST 2: Prediction Endpoints ---
        print("\n=== Test 2: Prediction Endpoints ===")

        # Scenario A: Predict planned event (duration model path)
        print("Testing POST /predict for planned event...")
        res_pred_planned = client.post("/predict", json={"event_id": event_id})
        assert res_pred_planned.status_code == 200, f"Predict planned failed: {res_pred_planned.text}"
        print("Predict planned response JSON:")
        print(res_pred_planned.json())

        # Scenario B: Predict unplanned event (severity model path)
        # First POST an unplanned event
        unplanned_payload = {
            "event_type": "unplanned",
            "event_cause": "vehicle_breakdown",
            "corridor": "Mysore Road",
            "latitude": 12.97,
            "longitude": 77.59,
            "requires_road_closure": False,
            "priority": "Low",
            "start_datetime": "2024-01-30T21:21:10+00:00",
            "description": "Test unplanned event"
        }
        res_unplanned_post = client.post("/events", json=unplanned_payload)
        assert res_unplanned_post.status_code == 200, f"POST /events (unplanned) failed: {res_unplanned_post.text}"
        unplanned_event_id = res_unplanned_post.json()["event_id"]

        print("\nTesting POST /predict for unplanned event...")
        res_pred_unplanned = client.post("/predict", json={"event_id": unplanned_event_id})
        assert res_pred_unplanned.status_code == 200, f"Predict unplanned failed: {res_pred_unplanned.text}"
        print("Predict unplanned response JSON:")
        print(res_pred_unplanned.json())

    finally:
        # Clean up database resources
        from backend.app.database import engine as app_engine
        
        try:
            with engine.connect() as conn:
                # Delete predictions first due to foreign keys
                if unplanned_event_id:
                    conn.execute(text("DELETE FROM predictions WHERE event_id = :eid"), {"eid": unplanned_event_id})
                    conn.execute(text("DELETE FROM events WHERE event_id = :eid"), {"eid": unplanned_event_id})
                if event_id:
                    conn.execute(text("DELETE FROM predictions WHERE event_id = :eid"), {"eid": event_id})
                    conn.execute(text("DELETE FROM events WHERE event_id = :eid"), {"eid": event_id})
                conn.commit()
                print("Test data cleaned up from database.")
        except Exception as e:
            print(f"Warning during test data cleanup: {e}")

        engine.dispose()
        app_engine.dispose()

        if IS_SQLITE:
            TEST_DB_PATH = PROJECT_ROOT / "test.db"
            if TEST_DB_PATH.exists():
                try:
                    TEST_DB_PATH.unlink()
                    print("\nTemporary SQLite database cleaned up.")
                except Exception as e:
                    print(f"\nWarning: could not delete temporary database file: {e}")

if __name__ == "__main__":
    run_tests()


