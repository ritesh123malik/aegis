import requests
import json
import sys
from pathlib import Path
from sqlalchemy import create_engine, text

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# Read database URL from .env
DATABASE_URL = "postgresql://aegis:aegis@localhost:5432/aegis"
if (PROJECT_ROOT / ".env").exists():
    with open(PROJECT_ROOT / ".env") as f:
        for line in f:
            if line.startswith("DATABASE_URL="):
                DATABASE_URL = line.split("=")[1].strip()

engine = create_engine(DATABASE_URL)
backend_url = "http://localhost:8000"

def check_step_1():
    print("--- Step 1: Health Check ---")
    try:
        r = requests.get(f"{backend_url}/health")
        if r.status_code == 200 and r.json().get("status") == "ok":
            print("STEP 1: PASS")
            return True
        else:
            print(f"STEP 1: FAIL (status: {r.status_code}, body: {r.text})")
            return False
    except Exception as e:
        print(f"STEP 1: FAIL (connection failed: {e})")
        return False

def check_step_2():
    print("\n--- Step 2: Row Count in events Table ---")
    try:
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM events")).fetchone()[0]
        print(f"Observed event count: {count}")
        if count >= 8100 and count <= 8200:
            print("STEP 2: PASS")
            return True
        else:
            print(f"STEP 2: FAIL (unexpected count: {count})")
            return False
    except Exception as e:
        print(f"STEP 2: FAIL (query failed: {e})")
        return False

def check_step_3():
    print("\n--- Step 3: Predict Planned Event ---")
    try:
        # Pick a planned event
        with engine.connect() as conn:
            row = conn.execute(text("SELECT event_id FROM events WHERE event_type = 'planned' LIMIT 1")).fetchone()
        if not row:
            print("STEP 3: FAIL (No planned event in database)")
            return False
        event_id = row[0]
        print(f"Picked planned event_id: {event_id}")

        r = requests.post(f"{backend_url}/predict", json={"event_id": event_id})
        print(f"Response: {r.status_code} - {r.text}")
        if r.status_code != 200:
            print("STEP 3: FAIL (POST /predict returned error)")
            return False
        
        data = r.json()
        pred_duration = data.get("predicted_duration_min")
        pred_disruption = data.get("predicted_disruption_class")
        confidence = data.get("confidence_score")

        if pred_duration is not None and pred_disruption is None and confidence is not None:
            print(f"STEP 3: PASS (duration={pred_duration}, confidence={confidence})")
            return True, event_id
        else:
            print("STEP 3: FAIL (response fields incorrect)")
            return False
    except Exception as e:
        print(f"STEP 3: FAIL ({e})")
        return False

def check_step_4():
    print("\n--- Step 4: Predict Unplanned Event ---")
    try:
        # Pick an unplanned event
        with engine.connect() as conn:
            row = conn.execute(text("SELECT event_id FROM events WHERE event_type = 'unplanned' LIMIT 1")).fetchone()
        if not row:
            print("STEP 4: FAIL (No unplanned event in database)")
            return False
        event_id = row[0]
        print(f"Picked unplanned event_id: {event_id}")

        r = requests.post(f"{backend_url}/predict", json={"event_id": event_id})
        print(f"Response: {r.status_code} - {r.text}")
        if r.status_code != 200:
            print("STEP 4: FAIL (POST /predict returned error)")
            return False

        data = r.json()
        pred_duration = data.get("predicted_duration_min")
        pred_disruption = data.get("predicted_disruption_class")

        if pred_disruption is not None and pred_duration is None:
            print(f"STEP 4: PASS (disruption_class={pred_disruption})")
            return True
        else:
            print("STEP 4: FAIL (response fields incorrect)")
            return False
    except Exception as e:
        print(f"STEP 4: FAIL ({e})")
        return False

