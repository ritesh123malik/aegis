import requests
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

def verify_unplanned_events():
    # Pick 5 unplanned events from different causes/corridors
    query_str = """
        SELECT event_id, event_cause, corridor
        FROM events
        WHERE event_type = 'unplanned'
        LIMIT 50
    """
    with engine.connect() as conn:
        events = conn.execute(text(query_str)).fetchall()
        
    # Pick 5 with different causes/corridors to ensure variety
    selected = []
    seen_causes = set()
    for ev in events:
        if ev.event_cause not in seen_causes:
            selected.append(ev)
            seen_causes.add(ev.event_cause)
        if len(selected) == 5:
            break
            
    print("--- Selected 5 Real Unplanned Events for Verification ---")
    print(f"{'Event ID':<15} | {'Cause':<20} | {'Corridor':<30}")
    print("-" * 75)
    for ev in selected:
        print(f"{ev.event_id:<15} | {ev.event_cause:<20} | {ev.corridor:<30}")

    print("\n--- Running Predictions (Unplanned Severity Classifier) ---")
    print(f"{'Event ID':<15} | {'Predicted Class':<18} | {'Confidence (predict_proba)':<26}")
    print("-" * 70)
    
    confidence_scores = []
    for ev in selected:
        r = requests.post(f"{backend_url}/predict", json={"event_id": ev.event_id})
        if r.status_code != 200:
            print(f"Error predicting on {ev.event_id}: {r.text}")
            continue
        data = r.json()
        conf = data.get("confidence_score")
        pred_class = data.get("predicted_disruption_class")
        print(f"{ev.event_id:<15} | {pred_class:<18} | {conf:<26.6f}")
        confidence_scores.append(conf)

    unique_scores = set(confidence_scores)
    print("\n--- Results Summary ---")
    print(f"Confidence scores: {[round(c, 6) for c in confidence_scores]}")
    print(f"Unique count: {len(unique_scores)} out of {len(confidence_scores)}")
    
    if len(unique_scores) == len(confidence_scores):
        print("VERIFICATION: PASS (All 5 unplanned confidence scores are unique class probabilities!)")
    else:
        print("VERIFICATION: FAIL (Duplicate confidence scores found!)")

if __name__ == "__main__":
    verify_unplanned_events()
