import requests
from sqlalchemy import create_engine, text
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent
DATABASE_URL = "postgresql://aegis:aegis@localhost:5432/aegis"
if (PROJECT_ROOT / ".env").exists():
    with open(PROJECT_ROOT / ".env") as f:
        for line in f:
            if line.startswith("DATABASE_URL="):
                DATABASE_URL = line.split("=")[1].strip()

engine = create_engine(DATABASE_URL)
backend_url = "http://localhost:8000"

def seed():
    print("Cleaning up old test outcomes...")
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM outcomes"))
        conn.execute(text("DELETE FROM predictions"))
        conn.execute(text("DELETE FROM recalibration_log"))
        conn.commit()

    # Find 3 planned events
    with engine.connect() as conn:
        planned = conn.execute(text(
            "SELECT event_id, event_cause, corridor FROM events WHERE event_type = 'planned' LIMIT 3"
        )).fetchall()
        unplanned = conn.execute(text(
            "SELECT event_id, event_cause, corridor FROM events WHERE event_type = 'unplanned' LIMIT 3"
        )).fetchall()

    print(f"Found planned: {planned}")
    print(f"Found unplanned: {unplanned}")

    # For planned event 1:
    # Let's run prediction, then log outcome. Since no bias exists, active_bias is 0.0.
    ev_p1 = planned[0]
    print(f"\nSeeding Planned Case 1: {ev_p1.event_id}")
    r = requests.post(f"{backend_url}/predict", json={"event_id": ev_p1.event_id})
    pred1 = r.json()
    pred_dur1 = pred1["predicted_duration_min"]
    print(f"Prediction 1: {pred_dur1}")
    # Log outcome with error: actual is pred_dur1 + 60
    requests.post(f"{backend_url}/outcomes", json={
        "event_id": ev_p1.event_id,
        "actual_duration_min": pred_dur1 + 60.0,
        "notes": "Planned outcome 1",
        "logged_by": "Test Operator"
    })
    
    # Recalibration will now establish a bias of +60 for ev_p1's bucket (cause, corridor)
    # Let's predict on the SAME bucket for another event (planned event 2)
    ev_p2 = planned[1]
    # Let's temporarily change ev_p2's cause and corridor to match ev_p1 so they share the bucket
    with engine.connect() as conn:
        conn.execute(text(
            "UPDATE events SET event_cause = :cause, corridor = :corridor WHERE event_id = :eid"
        ), {"cause": ev_p1.event_cause, "corridor": ev_p1.corridor, "eid": ev_p2.event_id})
        conn.commit()

    print(f"\nSeeding Planned Case 2 (shares bucket with Case 1): {ev_p2.event_id}")
    r = requests.post(f"{backend_url}/predict", json={"event_id": ev_p2.event_id})
    pred2 = r.json()
    pred_dur2 = pred2["predicted_duration_min"]
    print(f"Prediction 2 (corrected): {pred_dur2}")
    # At this point, active bias was +60.
    # Raw prediction is pred_dur2 - 60.
    # If actual duration is close to pred_dur2 (e.g. pred_dur2 + 5),
    # the corrected_error will be 5, while raw_error would be abs((pred_dur2 + 5) - (pred_dur2 - 60)) = 65!
    # This demonstrates the recalibration loop helping.
    requests.post(f"{backend_url}/outcomes", json={
        "event_id": ev_p2.event_id,
        "actual_duration_min": pred_dur2 + 5.0,
        "notes": "Planned outcome 2",
        "logged_by": "Test Operator"
    })

    # For planned event 3 (different bucket):
    ev_p3 = planned[2]
    print(f"\nSeeding Planned Case 3: {ev_p3.event_id}")
    r = requests.post(f"{backend_url}/predict", json={"event_id": ev_p3.event_id})
    pred3 = r.json()
    pred_dur3 = pred3["predicted_duration_min"]
    print(f"Prediction 3: {pred_dur3}")
    # Log outcome with error: actual is pred_dur3 + 30
    requests.post(f"{backend_url}/outcomes", json={
        "event_id": ev_p3.event_id,
        "actual_duration_min": pred_dur3 + 30.0,
        "notes": "Planned outcome 3",
        "logged_by": "Test Operator"
    })

    # For unplanned events (severity predictions)
    # Case 1: Correct prediction
    ev_u1 = unplanned[0]
    print(f"\nSeeding Unplanned Case 1: {ev_u1.event_id}")
    r = requests.post(f"{backend_url}/predict", json={"event_id": ev_u1.event_id})
    pred_u1 = r.json()
    pred_class1 = pred_u1["predicted_disruption_class"]
    print(f"Prediction: {pred_class1}")
    requests.post(f"{backend_url}/outcomes", json={
        "event_id": ev_u1.event_id,
        "actual_disruption_class": pred_class1,
        "notes": "Correct severity 1",
        "logged_by": "Test Operator"
    })

    # Case 2: Correct prediction
    ev_u2 = unplanned[1]
    print(f"\nSeeding Unplanned Case 2: {ev_u2.event_id}")
    r = requests.post(f"{backend_url}/predict", json={"event_id": ev_u2.event_id})
    pred_u2 = r.json()
    pred_class2 = pred_u2["predicted_disruption_class"]
    print(f"Prediction: {pred_class2}")
    requests.post(f"{backend_url}/outcomes", json={
        "event_id": ev_u2.event_id,
        "actual_disruption_class": pred_class2,
        "notes": "Correct severity 2",
        "logged_by": "Test Operator"
    })

    # Case 3: Mismatched prediction
    ev_u3 = unplanned[2]
    print(f"\nSeeding Unplanned Case 3: {ev_u3.event_id}")
    r = requests.post(f"{backend_url}/predict", json={"event_id": ev_u3.event_id})
    pred_u3 = r.json()
    pred_class3 = pred_u3["predicted_disruption_class"]
    incorrect_class = "Critical" if pred_class3 != "Critical" else "Low"
    print(f"Prediction: {pred_class3} | Actual Outcome will be: {incorrect_class}")
    requests.post(f"{backend_url}/outcomes", json={
        "event_id": ev_u3.event_id,
        "actual_disruption_class": incorrect_class,
        "notes": "Incorrect severity",
        "logged_by": "Test Operator"
    })

    print("\nOutcome seeding complete!")

if __name__ == "__main__":
    seed()