def check_step_5_and_6():
    print("\n--- Steps 5 & 6: Low Data Warning and Recommendations ---")
    try:
        # We need a combination with very few historical examples.
        # Find a low frequency bucket (e.g. event_cause='protest')
        with engine.connect() as conn:
            row = conn.execute(text(
                "SELECT event_cause, corridor, COUNT(*) FROM events "
                "GROUP BY event_cause, corridor "
                "HAVING COUNT(*) < 5 "
                "ORDER BY COUNT(*) ASC LIMIT 1"
            )).fetchone()
        
        if not row:
            # Fallback
            cause, corridor = "protest", "Mysore Road"
        else:
            cause, corridor = row[0], row[1]
            
        print(f"Low-frequency combination: cause='{cause}', corridor='{corridor}'")

        # Create a new temporary event to run prediction and recommendation on
        temp_id = "test-low-data-event-id"
        with engine.connect() as conn:
            # Delete if exists
            conn.execute(text("DELETE FROM predictions WHERE event_id = :eid"), {"eid": temp_id})
            conn.execute(text("DELETE FROM events WHERE event_id = :eid"), {"eid": temp_id})
            conn.execute(text(
                "INSERT INTO events (event_id, event_type, event_cause, corridor, latitude, longitude, "
                "requires_road_closure, priority, start_datetime) VALUES "
                "(:eid, 'planned', :cause, :corridor, 12.97, 77.59, TRUE, 'High', CURRENT_TIMESTAMP)"
            ), {"eid": temp_id, "cause": cause, "corridor": corridor})
            conn.commit()

        # Step 5: Run prediction
        print("Testing POST /predict...")
        r_pred = requests.post(f"{backend_url}/predict", json={"event_id": temp_id})
        print(f"Predict Response: {r_pred.status_code} - {r_pred.text}")
        if r_pred.status_code != 200:
            print("STEP 5: FAIL (prediction failed)")
            return False

        pred_data = r_pred.json()
        low_data_warning = pred_data.get("low_data_warning")
        
        if low_data_warning is True:
            print("STEP 5: PASS (low_data_warning is True)")
        else:
            print(f"STEP 5: FAIL (low_data_warning is {low_data_warning}, expected True)")
            return False

        # Step 6: Get recommendations
        print("Testing GET /recommend...")
        r_rec = requests.get(f"{backend_url}/recommend/{temp_id}")
        print(f"Recommend Response: {r_rec.status_code} - {r_rec.text}")
        if r_rec.status_code != 200:
            print("STEP 6: FAIL (recommendation failed)")
            return False

        rec_data = r_rec.json()
        officers = rec_data.get("recommended_officers")
        barricades = rec_data.get("recommended_barricades")
        
        print(f"Recommended officers: {officers}")
        print(f"Recommended barricades count: {len(barricades) if barricades else 0}")
        
        if officers is not None and barricades is not None:
            print("STEP 6: PASS")
        else:
            print("STEP 6: FAIL (recommended fields missing)")
            return False

        return True, temp_id, cause, corridor
    except Exception as e:
        print(f"STEP 5 & 6: FAIL ({e})")
        return False

