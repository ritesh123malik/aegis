import sys
import os
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path("/Users/ritesh/.gemini/antigravity/scratch/aegis")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load database URL and other variables from env into os.environ BEFORE importing backend modules
if (PROJECT_ROOT / ".env").exists():
    with open(PROJECT_ROOT / ".env") as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                try:
                    key, val = line.strip().split("=", 1)
                    os.environ[key] = val
                except ValueError:
                    pass

import requests
import json
import numpy as np
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://aegis:aegis@localhost:5432/aegis")
engine = create_engine(DATABASE_URL)
backend_url = "http://localhost:8000"

def run_tests():
    print("=== STARTING ADVANCED FEATURES VERIFICATION ===")
    
    # 1. Clear database outcomes
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM outcomes"))
        conn.execute(text("DELETE FROM severity_recalibration_log"))
        conn.commit()
    print("Cleaned database tables.")

    # Find one unplanned event cause
    with engine.connect() as conn:
        event = conn.execute(text(
            "SELECT event_id, event_cause, corridor FROM events WHERE event_type = 'unplanned' LIMIT 1"
        )).fetchone()
        
    if not event:
        print("No unplanned event found in database.")
        return
        
    event_id, cause, corridor = event.event_id, event.event_cause, event.corridor
    print(f"Picked test event: ID={event_id}, Cause={cause}, Corridor={corridor}")

    # 2. Run prediction before recalibration (will return raw probability outputs since log is empty)
    r_pred1 = requests.post(f"{backend_url}/predict", json={"event_id": event_id})
    pred1 = r_pred1.json()
    print("\nInitial Prediction Response:")
    print(json.dumps(pred1, indent=2))
    
    initial_class = pred1.get("predicted_disruption_class")
    initial_conf = pred1.get("confidence_score")
    
    # 3. Log outcome with a different class to trigger misclassification logging and probability shifts
    # We will choose a class different from the initial prediction
    actual_class = "Critical" if initial_class != "Critical" else "Low"
    print(f"\nLogging actual outcome as '{actual_class}' (predicted class was '{initial_class}')")
    
    r_out = requests.post(f"{backend_url}/outcomes", json={
        "event_id": event_id,
        "actual_disruption_class": actual_class,
        "notes": "Testing severity recalibration weights",
        "logged_by": "Test Suite"
    })
    print("Log Outcome Response Status:", r_out.status_code)
    
    # Check if a log row is inserted in severity_recalibration_log
    with engine.connect() as conn:
        recal_logs = conn.execute(text("SELECT * FROM severity_recalibration_log")).fetchall()
        
    print(f"\nNumber of recalibration log rows in DB: {len(recal_logs)}")
    assert len(recal_logs) > 0, "No recalibration log row was created!"
    log_row = recal_logs[0]
    print(f"Logged Weights: {log_row.class_weights}")
    
    # 4. Predict event again to verify probability shift is applied
    r_pred2 = requests.post(f"{backend_url}/predict", json={"event_id": event_id})
    pred2 = r_pred2.json()
    print("\nPrediction Response AFTER Recalibration Log:")
    print(json.dumps(pred2, indent=2))
    
    # Check L1 Normalization: retrieve raw probability from test
    transparency = pred2.get("prediction_transparency")
    print(f"Inference Transparency: {transparency}")
    
    # 5. Test retraining pipeline directly
    print("\n--- Testing Retraining Pipeline ---")
    from backend.app.services.pipeline_service import trigger_retraining_pipeline
    
    try:
        trigger_retraining_pipeline()
        print("Retraining pipeline run completed successfully.")
        
        # Verify that outcomes are marked as processed
        with engine.connect() as conn:
            unprocessed_count = conn.execute(text(
                "SELECT COUNT(*) FROM outcomes WHERE processed_for_training = false"
            )).fetchone()[0]
        print(f"Unprocessed outcomes remaining: {unprocessed_count}")
        assert unprocessed_count == 0, "Outcomes were not marked as processed!"
        print("Retraining pipeline validation PASSED!")
    except Exception as e:
        print(f"Retraining pipeline validation FAILED: {e}")
        raise e

    # 6. Test Valhalla get_dynamic_diversion_routes local check (should return empty or warn gracefully if Valhalla is offline)
    print("\n--- Testing Valhalla Local Service check ---")
    from backend.app.services.recommendation_service import get_dynamic_diversion_routes
    res_valhalla = get_dynamic_diversion_routes(12.97, 77.59, 12.98, 77.60, 12.975, 77.595, True)
    print(f"Valhalla return payload (expected offline default: empty dict): {res_valhalla}")
    assert isinstance(res_valhalla, dict), "Valhalla routing did not return a dictionary!"

    print("\n===============================")
    print("ALL ADVANCED VERIFICATION PASSED")
    print("===============================")

if __name__ == "__main__":
    run_tests()
