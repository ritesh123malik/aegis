import requests
from sqlalchemy import create_engine, text
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DATABASE_URL = "postgresql://aegis:aegis@localhost:5432/aegis"
if (PROJECT_ROOT / ".env").exists():
    with open(PROJECT_ROOT / ".env") as f:
        for line in f:
            if line.startswith("DATABASE_URL="):
                DATABASE_URL = line.split("=")[1].strip()

engine = create_engine(DATABASE_URL)
backend_url = "http://localhost:8000"

def test():
    # --- CASE 1: Planned event on others/Varthur Road (150.0 bias, 2 outcomes) ---
    print("\n--- CASE 1: Planned event on others/Varthur Road (150.0 bias, 2 outcomes) ---")
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM predictions WHERE event_id = 'test-trans-planned-1'"))
        conn.execute(text("DELETE FROM events WHERE event_id = 'test-trans-planned-1'"))
        conn.execute(text("DELETE FROM recalibration_log WHERE event_cause = 'others' AND corridor = 'Varthur Road'"))
        
        # Insert recalibration log
        conn.execute(text(
            "INSERT INTO recalibration_log (event_cause, corridor, old_bias_correction, new_bias_correction, n_outcomes_used, recalibrated_at) "
            "VALUES ('others', 'Varthur Road', 100.0, 150.0, 2, CURRENT_TIMESTAMP)"
        ))
        
        # Insert target event
        conn.execute(text(
            "INSERT INTO events (event_id, event_type, event_cause, corridor, latitude, longitude, "
            "requires_road_closure, priority, start_datetime) VALUES "
            "('test-trans-planned-1', 'planned', 'others', 'Varthur Road', 12.95, 77.70, TRUE, 'High', '2024-03-05 01:00:00')"
        ))
        conn.commit()

    r1 = requests.post(f"{backend_url}/predict", json={"event_id": "test-trans-planned-1"})
    print("Response Status:", r1.status_code)
    print(requests.compat.json.dumps(r1.json(), indent=2))

    # --- CASE 2: Planned event in a bucket with ZERO logged outcomes ---
    print("\n--- CASE 2: Planned event in a bucket with ZERO logged outcomes ---")
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM predictions WHERE event_id = 'test-trans-planned-zero'"))
        conn.execute(text("DELETE FROM events WHERE event_id = 'test-trans-planned-zero'"))
        
        # Insert target event in an uncalibrated bucket: 'vip_movement' on 'Varthur Road'
        conn.execute(text(
            "INSERT INTO events (event_id, event_type, event_cause, corridor, latitude, longitude, "
            "requires_road_closure, priority, start_datetime) VALUES "
            "('test-trans-planned-zero', 'planned', 'vip_movement', 'Varthur Road', 12.95, 77.70, TRUE, 'High', '2024-03-05 01:00:00')"
        ))
        conn.commit()

    r2 = requests.post(f"{backend_url}/predict", json={"event_id": "test-trans-planned-zero"})
    print("Response Status:", r2.status_code)
    print(requests.compat.json.dumps(r2.json(), indent=2))

    # --- CASE 3: Unplanned event ---
    print("\n--- CASE 3: Unplanned event ---")
    # FKID000000 is a real unplanned event in our database
    r3 = requests.post(f"{backend_url}/predict", json={"event_id": "FKID000000"})
    print("Response Status:", r3.status_code)
    print(requests.compat.json.dumps(r3.json(), indent=2))

    # Clean up test events
    print("\nCleaning up test events...")
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM predictions WHERE event_id IN ('test-trans-planned-1', 'test-trans-planned-zero')"))
        conn.execute(text("DELETE FROM events WHERE event_id IN ('test-trans-planned-1', 'test-trans-planned-zero')"))
        conn.execute(text("DELETE FROM recalibration_log WHERE event_cause = 'others' AND corridor = 'Varthur Road'"))
        conn.commit()
    print("Cleanup complete.")

if __name__ == "__main__":
    test()