def check_step_8_9_10(temp_id, cause, corridor):
    print("\n--- Steps 8, 9 & 10: Feedback Loop and Bias Calibration ---")
    try:
        # Clean existing outcomes or recalibration log for this bucket so we start fresh
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM outcomes WHERE event_id = :eid"), {"eid": temp_id})
            conn.execute(text("DELETE FROM recalibration_log WHERE event_cause = :cause AND corridor = :corr"), {"cause": cause, "corr": corridor})
            conn.commit()

        # Get initial prediction for model output logging
        r_init_pred = requests.post(f"{backend_url}/predict", json={"event_id": temp_id})
        init_pred_val = r_init_pred.json().get("predicted_duration_min")
        print(f"Initial raw/predicted duration: {init_pred_val}")

        # Step 8: Log outcome 1
        # Predicted was init_pred_val. Let's submit actual_duration_min = init_pred_val + 100
        actual_1 = init_pred_val + 100.0 if init_pred_val else 150.0
        payload_1 = {
            "event_id": temp_id,
            "actual_duration_min": actual_1,
            "actual_disruption_class": "Critical",
            "actual_officers_deployed": 12,
            "notes": "First integration test outcome",
            "logged_by": "Test Operator 1"
        }
        print(f"Logging first outcome: {payload_1}")
        r_out_1 = requests.post(f"{backend_url}/outcomes", json=payload_1)
        print(f"Outcomes response 1: {r_out_1.status_code} - {r_out_1.text}")
        if r_out_1.status_code != 200:
            print("STEP 8: FAIL (failed to insert outcome 1)")
            return False

        # Verify outcome 1 in database and recalibration_log
        with engine.connect() as conn:
            outcome_row = conn.execute(text("SELECT COUNT(*) FROM outcomes WHERE event_id = :eid"), {"eid": temp_id}).fetchone()
            recal_row = conn.execute(text(
                "SELECT old_bias_correction, new_bias_correction, n_outcomes_used FROM recalibration_log "
                "WHERE event_cause = :cause AND corridor = :corr ORDER BY recalibrated_at DESC LIMIT 1"
            ), {"cause": cause, "corr": corridor}).fetchone()

        if outcome_row[0] != 1 or not recal_row:
            print("STEP 8: FAIL (database state incorrect after outcome 1)")
            return False

        old_bias_1, new_bias_1, n_out_1 = recal_row
        print(f"Recalibration log 1: old_bias={old_bias_1}, new_bias={new_bias_1}, n_outcomes_used={n_out_1}")
        
        if n_out_1 == 1:
            print(f"STEP 8: PASS (n_outcomes_used={n_out_1})")
        else:
            print(f"STEP 8: FAIL (n_outcomes_used={n_out_1}, expected 1)")
            return False

        # Step 9: Log outcome 2 (SAME event bucket, we can log it for the same event or another one, let's log it for the same event by cleaning/reinserting or just submitting another outcome)
        # Note: outcomes table has serial primary key, so we can insert another outcome for the same event_id, or we can just POST it again.
        # But wait, in the db, outcomes has outcome_id as primary key and event_id is a foreign key (not unique), so we can insert multiple outcomes for the same event_id!
        # Let's do that.
        actual_2 = init_pred_val + 200.0 if init_pred_val else 250.0
        payload_2 = {
            "event_id": temp_id,
            "actual_duration_min": actual_2,
            "actual_disruption_class": "Critical",
            "actual_officers_deployed": 15,
            "notes": "Second integration test outcome",
            "logged_by": "Test Operator 2"
        }
        print(f"Logging second outcome: {payload_2}")
        r_out_2 = requests.post(f"{backend_url}/outcomes", json=payload_2)
        print(f"Outcomes response 2: {r_out_2.status_code} - {r_out_2.text}")
        if r_out_2.status_code != 200:
            print("STEP 9: FAIL (failed to insert outcome 2)")
            return False

        with engine.connect() as conn:
            recal_row_2 = conn.execute(text(
                "SELECT old_bias_correction, new_bias_correction, n_outcomes_used FROM recalibration_log "
                "WHERE event_cause = :cause AND corridor = :corr ORDER BY recalibrated_at DESC LIMIT 1"
            ), {"cause": cause, "corr": corridor}).fetchone()

        if not recal_row_2:
            print("STEP 9: FAIL (No recalibration row for second outcome)")
            return False

        old_bias_2, new_bias_2, n_out_2 = recal_row_2
        print(f"Recalibration log 2: old_bias={old_bias_2}, new_bias={new_bias_2}, n_outcomes_used={n_out_2}")
        
        if n_out_2 == n_out_1 + 1:
            print(f"STEP 9: PASS ({n_out_1} then {n_out_2})")
        else:
            print(f"STEP 9: FAIL (n_outcomes_used={n_out_2}, expected {n_out_1 + 1})")
            return False

        # Step 10: Call predict again for a NEW event sharing the same bucket
        new_event_id = "test-new-event-id"
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM predictions WHERE event_id = :eid"), {"eid": new_event_id})
            conn.execute(text("DELETE FROM events WHERE event_id = :eid"), {"eid": new_event_id})
            conn.execute(text(
                "INSERT INTO events (event_id, event_type, event_cause, corridor, latitude, longitude, "
                "requires_road_closure, priority, start_datetime) VALUES "
                "(:eid, 'planned', :cause, :corridor, 12.97, 77.59, TRUE, 'High', CURRENT_TIMESTAMP)"
            ), {"eid": new_event_id, "cause": cause, "corridor": corridor})
            conn.commit()

        # Let's predict!
        r_new_pred = requests.post(f"{backend_url}/predict", json={"event_id": new_event_id})
        print(f"New Predict Response: {r_new_pred.status_code} - {r_new_pred.text}")
        if r_new_pred.status_code != 200:
            print("STEP 10: FAIL (new prediction failed)")
            return False

        new_pred_data = r_new_pred.json()
        new_pred_val = new_pred_data.get("predicted_duration_min")

        # Let's verify that bias correction was applied
        # In step 10, final prediction = raw model output + new_bias_correction
        # We can see what raw model output is. But wait, does the endpoint return both raw and bias corrected?
        # Let's look at the response schema or predict router.
        print(f"New bias-corrected prediction: {new_pred_val}")
        print(f"Expected raw model prediction (roughly): {init_pred_val}")
        print(f"Applied bias correction: {new_bias_2}")
        
        # Let's check if the prediction is adjusted:
        # Since we set actual_1 = init_pred_val + 100, actual_2 = init_pred_val + 200,
        # the new_bias_correction should be roughly +150.
        # Let's check if the new_pred_val matches raw + bias.
        diff = new_pred_val - init_pred_val
        print(f"Difference in prediction: {diff} (expected around {new_bias_2})")
        
        if abs(diff - new_bias_2) < 1e-2:
            print(f"STEP 10: PASS (Raw model output: {init_pred_val:.2f}, Final bias-corrected output: {new_pred_val:.2f}, Difference: {diff:.2f})")
        else:
            print(f"STEP 10: FAIL (Prediction difference {diff:.2f} does not match bias correction {new_bias_2:.2f})")
            return False

        # Cleanup
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM outcomes WHERE event_id IN (:eid1, :eid2)"), {"eid1": temp_id, "eid2": new_event_id})
            conn.execute(text("DELETE FROM predictions WHERE event_id IN (:eid1, :eid2)"), {"eid1": temp_id, "eid2": new_event_id})
            conn.execute(text("DELETE FROM events WHERE event_id IN (:eid1, :eid2)"), {"eid1": temp_id, "eid2": new_event_id})
            conn.execute(text("DELETE FROM recalibration_log WHERE event_cause = :cause AND corridor = :corr"), {"cause": cause, "corr": corridor})
            conn.commit()

        return True
    except Exception as e:
        print(f"STEP 8, 9 & 10: FAIL ({e})")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if not check_step_1():
        sys.exit(1)
    if not check_step_2():
        sys.exit(1)
    res_3 = check_step_3()
    if not res_3:
        sys.exit(1)
    if not check_step_4():
        sys.exit(1)
    res_5_6 = check_step_5_and_6()
    if not res_5_6:
        sys.exit(1)
    
    _, temp_id, cause, corridor = res_5_6
    if not check_step_8_9_10(temp_id, cause, corridor):
        sys.exit(1)
    
    print("\nALL API-BASED STEPS RUN COMPLETED!")
